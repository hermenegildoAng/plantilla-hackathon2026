"""Upload validators for CFDI XML and PDF files [E-04] [E-06] [E-07].

The functions in this module raise :class:`DocumentFileValidationError` with a
stable ``code`` so the bulk upload can report per-file failures without
aborting the whole batch. Names are never trusted: null bytes, path separators
and traversal segments are rejected before the file reaches storage.
"""

import os

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError


XML_MIME_TYPES = {"application/xml", "text/xml"}
PDF_MIME_TYPES = {"application/pdf"}


class DocumentFileValidationError(DjangoValidationError):
    """A per-file upload error with a machine-readable ``code``.

    It subclasses Django's ``ValidationError`` so the functions can also be
    used as regular model/serializer validators.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message, code=code)


def _max_size(kind: str) -> int:
    if kind == "xml":
        return int(
            getattr(settings, "DOCUMENT_XML_MAX_SIZE", 2 * 1024 * 1024)
        )
    return int(getattr(settings, "DOCUMENT_PDF_MAX_SIZE", 5 * 1024 * 1024))


def _human_size(size: int) -> str:
    megabytes = size / (1024 * 1024)
    if megabytes >= 1:
        return f"{megabytes:.0f} MB"
    return f"{size} bytes"


def validate_filename(filename: str) -> str:
    """Reject unsafe names while keeping the original informative label."""
    name = str(filename or "")
    if not name.strip():
        raise DocumentFileValidationError(
            "invalid_file_type",
            "El archivo no tiene un nombre válido.",
        )
    if "\x00" in name:
        raise DocumentFileValidationError(
            "invalid_file_type",
            "El nombre del archivo contiene caracteres no permitidos.",
        )
    if "/" in name or "\\" in name:
        raise DocumentFileValidationError(
            "invalid_file_type",
            "El nombre del archivo no puede contener separadores de ruta.",
        )
    if name in {".", ".."} or ".." in name.split(os.sep):
        raise DocumentFileValidationError(
            "invalid_file_type",
            "El nombre del archivo contiene una ruta no permitida.",
        )
    return name


def validate_extension(filename: str, allowed: set[str]) -> str:
    extension = os.path.splitext(filename)[1].lower()
    if extension not in allowed:
        allowed_text = " o ".join(sorted(ext.replace(".", "").upper() for ext in allowed))
        raise DocumentFileValidationError(
            "invalid_file_type",
            f"La extensión del archivo no está permitida. Use {allowed_text}.",
        )
    return extension


def _validate_mime(uploaded_file, allowed: set[str]) -> None:
    content_type = getattr(uploaded_file, "content_type", None)
    if content_type is None:
        # Model-level validation (FieldFile) has no MIME information. Request
        # serializers always pass an UploadedFile with content_type.
        return
    content_type = str(content_type).split(";", 1)[0].strip().lower()
    if content_type not in allowed:
        raise DocumentFileValidationError(
            "invalid_file_type",
            "El tipo MIME del archivo no está permitido.",
        )


def _validate_size(uploaded_file, kind: str) -> None:
    size = getattr(uploaded_file, "size", None)
    if size is None:
        return
    limit = _max_size(kind)
    if size > limit:
        raise DocumentFileValidationError(
            "file_too_large",
            (
                "El archivo excede el tamaño máximo permitido de "
                f"{_human_size(limit)} para {kind.upper()}."
            ),
        )


def _read_head(uploaded_file, length: int) -> bytes:
    try:
        uploaded_file.seek(0)
        head = uploaded_file.read(length)
    finally:
        try:
            uploaded_file.seek(0)
        except (AttributeError, ValueError):
            pass
    if isinstance(head, str):
        return head.encode()
    return head or b""


def validate_xml_upload(uploaded_file) -> None:
    """Validate an XML upload: name, extension, MIME and size."""
    filename = validate_filename(getattr(uploaded_file, "name", ""))
    validate_extension(filename, {".xml"})
    _validate_mime(uploaded_file, XML_MIME_TYPES)
    _validate_size(uploaded_file, "xml")


def validate_pdf_upload(uploaded_file) -> None:
    """Validate a PDF upload: name, extension, MIME, size and ``%PDF-``."""
    filename = validate_filename(getattr(uploaded_file, "name", ""))
    validate_extension(filename, {".pdf"})
    _validate_mime(uploaded_file, PDF_MIME_TYPES)
    _validate_size(uploaded_file, "pdf")

    if _read_head(uploaded_file, 5) != b"%PDF-":
        raise DocumentFileValidationError(
            "invalid_file_type",
            "El archivo PDF no tiene una firma de cabecera válida (%PDF-).",
        )


def validate_document_upload(uploaded_file) -> str:
    """Validate by extension and return ``"xml"`` or ``"pdf"``."""
    filename = validate_filename(getattr(uploaded_file, "name", ""))
    extension = os.path.splitext(filename)[1].lower()
    if extension == ".xml":
        validate_xml_upload(uploaded_file)
        return "xml"
    if extension == ".pdf":
        validate_pdf_upload(uploaded_file)
        return "pdf"
    raise DocumentFileValidationError(
        "invalid_file_type",
        "El tipo de archivo no está permitido. Solo se aceptan XML y PDF.",
    )
