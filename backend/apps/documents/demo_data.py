"""Deterministic CFDI 4.0 files used by the demo seed [E-25].

The XMLs are generated with valid CFDI namespaces, a TFD 1.1 and 16 % IVA.
Some invoices include IVA/ISR retentions. UUIDs are deterministic so running
the seed twice does not create duplicates.
"""

from datetime import date, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5
from xml.sax.saxutils import escape


def _money(value) -> str:
    return format(Decimal(str(value)), ".2f")


def _previous_month_date(today: date) -> date:
    first_day = today.replace(day=1)
    previous = first_day - timedelta(days=1)
    return date(previous.year, previous.month, 15)


def _tax_node(tax_code: str, base: str, rate: str, amount: str) -> str:
    return (
        f'<cfdi:Traslado Base="{base}" Impuesto="{tax_code}" '
        f'TipoFactor="Tasa" TasaOCuota="{rate}" Importe="{amount}"/>'
    )


def _retention_node(tax_code: str, base: str, rate: str, amount: str) -> str:
    return (
        f'<cfdi:Retencion Base="{base}" Impuesto="{tax_code}" '
        f'TipoFactor="Tasa" TasaOCuota="{rate}" Importe="{amount}"/>'
    )


def _build_xml(
    *,
    uuid_value,
    fecha: str,
    cfdi_type: str,
    issuer,
    receiver,
    subtotal: str,
    iva: str,
    total: str,
    series: str,
    folio: str,
    payment_method: str,
    payment_form: str,
    iva_retained: str = "0.00",
    isr_retained: str = "0.00",
    discount: str = "0.00",
    description: str,
    uso_cfdi: str,
) -> bytes:
    iva_decimal = Decimal(iva)
    iva_retained_decimal = Decimal(iva_retained)
    isr_retained_decimal = Decimal(isr_retained)
    total_retained = iva_retained_decimal + isr_retained_decimal

    concept_taxes = [
        _tax_node("002", subtotal, "0.160000", iva),
    ]
    if iva_retained_decimal:
        concept_taxes.append(
            _retention_node("002", subtotal, "0.106667", iva_retained)
        )
    if isr_retained_decimal:
        concept_taxes.append(
            _retention_node("001", subtotal, "0.012500", isr_retained)
        )

    root_taxes = (
        f' TotalImpuestosTrasladados="{iva}"'
        f' TotalImpuestosRetenidos="{_money(total_retained)}"'
    )
    retention_xml = ""
    if total_retained:
        retention_nodes = []
        if iva_retained_decimal:
            retention_nodes.append(
                _retention_node("002", subtotal, "0.106667", iva_retained)
            )
        if isr_retained_decimal:
            retention_nodes.append(
                _retention_node("001", subtotal, "0.012500", isr_retained)
            )
        retention_xml = (
            "<cfdi:Retenciones>"
            + "".join(retention_nodes)
            + "</cfdi:Retenciones>"
        )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xsi:schemaLocation="http://www.sat.gob.mx/cfd/4 http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd"
 Version="4.0" Serie="{escape(series)}" Folio="{escape(folio)}"
 Fecha="{fecha}" NoCertificado="00001000000500000000" Certificado=""
 SubTotal="{subtotal}" Descuento="{discount}" Moneda="MXN" Total="{total}"
 TipoDeComprobante="{cfdi_type}" Exportacion="01"
 MetodoPago="{payment_method}" FormaPago="{payment_form}"
 LugarExpedicion="06600">
 <cfdi:Emisor Rfc="{issuer['rfc']}" Nombre="{escape(issuer['name'])}"
  RegimenFiscal="{issuer['regime']}"/>
 <cfdi:Receptor Rfc="{receiver['rfc']}" Nombre="{escape(receiver['name'])}"
  DomicilioFiscalReceptor="06600" RegimenFiscalReceptor="{receiver['regime']}"
  UsoCFDI="{uso_cfdi}"/>
 <cfdi:Conceptos>
  <cfdi:Concepto ClaveProdServ="84111506" Cantidad="1" ClaveUnidad="E48"
   Descripcion="{escape(description)}" ValorUnitario="{subtotal}"
   Importe="{subtotal}" Descuento="{discount}" ObjetoImp="02">
   <cfdi:Impuestos>
    <cfdi:Traslados>{''.join(concept_taxes[:1])}</cfdi:Traslados>
    {('<cfdi:Retenciones>' + ''.join(concept_taxes[1:]) + '</cfdi:Retenciones>') if len(concept_taxes) > 1 else ''}
   </cfdi:Impuestos>
  </cfdi:Concepto>
 </cfdi:Conceptos>
 <cfdi:Impuestos{root_taxes}>
  <cfdi:Traslados>{_tax_node('002', subtotal, '0.160000', iva)}</cfdi:Traslados>
  {retention_xml}
 </cfdi:Impuestos>
 <cfdi:Complemento>
  <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
   Version="1.1" UUID="{uuid_value}" FechaTimbrado="{fecha}"
   RfcProvCertif="SAT970701NN3" SelloCFD="" NoCertificadoSAT="00001000000500000000"
   SelloSAT=""/>
 </cfdi:Complemento>
</cfdi:Comprobante>
"""
    return xml.encode("utf-8")


def build_demo_cfdi_files(company, counterpart, today: date):
    """Return five (filename, content) pairs for one demo company."""
    previous = _previous_month_date(today)
    company_issuer = {
        "rfc": company.rfc,
        "name": company.legal_name,
        "regime": company.tax_regime,
    }
    counterpart_issuer = {
        "rfc": counterpart.rfc,
        "name": counterpart.legal_name,
        "regime": counterpart.tax_regime,
    }
    current_date = date(today.year, today.month, min(today.day, 15))

    specs = [
        {
            "kind": "I",
            "date": current_date,
            "issuer": company_issuer,
            "receiver": counterpart_issuer,
            "subtotal": "12500.00",
            "iva": "2000.00",
            "total": "14500.00",
            "series": "ING",
            "folio": "0001",
            "method": "PUE",
            "form": "03",
            "description": "Servicios de consultoría administrativa",
            "uso": "G01",
        },
        {
            "kind": "I",
            "date": current_date,
            "issuer": company_issuer,
            "receiver": counterpart_issuer,
            "subtotal": "8600.00",
            "iva": "1376.00",
            "total": "9976.00",
            "series": "ING",
            "folio": "0002",
            "method": "PPD",
            "form": "99",
            "description": "Desarrollo de software a la medida",
            "uso": "G01",
        },
        {
            "kind": "I",
            "date": previous,
            "issuer": company_issuer,
            "receiver": counterpart_issuer,
            "subtotal": "24000.00",
            "iva": "3840.00",
            "iva_retained": "2560.00",
            "isr_retained": "300.00",
            "total": "24980.00",
            "series": "ING",
            "folio": "0003",
            "method": "PUE",
            "form": "03",
            "description": "Servicios profesionales con retenciones",
            "uso": "G01",
        },
        {
            "kind": "E",
            "date": current_date,
            "issuer": counterpart_issuer,
            "receiver": company_issuer,
            "subtotal": "3200.00",
            "iva": "512.00",
            "total": "3712.00",
            "series": "EGR",
            "folio": "0004",
            "method": "PUE",
            "form": "03",
            "description": "Renta de equipo de cómputo",
            "uso": "G03",
        },
        {
            "kind": "E",
            "date": previous,
            "issuer": counterpart_issuer,
            "receiver": company_issuer,
            "subtotal": "1800.00",
            "iva": "288.00",
            "total": "2088.00",
            "series": "EGR",
            "folio": "0005",
            "method": "PUE",
            "form": "01",
            "description": "Material de papelería y consumibles",
            "uso": "G03",
        },
    ]

    files = []
    for index, spec in enumerate(specs, start=1):
        uuid_value = uuid5(
            NAMESPACE_URL,
            f"https://demo.local/cfdi/{company.rfc}/{index}",
        )
        fecha = f"{spec['date'].isoformat()}T10:30:00"
        content = _build_xml(
            uuid_value=uuid_value,
            fecha=fecha,
            cfdi_type=spec["kind"],
            issuer=spec["issuer"],
            receiver=spec["receiver"],
            subtotal=spec["subtotal"],
            iva=spec["iva"],
            total=spec["total"],
            series=spec["series"],
            folio=spec["folio"],
            payment_method=spec["method"],
            payment_form=spec["form"],
            iva_retained=spec.get("iva_retained", "0.00"),
            isr_retained=spec.get("isr_retained", "0.00"),
            description=spec["description"],
            uso_cfdi=spec["uso"],
        )
        filename = (
            f"DEMO_{company.rfc}_{spec['series']}_"
            f"{spec['folio']}.xml"
        )
        files.append((filename, content))
    return files
