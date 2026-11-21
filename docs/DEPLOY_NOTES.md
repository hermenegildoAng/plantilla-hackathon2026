# Notas de despliegue

## Archivos fiscales privados (`/media/`)

`MEDIA_ROOT` contiene XML/PDF de comprobantes fiscales y **nunca** debe servirse
directamente. El único acceso permitido es:

```text
GET /api/v1/documents/{id}/download/?file=xml|pdf
```

con `Authorization: Bearer ...` y `X-Company-ID: ...`. Ese endpoint verifica la
empresa del documento y responde `404` cuando el comprobante pertenece a otro
tenant `[E-07]`.

### Regla obligatoria de Nginx

Bloquee `/media/` antes de cualquier `location` genérica de archivos estáticos:

```nginx
# [E-07] Los comprobantes solo se descargan por la API autenticada.
location ^~ /media/ {
    deny all;
    return 404;
}

# [E-04] 50 archivos por petición: 50 PDF de 5 MB + margen multipart.
client_max_body_size 260m;
```

No configure `alias`, `root` ni `X-Accel-Redirect` hacia `MEDIA_ROOT` para el
público. Si en el futuro se usa `X-Accel-Redirect`, debe hacerse desde una
`location internal;` invocada únicamente por Django después de validar el JWT y
el tenant.

## Variables relevantes

* `MEDIA_ROOT`: volumen persistente montado en el contenedor (por defecto
  `backend/media`). En Docker Compose ya persiste porque `./backend` se monta
  en `/app`.
* `DATA_UPLOAD_MAX_NUMBER_FILES=50`.
* `DOCUMENT_XML_MAX_SIZE=2097152` (2 MB) y `DOCUMENT_PDF_MAX_SIZE=5242880`
  (5 MB); se validan además en la aplicación, no solo en Nginx.
