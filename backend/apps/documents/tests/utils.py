"""Helpers to build safe CFDI XML fixtures for tests."""

from decimal import Decimal
from xml.sax.saxutils import escape


CFDI_NS = {
    "4.0": "http://www.sat.gob.mx/cfd/4",
    "3.3": "http://www.sat.gob.mx/cfd/3",
}


def _quantity(value) -> str:
    return format(Decimal(str(value)), ".2f")


def build_cfdi_xml(
    *,
    cfdi_type="I",
    version="4.0",
    uuid_value="550e8400-e29b-41d4-a716-446655440000",
    fecha="2026-05-15T10:30:00",
    issuer_rfc="CNO200101AB9",
    issuer_name="Comercializadora del Norte",
    receiver_rfc="SDA210515XY1",
    receiver_name="Servicios Digitales del Altiplano",
    subtotal="1000.00",
    discount="0.00",
    iva_transferred="160.00",
    ieps_transferred="0.00",
    iva_retained="0.00",
    isr_retained="0.00",
    total="1160.00",
    payment_method="PUE",
    payment_form="03",
    currency="MXN",
    exchange_rate=None,
    include_taxes=True,
    include_tfd=True,
    extra_complement="",
    root_tag="cfdi:Comprobante",
    xml_declaration=True,
):
    """Build a small but structurally valid CFDI with optional tax nodes."""
    namespace = CFDI_NS.get(version, CFDI_NS["4.0"])
    attributes = [
        f'xmlns:cfdi="{namespace}"',
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        f'Version="{version}"',
        f'Fecha="{fecha}"',
        f'SubTotal="{_quantity(subtotal)}"',
        f'Descuento="{_quantity(discount)}"',
        f'Moneda="{currency}"',
        f'Total="{_quantity(total)}"',
        f'TipoDeComprobante="{cfdi_type}"',
        'Serie="T"',
        'Folio="0001"',
        'LugarExpedicion="06600"',
    ]
    if payment_method:
        attributes.append(f'MetodoPago="{payment_method}"')
    if payment_form:
        attributes.append(f'FormaPago="{payment_form}"')
    if exchange_rate is not None:
        attributes.append(f'TipoCambio="{exchange_rate}"')

    tax_nodes = []
    if include_taxes and Decimal(str(iva_transferred or "0")) > 0:
        tax_nodes.append(
            f'<cfdi:Traslado Base="{_quantity(subtotal)}" Impuesto="002" '
            'TipoFactor="Tasa" TasaOCuota="0.160000" '
            f'Importe="{_quantity(iva_transferred)}"/>'
        )
    if include_taxes and Decimal(str(ieps_transferred or "0")) > 0:
        tax_nodes.append(
            f'<cfdi:Traslado Base="{_quantity(subtotal)}" Impuesto="003" '
            'TipoFactor="Tasa" TasaOCuota="0.080000" '
            f'Importe="{_quantity(ieps_transferred)}"/>'
        )

    retention_nodes = []
    if include_taxes and Decimal(str(iva_retained or "0")) > 0:
        retention_nodes.append(
            f'<cfdi:Retencion Base="{_quantity(subtotal)}" Impuesto="002" '
            'TipoFactor="Tasa" TasaOCuota="0.106667" '
            f'Importe="{_quantity(iva_retained)}"/>'
        )
    if include_taxes and Decimal(str(isr_retained or "0")) > 0:
        retention_nodes.append(
            f'<cfdi:Retencion Base="{_quantity(subtotal)}" Impuesto="001" '
            'TipoFactor="Tasa" TasaOCuota="0.012500" '
            f'Importe="{_quantity(isr_retained)}"/>'
        )

    impuestos_xml = ""
    if include_taxes and (tax_nodes or retention_nodes):
        total_retained = Decimal(str(iva_retained or "0")) + Decimal(
            str(isr_retained or "0")
        )
        impuestos_xml = (
            f'<cfdi:Impuestos TotalImpuestosTrasladados="'
            f'{_quantity(iva_transferred)}" '
            f'TotalImpuestosRetenidos="{_quantity(total_retained)}">'
        )
        if tax_nodes:
            impuestos_xml += (
                "<cfdi:Traslados>" + "".join(tax_nodes) + "</cfdi:Traslados>"
            )
        if retention_nodes:
            impuestos_xml += (
                "<cfdi:Retenciones>"
                + "".join(retention_nodes)
                + "</cfdi:Retenciones>"
            )
        impuestos_xml += "</cfdi:Impuestos>"

    tfd_xml = ""
    if include_tfd:
        tfd_xml = (
            '<cfdi:Complemento>'
            '<tfd:TimbreFiscalDigital '
            'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            'Version="1.1" '
            f'UUID="{uuid_value}" '
            'FechaTimbrado="2026-05-15T10:31:00" '
            'RfcProvCertif="SAT970701NN3" SelloCFD="" '
            'NoCertificadoSAT="00001000000500000000" SelloSAT=""/>'
            f"{extra_complement}"
            "</cfdi:Complemento>"
        )

    declaration = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        if xml_declaration
        else ""
    )
    return (
        declaration
        + f"<{root_tag} " + " ".join(attributes) + ">"
        + f'<cfdi:Emisor Rfc="{issuer_rfc}" Nombre="{escape(issuer_name)}" '
        'RegimenFiscal="601"/>'
        + f'<cfdi:Receptor Rfc="{receiver_rfc}" '
        f'Nombre="{escape(receiver_name)}" '
        'DomicilioFiscalReceptor="06600" RegimenFiscalReceptor="601" '
        'UsoCFDI="G03"/>'
        + "<cfdi:Conceptos>"
        + f'<cfdi:Concepto ClaveProdServ="84111506" Cantidad="1" '
        'ClaveUnidad="E48" Descripcion="Servicio profesional" '
        f'ValorUnitario="{_quantity(subtotal)}" '
        f'Importe="{_quantity(subtotal)}" '
        f'Descuento="{_quantity(discount)}" ObjetoImp="02"/>'
        + "</cfdi:Conceptos>"
        + impuestos_xml
        + tfd_xml
        + f"</{root_tag}>"
    ).encode("utf-8")
