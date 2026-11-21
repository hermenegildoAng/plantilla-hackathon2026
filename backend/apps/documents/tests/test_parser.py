from datetime import datetime
from decimal import Decimal

import pytest

from apps.documents.services import CfdiParseError, parse_cfdi_xml
from apps.documents.tests.utils import build_cfdi_xml


@pytest.mark.parametrize("cfdi_type", ["I", "E", "T", "N", "P"])
def test_parser_accepts_every_supported_cfdi_type(cfdi_type):
    content = build_cfdi_xml(cfdi_type=cfdi_type)

    parsed = parse_cfdi_xml(content)

    assert parsed["cfdi_type"] == cfdi_type
    assert str(parsed["uuid"]) == "550e8400-e29b-41d4-a716-446655440000"
    assert parsed["cfdi_version"] == "4.0"


@pytest.mark.parametrize("cfdi_type", ["P", "N"])
def test_parser_is_tolerant_with_payment_and_payroll_without_optional_fields(
    cfdi_type,
):
    content = build_cfdi_xml(
        cfdi_type=cfdi_type,
        subtotal="0.00",
        total="0.00",
        iva_transferred="0.00",
        include_taxes=False,
        payment_method=None,
        payment_form=None,
        currency="MXN",
    )

    parsed = parse_cfdi_xml(content)

    assert parsed["cfdi_type"] == cfdi_type
    assert parsed["payment_method"] == ""
    assert parsed["payment_form"] == ""
    assert parsed["subtotal"] == Decimal("0.00")
    assert parsed["total"] == Decimal("0.00")
    assert parsed["iva_transferred"] == Decimal("0.00")


def test_parser_supports_cfdi_3_3_namespace():
    content = build_cfdi_xml(version="3.3")

    parsed = parse_cfdi_xml(content)

    assert parsed["cfdi_version"] == "3.3"


def test_parser_extracts_issuer_receiver_payment_and_currency():
    content = build_cfdi_xml(
        issuer_rfc="CNO200101AB9",
        issuer_name="Comercializadora del Norte",
        receiver_rfc="SDA210515XY1",
        receiver_name="Servicios Digitales del Altiplano",
        payment_method="PPD",
        payment_form="99",
        currency="USD",
        exchange_rate="17.2500",
        subtotal="1000.00",
        discount="50.00",
        iva_transferred="152.00",
        total="1102.00",
    )

    parsed = parse_cfdi_xml(content)

    assert parsed["issuer_rfc"] == "CNO200101AB9"
    assert parsed["issuer_name"] == "Comercializadora del Norte"
    assert parsed["receiver_rfc"] == "SDA210515XY1"
    assert parsed["receiver_name"] == "Servicios Digitales del Altiplano"
    assert parsed["payment_method"] == "PPD"
    assert parsed["payment_form"] == "99"
    assert parsed["currency"] == "USD"
    assert parsed["exchange_rate"] == Decimal("17.2500")
    assert parsed["subtotal"] == Decimal("1000.00")
    assert parsed["discount"] == Decimal("50.00")
    assert parsed["iva_transferred"] == Decimal("152.00")
    assert parsed["total"] == Decimal("1102.00")


def test_parser_extracts_iva_ieps_and_retentions():
    content = build_cfdi_xml(
        subtotal="1000.00",
        iva_transferred="160.00",
        ieps_transferred="80.00",
        iva_retained="106.67",
        isr_retained="12.50",
        total="1120.83",
    )

    parsed = parse_cfdi_xml(content)

    assert parsed["iva_transferred"] == Decimal("160.00")
    assert parsed["ieps_transferred"] == Decimal("80.00")
    assert parsed["iva_retained"] == Decimal("106.67")
    assert parsed["isr_retained"] == Decimal("12.50")


def test_parser_localizes_issue_date_to_mexico_city():
    content = build_cfdi_xml(fecha="2026-05-15T10:30:00")

    parsed = parse_cfdi_xml(content)

    assert isinstance(parsed["issue_date"], datetime)
    assert parsed["issue_date"].tzinfo is not None
    assert parsed["issue_date"].utcoffset().total_seconds() == -6 * 3600
    assert parsed["issue_date"].date().isoformat() == "2026-05-15"


def test_parser_keeps_concepts_and_complements_in_raw_metadata():
    content = build_cfdi_xml(
        extra_complement=(
            '<pago10:Pagos xmlns:pago10="http://www.sat.gob.mx/Pagos" '
            'Version="1.0"/>'
        )
    )

    parsed = parse_cfdi_xml(content)

    metadata = parsed["raw_metadata"]
    assert metadata["conceptos"][0]["Descripcion"] == "Servicio profesional"
    tags = {item["tag"] for item in metadata["complementos"]}
    assert {"TimbreFiscalDigital", "Pagos"}.issubset(tags)


def test_parser_rejects_non_cfdi_root():
    content = b'<?xml version="1.0"?><Factura Version="4.0"></Factura>'

    with pytest.raises(CfdiParseError) as exc_info:
        parse_cfdi_xml(content)

    assert exc_info.value.code == "not_cfdi"


def test_parser_rejects_unsupported_version():
    content = build_cfdi_xml(version="5.0")

    with pytest.raises(CfdiParseError) as exc_info:
        parse_cfdi_xml(content)

    assert exc_info.value.code == "not_cfdi"


def test_parser_rejects_malformed_xml():
    with pytest.raises(CfdiParseError) as exc_info:
        parse_cfdi_xml(b"<cfdi:Comprobante>")

    assert exc_info.value.code == "invalid_xml"


def test_parser_rejects_missing_tfd_uuid():
    content = build_cfdi_xml(include_tfd=False)

    with pytest.raises(CfdiParseError) as exc_info:
        parse_cfdi_xml(content)

    assert exc_info.value.code == "invalid_xml"


def test_parser_rejects_xxe_external_entity():
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
 Version="4.0" Fecha="2026-05-15T10:30:00" SubTotal="1.00" Total="1.00"
 TipoDeComprobante="I">
 <cfdi:Emisor Rfc="CNO200101AB9" Nombre="Emisor"/>
 <cfdi:Receptor Rfc="SDA210515XY1" Nombre="Receptor"/>
 <cfdi:Conceptos/>
 &xxe;
</cfdi:Comprobante>
"""

    with pytest.raises(CfdiParseError) as exc_info:
        parse_cfdi_xml(content)

    assert exc_info.value.code == "invalid_xml"


def test_parser_rejects_billion_laughs_expansion():
    content = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
 Version="4.0" Fecha="2026-05-15T10:30:00" SubTotal="1.00" Total="1.00"
 TipoDeComprobante="I">
 <cfdi:Emisor Rfc="CNO200101AB9" Nombre="&lol3;"/>
 <cfdi:Receptor Rfc="SDA210515XY1" Nombre="Receptor"/>
 <cfdi:Conceptos/>
</cfdi:Comprobante>
"""

    with pytest.raises(CfdiParseError) as exc_info:
        parse_cfdi_xml(content)

    assert exc_info.value.code == "invalid_xml"
