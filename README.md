# Finmaxxin V1 Prototype

Finmaxxin is a production-oriented prototype of a personal financial digital twin.  
It models major life decisions over a 0-5 year horizon, ranks conservative recommendations with transparent rationale, and supports explicit one-click execution flow with idempotency and decision traces.

## What is implemented

### Backend (`FastAPI`)
- `POST /v1/scenarios`: create scenario draft from user input + account snapshot provider.
- `POST /v1/scenarios/{scenario_id}/simulate`: Monte Carlo + deterministic policy-aware simulation.
- `GET /v1/scenarios/{scenario_id}/recommendations`: ranked recommendations with confidence and downside.
- `POST /v1/actions/preview`: execution preview with impact, fees, warnings, and TTL.
- `POST /v1/actions/execute`: explicit-confirm execution with idempotency protection.
- `GET /v1/decisions/{decision_id}/trace`: full explainability and policy trace.
- `GET /events`: emitted domain events for observability validation.

### Frontend (`Next.js`)
- Form-driven planner UX.
- End-to-end flow for create -> simulate -> recommendations -> preview -> execute.
- Trace viewer for explainability inspection.
- Responsive layout with mobile + desktop support.

### Local infrastructure (`Docker Compose`)
- Nginx reverse proxy, API service, web service.
- Postgres, Redis, Redpanda (event-stream placeholder for production parity).
- Redis is internal-only by default (not published to host) and requires a password.
- Published service ports are bound to `127.0.0.1` only.

## Repository structure

```text
backend/
  app/
    api/
    models/
    services/
  tests/
frontend/
docker-compose.yml
.env.example
```

## Quick start

### 1. Run with Docker Compose

```bash
docker compose up --build
```

- Public entrypoint (Nginx): `http://localhost`
- API docs: `http://localhost/docs`
- Web: `http://localhost`
- API via proxy: `http://localhost/api/*`

If you need Redis shell access, run:

```bash
docker compose exec redis redis-cli -a "$REDIS_PASSWORD"
```

### 2. Demo auth

Use:
- `Authorization: Bearer finmaxxin-demo-token`
- `X-User-Id: user-123`

The web UI is prefilled with this token.

### 3. Run backend tests

```bash
cd backend
pip install -e ".[dev]"
pytest -q
```

## Run locally without Docker

### Backend (Terminal 1)

```bash
cd backend
pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Terminal 2)

```bash
cd frontend
npm install
npm run dev
```

- Web app: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`

## API contract notes

- Currency is fixed to `CAD` in V1.
- `horizon_months` max is `60`.
- Execution requires `confirm=true` and an `idempotency_key`.
- Decision traces capture model version, policy version, input hash, feature contributions, and policy checks.

## Security and reliability in this prototype

- Bearer token validation for all protected routes.
- Scenario ownership checks (`X-User-Id` must match scenario owner).
- Idempotent execution endpoint for money-movement safety.
- Event emission for key lifecycle transitions.

## Production hardening path

- Replace in-memory store with Postgres + Redis + object storage.
- Replace deterministic account provider with real internal data adapters.
- Add queue workers for heavy simulation jobs.
- Add mTLS/service identity, KMS encryption, vault-managed secrets, and WAF.
- Add model registry, drift monitoring, and rollout gates.
