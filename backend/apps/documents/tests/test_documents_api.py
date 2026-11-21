from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounting.models import FiscalPeriod
from apps.accounting.services import close_period, get_or_create_period
from apps.authentication.models import CompanyMembership
from apps.documents.models import Document
from apps.documents.tests.utils import build_cfdi_xml


pytestmark = pytest.mark.django_db

DOCUMENTS_URL = "/api/v1/documents/"
BULK_URL = "/api/v1/documents/bulk-upload/"
MANUAL_URL = "/api/v1/documents/manual/"
PERIODS_URL = "/api/v1/periods/"

XML_MIME = "application/xml"
PDF_MIME = "application/pdf"
PDF_CONTENT = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def headers(company):
    return {"HTTP_X_COMPANY_ID": str(company.id)}


def xml_file(name, content):
    return SimpleUploadedFile(name, content, content_type=XML_MIME)


def pdf_file(name, content=PDF_CONTENT):
    return SimpleUploadedFile(name, content, content_type=PDF_MIME)


def upload_xml(client, company, name, content, **extra):
    data = {"files": [xml_file(name, content)]}
    data.update(extra)
    return client.post(
        BULK_URL,
        data,
        format="multipart",
        **headers(company),
    )


def issued_xml(company, counterpart, **overrides):
    data = {
        "issuer_rfc": company.rfc,
        "issuer_name": company.legal_name,
        "receiver_rfc": counterpart.rfc,
        "receiver_name": counterpart.legal_name,
        "uuid_value": str(uuid4()),
    }
    data.update(overrides)
    return build_cfdi_xml(**data)


def received_xml(company, counterpart, **overrides):
    data = {
        "cfdi_type": "E",
        "issuer_rfc": counterpart.rfc,
        "issuer_name": counterpart.legal_name,
        "receiver_rfc": company.rfc,
        "receiver_name": company.legal_name,
        "uuid_value": str(uuid4()),
    }
    data.update(overrides)
    return build_cfdi_xml(**data)


def test_bulk_upload_creates_document_and_returns_processed_item(
    tenant_user, make_company
):
    user, company, _membership, client = tenant_user()
    counterpart = make_company()

    response = upload_xml(
        client,
        company,
        "factura.xml",
        issued_xml(company, counterpart),
    )

    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data["summary"] == {
        "total_received": 1,
        "processed_count": 1,
        "failed_count": 0,
    }
    assert data["processed"][0]["direction"] == "ISSUED"
    assert data["processed"][0]["total"] == "1160.00"
    assert data["failed"] == []

    document = Document.objects.get(company=company)
    assert document.uploaded_by == user
    assert document.cfdi_type == "I"
    assert document.cfdi_version == "4.0"
    assert document.original_filename == "factura.xml"
    assert document.sat_status == Document.SatStatus.UNVERIFIED
    assert document.xml_file.name.startswith(
        f"companies/{company.pk}/documents/2026/05/"
    )
    assert document.xml_file.name.endswith(".xml")
    assert "factura" not in document.xml_file.name


def test_bulk_upload_infers_received_direction(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()

    response = client.post(
        BULK_URL,
        {"files": [xml_file("gasto.xml", received_xml(company, counterpart))]},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    item = response.json()["data"]["processed"][0]
    assert item["direction"] == "RECEIVED"


def test_bulk_upload_respects_explicit_direction(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()
    content = issued_xml(company, counterpart)

    response = upload_xml(
        client,
        company,
        "factura.xml",
        content,
        direction="RECEIVED",
    )

    assert response.status_code == 200
    assert response.json()["data"]["processed"][0]["direction"] == "RECEIVED"
    assert Document.objects.get(company=company).direction == "RECEIVED"


def test_duplicate_cfdi_uuid_is_reported_per_file(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()
    content = issued_xml(company, counterpart)

    first = upload_xml(client, company, "factura.xml", content)
    second = upload_xml(client, company, "factura-copia.xml", content)

    assert first.status_code == 200
    assert second.status_code == 200
    data = second.json()["data"]
    assert data["summary"]["processed_count"] == 0
    assert data["summary"]["failed_count"] == 1
    assert data["failed"][0]["code"] == "duplicate_cfdi_uuid"
    assert data["failed"][0]["message"] == (
        "El UUID ya se encuentra registrado en esta empresa."
    )
    assert Document.objects.filter(company=company).count() == 1


def test_rfc_mismatch_is_rejected(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    foreign_a = make_company()
    foreign_b = make_company()

    response = upload_xml(
        client,
        company,
        "ajena.xml",
        issued_xml(foreign_a, foreign_b),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["processed_count"] == 0
    assert data["failed"][0]["code"] == "rfc_mismatch"
    assert Document.objects.filter(company=company).count() == 0


def test_period_closed_is_rejected(tenant_user, make_company):
    user, company, _membership, client = tenant_user()
    counterpart = make_company()
    period = get_or_create_period(company, date(2026, 5, 1))
    close_period(period, user=user)

    response = upload_xml(
        client,
        company,
        "mayo.xml",
        issued_xml(company, counterpart, fecha="2026-05-10T09:00:00"),
    )

    assert response.status_code == 200
    failure = response.json()["data"]["failed"][0]
    assert failure["code"] == "period_closed"
    assert "2026-05" in failure["message"]
    assert Document.objects.filter(company=company).count() == 0


def test_partial_batch_processes_eight_and_reports_two_failures(
    tenant_user, make_company
):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()
    duplicate_content = issued_xml(company, counterpart)
    upload_xml(client, company, "duplicada.xml", duplicate_content)

    files = [
        xml_file(f"ok-{index}.xml", issued_xml(company, counterpart))
        for index in range(8)
    ]
    files.append(xml_file("duplicada.xml", duplicate_content))
    files.append(
        xml_file(
            "rfc-ajeno.xml",
            build_cfdi_xml(
                issuer_rfc="XAXX010101000",
                receiver_rfc="XEXX010101000",
                uuid_value=str(uuid4()),
            ),
        )
    )

    response = client.post(
        BULK_URL,
        {"files": files},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"] == {
        "total_received": 10,
        "processed_count": 8,
        "failed_count": 2,
    }
    codes = {item["code"] for item in data["failed"]}
    assert codes == {"duplicate_cfdi_uuid", "rfc_mismatch"}
    assert Document.objects.filter(company=company).count() == 9
    assert "8 comprobantes importados" in response.json()["message"]


def test_pdf_with_same_stem_is_attached_to_xml(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()

    response = client.post(
        BULK_URL,
        {
            "files": [
                xml_file("factura.xml", issued_xml(company, counterpart)),
                pdf_file("factura.pdf"),
            ]
        },
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["processed_count"] == 1
    document = Document.objects.get(company=company)
    assert document.pdf_file
    serializer_data = client.get(
        DOCUMENTS_URL, **headers(company)
    ).json()["data"]["results"][0]
    assert serializer_data["pdf_url"] == (
        f"/api/v1/documents/{document.pk}/download/?file=pdf"
    )


def test_orphan_pdf_is_reported(tenant_user):
    _user, company, _membership, client = tenant_user()

    response = client.post(
        BULK_URL,
        {"files": [pdf_file("solo.pdf")]},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["processed_count"] == 0
    assert data["failed"][0]["code"] == "orphan_pdf"


def test_invalid_file_type_and_size_are_reported(
    tenant_user, settings
):
    _user, company, _membership, client = tenant_user()
    settings.DOCUMENT_XML_MAX_SIZE = 20

    response = client.post(
        BULK_URL,
        {
            "files": [
                SimpleUploadedFile(
                    "nota.txt",
                    b"texto",
                    content_type="text/plain",
                ),
                xml_file("grande.xml", b"<xml>" + b"a" * 50 + b"</xml>"),
            ]
        },
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    codes = {item["code"] for item in response.json()["data"]["failed"]}
    assert codes == {"invalid_file_type", "file_too_large"}


def test_bulk_upload_rejects_more_than_fifty_files(tenant_user):
    _user, company, _membership, client = tenant_user()
    files = [xml_file(f"{index}.xml", b"<x/>") for index in range(51)]

    response = client.post(
        BULK_URL,
        {"files": files},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "files"


@pytest.mark.parametrize(
    "role,expected_status",
    [
        (CompanyMembership.Role.PARTNER, 200),
        (CompanyMembership.Role.ACCOUNTANT, 200),
        (CompanyMembership.Role.CLIENT, 200),
        (CompanyMembership.Role.AUDITOR, 403),
    ],
)
def test_bulk_upload_role_matrix(role, expected_status, tenant_user, make_company):
    _user, company, _membership, client = tenant_user(role=role)
    counterpart = make_company()

    response = upload_xml(
        client,
        company,
        "factura.xml",
        issued_xml(company, counterpart),
    )

    assert response.status_code == expected_status


def test_client_can_upload_but_cannot_delete(tenant_user, make_company):
    _user, company, _membership, client = tenant_user(
        role=CompanyMembership.Role.CLIENT
    )
    counterpart = make_company()
    response = upload_xml(
        client,
        company,
        "factura.xml",
        issued_xml(company, counterpart),
    )
    assert response.status_code == 200
    document = Document.objects.get(company=company)

    delete_response = client.delete(
        f"{DOCUMENTS_URL}{document.pk}/",
        **headers(company),
    )

    assert delete_response.status_code == 403
    assert Document.objects.filter(pk=document.pk).exists()


def test_partner_can_delete_non_accounted_document(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()
    upload_xml(client, company, "factura.xml", issued_xml(company, counterpart))
    document = Document.objects.get(company=company)

    response = client.delete(
        f"{DOCUMENTS_URL}{document.pk}/",
        **headers(company),
    )

    assert response.status_code == 204
    assert not Document.objects.filter(pk=document.pk).exists()


def test_accounted_document_cannot_be_deleted(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()
    upload_xml(client, company, "factura.xml", issued_xml(company, counterpart))
    document = Document.objects.get(company=company)
    document.is_accounted = True
    document.save(update_fields=["is_accounted"])

    response = client.delete(
        f"{DOCUMENTS_URL}{document.pk}/",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "document_accounted"


def test_document_in_closed_period_cannot_be_deleted(
    tenant_user, make_company
):
    user, company, _membership, client = tenant_user()
    counterpart = make_company()
    upload_xml(client, company, "factura.xml", issued_xml(company, counterpart))
    document = Document.objects.get(company=company)
    close_period(document.fiscal_period, user=user)

    response = client.delete(
        f"{DOCUMENTS_URL}{document.pk}/",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "period_closed"


def test_list_filters_and_search(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()
    upload_xml(
        client,
        company,
        "ingreso.xml",
        issued_xml(company, counterpart, issuer_name="Proveedor Alfa"),
    )
    upload_xml(
        client,
        company,
        "egreso.xml",
        received_xml(
            company,
            counterpart,
            issuer_name="Distribuidora Beta",
            fecha="2026-06-10T09:00:00",
        ),
    )

    by_direction = client.get(
        DOCUMENTS_URL,
        {"direction": "RECEIVED"},
        **headers(company),
    ).json()["data"]
    assert by_direction["count"] == 1
    assert by_direction["results"][0]["issuer_name"] == "Distribuidora Beta"

    by_search = client.get(
        DOCUMENTS_URL,
        {"search": "Beta"},
        **headers(company),
    ).json()["data"]
    assert by_search["count"] == 1

    by_type = client.get(
        DOCUMENTS_URL,
        {"cfdi_type": "I"},
        **headers(company),
    ).json()["data"]
    assert by_type["count"] == 1
    assert by_type["results"][0]["total"] == "1160.00"
    assert by_type["results"][0]["subtotal"] == "1000.00"
    assert by_type["results"][0]["xml_url"].endswith("?file=xml")

    by_uuid = client.get(
        DOCUMENTS_URL,
        {"search": by_type["results"][0]["uuid"]},
        **headers(company),
    ).json()["data"]
    assert by_uuid["count"] == 1


def test_fiscal_period_serializer_counts_unaccounted_documents(
    tenant_user, make_company
):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()
    upload_xml(client, company, "factura.xml", issued_xml(company, counterpart))

    response = client.get(PERIODS_URL, **headers(company))

    assert response.status_code == 200
    period = response.json()["data"]["results"][0]
    assert period["unaccounted_documents_count"] == 1


def test_manual_document_requires_and_stores_pdf(tenant_user):
    _user, company, _membership, client = tenant_user()

    response = client.post(
        MANUAL_URL,
        {
            "pdf_file": pdf_file("nota.pdf"),
            "issue_date": "2026-05-15T10:00:00-06:00",
            "direction": "RECEIVED",
            "issuer_rfc": "XAXX010101000",
            "issuer_name": "Proveedor sin CFDI",
            "subtotal": "500.00",
            "iva_transferred": "80.00",
            "total": "580.00",
        },
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["cfdi_type"] == "M"
    assert data["uuid"] is None
    assert data["pdf_url"].endswith("?file=pdf")
    document = Document.objects.get(company=company)
    assert document.cfdi_type == Document.CfdiType.MANUAL
    assert document.receiver_rfc == company.rfc
    assert document.pdf_file.name.endswith(".pdf")


def test_manual_document_rejects_invalid_pdf_signature(tenant_user):
    _user, company, _membership, client = tenant_user()

    response = client.post(
        MANUAL_URL,
        {
            "pdf_file": pdf_file("nota.pdf", b"not a pdf"),
            "issue_date": "2026-05-15T10:00:00-06:00",
            "direction": "RECEIVED",
            "issuer_rfc": "XAXX010101000",
            "issuer_name": "Proveedor sin CFDI",
            "subtotal": "500.00",
            "iva_transferred": "80.00",
            "total": "580.00",
        },
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "pdf_file"
    assert "PDF" in response.json()["errors"][0]["message"]


def test_attach_pdf_to_existing_document(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()
    upload_xml(client, company, "factura.xml", issued_xml(company, counterpart))
    document = Document.objects.get(company=company)

    response = client.post(
        f"{DOCUMENTS_URL}{document.pk}/pdf/",
        {"pdf_file": pdf_file("respaldo.pdf")},
        format="multipart",
        **headers(company),
    )

    assert response.status_code == 200
    document.refresh_from_db()
    assert document.pdf_file
    assert response.json()["data"]["pdf_url"].endswith("?file=pdf")


def test_download_own_document_and_foreign_document_returns_404(
    tenant_user, make_company
):
    user, company, _membership, client = tenant_user()
    counterpart = make_company()
    upload_xml(client, company, "factura.xml", issued_xml(company, counterpart))
    own_document = Document.objects.get(company=company)

    own = client.get(
        f"{DOCUMENTS_URL}{own_document.pk}/download/",
        {"file": "xml"},
        **headers(company),
    )
    assert own.status_code == 200
    assert own["Content-Type"] == "application/xml"
    assert b"<cfdi:Comprobante" in b"".join(own.streaming_content)

    foreign_company = make_company()
    foreign_period = get_or_create_period(foreign_company, date(2026, 5, 1))
    foreign_document = Document.objects.create(
        company=foreign_company,
        fiscal_period=foreign_period,
        uuid=uuid4(),
        direction=Document.Direction.ISSUED,
        cfdi_type=Document.CfdiType.INGRESO,
        issue_date=own_document.issue_date,
        issuer_rfc=foreign_company.rfc,
        issuer_name=foreign_company.legal_name,
        receiver_rfc=company.rfc,
        receiver_name=company.legal_name,
        uploaded_by=user,
    )
    foreign_document.xml_file.save(
        "foreign.xml",
        ContentFile(issued_xml(foreign_company, counterpart)),
        save=True,
    )

    response = client.get(
        f"{DOCUMENTS_URL}{foreign_document.pk}/download/",
        {"file": "xml"},
        **headers(company),
    )

    assert response.status_code == 404


def test_download_without_file_parameter_returns_400(tenant_user, make_company):
    _user, company, _membership, client = tenant_user()
    counterpart = make_company()
    upload_xml(client, company, "factura.xml", issued_xml(company, counterpart))
    document = Document.objects.get(company=company)

    response = client.get(
        f"{DOCUMENTS_URL}{document.pk}/download/",
        **headers(company),
    )

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "file"
