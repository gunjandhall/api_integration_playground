# API Integration Playground

A mini Postman-style web app with a secure backend relay.

Users provide:
- API endpoint URL
- HTTP method
- headers (JSON textarea)
- body text

The app returns:
- status code
- latency
- response headers
- formatted response body
- clear error output

## Why this is a strong Partner Engineer demo

It shows practical integration engineering skills:
- fast developer onboarding with a browser UI
- CORS-friendly backend relay design
- secure request guardrails (SSRF mitigation)
- useful debugging output for real API integration work

## Safety checks included

- Only `http` / `https` URLs allowed
- Only common methods allowed (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`)
- Blocks localhost/private/link-local/reserved IP ranges
- DNS resolution check before outbound call
- Upstream timeout
- Max response size cap (default 1 MB)

## Quickstart

1. Install deps:

```bash
pip install -r requirements.txt
```

2. Run app:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

3. Open:
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`

## API

- `GET /`
  - Serves playground UI
- `POST /api/proxy-request`
  - Relays outbound request with validation + safety checks
  - Input JSON:
    - `method`: string
    - `url`: string
    - `headers`: object
    - `body`: string

## Config (optional)

- `REQUEST_TIMEOUT_SECONDS` (default `10`)
- `MAX_RESPONSE_BYTES` (default `1048576`)

## Setup

- Run command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Optional secrets:
  - `REQUEST_TIMEOUT_SECONDS`
  - `MAX_RESPONSE_BYTES`
