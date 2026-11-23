# Sistema contable multi-tenant (México)

Monorepo del MVP contable: Django 5 + Django REST Framework + PostgreSQL 16 en
el backend y Vue 3 + Pinia + Tailwind en el frontend.

## Estructura

```text
backend/
  config/settings/{base,local,production}.py
  apps/{core,authentication,tenants,accounting,documents,reconciliation}/
  requirements/{base,local,production}.txt
frontend/
docs/
```

## Puesta en marcha (Docker)

```bash
cp .env.example .env
docker compose up --build
```

La API queda disponible en `http://localhost:8000/api/v1/`.
La interfaz queda disponible en `http://localhost:5173/`; Vite proxya `/api`
hacia el servicio `backend` dentro de la red de Docker Compose.

## Puesta en marcha local

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/local.txt
export DB_HOST=localhost
python manage.py migrate
python manage.py runserver
```

Frontend (Vite proxya `/api` a `http://localhost:8000`):

```bash
cd frontend
npm install
npm run dev
```

## Verificación

```bash
curl http://localhost:8000/api/v1/health/
```
Respuesta esperada:

```json
{
  "success": true,
  "message": "Consulta exitosa.",
  "data": { "status": "ok" },
  "errors": null
}
```

## Tests

Con PostgreSQL levantado (`docker compose up -d db`):

```bash
cd backend
source .venv/bin/activate
pytest
```

Frontend:

```bash
cd frontend
npm test
```

## Variables de entorno

Consulta `.env.example`. En producción usa
`DJANGO_SETTINGS_MODULE=config.settings.production` y define
`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` y
`CSRF_TRUSTED_ORIGINS` con valores reales.
