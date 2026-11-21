import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.documents.validators import (
    DocumentFileValidationError,
    validate_document_upload,
    validate_filename,
    validate_pdf_upload,
    validate_xml_upload,
)


def xml_upload(name="factura.xml", content=b"<cfdi:Comprobante/>", mime="application/xml"):
    return SimpleUploadedFile(name, content, content_type=mime)


def pdf_upload(name="respaldo.pdf", content=b"%PDF-1.7\n%%EOF\n", mime="application/pdf"):
    return SimpleUploadedFile(name, content, content_type=mime)


@pytest.mark.parametrize(
    "filename",
    ["../factura.xml", "..\\factura.xml", "carpeta/factura.xml", "a\\b.pdf"],
)
def test_validate_filename_rejects_path_separators(filename):
    with pytest.raises(DocumentFileValidationError) as exc_info:
        validate_filename(filename)

    assert exc_info.value.code == "invalid_file_type"


def test_validate_filename_rejects_null_byte():
    with pytest.raises(DocumentFileValidationError) as exc_info:
        validate_filename("factura\x00.xml")

    assert exc_info.value.code == "invalid_file_type"


def test_xml_validator_accepts_text_xml_mime():
    validate_xml_upload(xml_upload(mime="text/xml"))


def test_xml_validator_rejects_wrong_mime_and_extension():
    with pytest.raises(DocumentFileValidationError) as mime_error:
        validate_xml_upload(xml_upload(mime="application/pdf"))
    assert mime_error.value.code == "invalid_file_type"

    with pytest.raises(DocumentFileValidationError) as extension_error:
        validate_xml_upload(xml_upload(name="factura.txt"))
    assert extension_error.value.code == "invalid_file_type"


def test_xml_size_limit(settings):
    settings.DOCUMENT_XML_MAX_SIZE = 10

    with pytest.raises(DocumentFileValidationError) as exc_info:
        validate_xml_upload(xml_upload(content=b"<xml>123456</xml>"))

    assert exc_info.value.code == "file_too_large"


def test_pdf_validator_accepts_valid_signature():
    validate_pdf_upload(pdf_upload())


def test_pdf_validator_rejects_missing_signature():
    with pytest.raises(DocumentFileValidationError) as exc_info:
        validate_pdf_upload(pdf_upload(content=b"plain text"))

    assert exc_info.value.code == "invalid_file_type"
    assert "%PDF-" in exc_info.value.message


def test_pdf_size_limit(settings):
    settings.DOCUMENT_PDF_MAX_SIZE = 10

    with pytest.raises(DocumentFileValidationError) as exc_info:
        validate_pdf_upload(pdf_upload(content=b"%PDF-1.7 more than ten bytes"))

    assert exc_info.value.code == "file_too_large"


def test_validate_document_upload_dispatches_by_extension():
    assert validate_document_upload(xml_upload()) == "xml"
    assert validate_document_upload(pdf_upload()) == "pdf"

    with pytest.raises(DocumentFileValidationError):
        validate_document_upload(
            SimpleUploadedFile("nota.txt", b"x", content_type="text/plain")
        )
