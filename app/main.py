from __future__ import annotations
import ipaddress
import json
import socket
import time
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import settings

app = FastAPI(title=settings.app_name)
ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}


class ProxyRequest(BaseModel):
    method: str = Field(default="GET")
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_and_validate_host(hostname: str) -> None:
    normalized = hostname.strip().lower()
    if normalized in BLOCKED_HOSTS:
        raise HTTPException(status_code=400, detail="Blocked host")

    try:
        direct_ip = ipaddress.ip_address(normalized)
        if _is_disallowed_ip(direct_ip):
            raise HTTPException(status_code=400, detail="Blocked IP range")
        return
    except ValueError:
        pass

    try:
        records = socket.getaddrinfo(normalized, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="Unable to resolve host") from exc

    for record in records:
        resolved = ipaddress.ip_address(record[4][0])
        if _is_disallowed_ip(resolved):
            raise HTTPException(status_code=400, detail="Blocked IP range")


def _parse_and_validate_url(raw_url: str) -> str:
    parsed = urlsplit(raw_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="URL must include a hostname")
    _resolve_and_validate_host(parsed.hostname)
    return parsed.geturl()


def _normalize_method(method: str) -> str:
    method_name = method.upper().strip()
    if method_name not in ALLOWED_METHODS:
        raise HTTPException(status_code=400, detail="Unsupported HTTP method")
    return method_name


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    disallowed = {"host", "content-length", "connection"}
    clean_headers = {}
    for key, value in headers.items():
        if key.lower() in disallowed:
            continue
        clean_headers[str(key)] = str(value)
    return clean_headers


def _format_response_body(content_type: str, body: bytes) -> tuple[str, dict | None]:
    body_text = body.decode("utf-8", errors="replace")
    if "application/json" in content_type.lower():
        try:
            parsed = json.loads(body_text)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=True)
            return pretty, parsed
        except json.JSONDecodeError:
            return body_text, None
    return body_text, None


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return f"""
    <html>
      <head>
        <title>{settings.app_name}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            padding: 24px;
            background: #f8fafc;
            color: #0f172a;
          }}
          h1 {{ margin-top: 0; }}
          .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
          }}
          .card {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 16px;
          }}
          label {{
            display: block;
            margin-top: 10px;
            font-size: 14px;
            font-weight: 600;
          }}
          input, select, textarea {{
            width: 100%;
            margin-top: 6px;
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 10px;
            box-sizing: border-box;
            font-family: ui-monospace, Menlo, Monaco, "Courier New", monospace;
          }}
          textarea {{ min-height: 120px; }}
          button {{
            margin-top: 12px;
            border: 0;
            border-radius: 8px;
            background: #0f172a;
            color: #fff;
            padding: 10px 14px;
            cursor: pointer;
          }}
          pre {{
            background: #0f172a;
            color: #e2e8f0;
            border-radius: 8px;
            padding: 12px;
            min-height: 300px;
            overflow: auto;
            margin: 0;
          }}
          .meta {{
            font-size: 13px;
            color: #334155;
            margin: 8px 0 12px;
          }}
          @media (max-width: 960px) {{
            .grid {{ grid-template-columns: 1fr; }}
          }}
        </style>
      </head>
      <body>
        <h1>{settings.app_name}</h1>
        <p class="meta">Mini Postman-style playground with backend relay and safety checks.</p>
        <div class="grid">
          <section class="card">
            <label>Method</label>
            <select id="method">
              <option>GET</option>
              <option>POST</option>
              <option>PUT</option>
              <option>PATCH</option>
              <option>DELETE</option>
            </select>
            <label>URL</label>
            <input id="url" placeholder="https://api.example.com/resource" />
            <label>Headers (JSON)</label>
            <textarea id="headers">{{}}</textarea>
            <label>Body (raw text)</label>
            <textarea id="body"></textarea>
            <button id="send-btn">Send Request</button>
          </section>
          <section class="card">
            <div class="meta" id="meta">No request yet.</div>
            <pre id="response-output"></pre>
          </section>
        </div>
        <script>
          const sendBtn = document.getElementById("send-btn");
          const output = document.getElementById("response-output");
          const meta = document.getElementById("meta");
          sendBtn.addEventListener("click", async () => {{
            output.textContent = "Loading...";
            meta.textContent = "Sending request...";
            let headersObj = {{}};
            try {{
              const rawHeaders = document.getElementById("headers").value.trim();
              headersObj = rawHeaders ? JSON.parse(rawHeaders) : {{}};
            }} catch (err) {{
              meta.textContent = "Header parse error";
              output.textContent = "Headers must be valid JSON.";
              return;
            }}

            const payload = {{
              method: document.getElementById("method").value,
              url: document.getElementById("url").value,
              headers: headersObj,
              body: document.getElementById("body").value
            }};

            try {{
              const resp = await fetch("/api/proxy-request", {{
                method: "POST",
                headers: {{"Content-Type": "application/json"}},
                body: JSON.stringify(payload)
              }});
              const data = await resp.json();
              meta.textContent = `Status: ${{resp.status}} | Latency: ${{data.latency_ms ?? "n/a"}} ms`;
              output.textContent = JSON.stringify(data, null, 2);
            }} catch (err) {{
              meta.textContent = "Request failed";
              output.textContent = err.toString();
            }}
          }});
        </script>
      </body>
    </html>
    """


@app.post("/api/proxy-request")
async def proxy_request(payload: ProxyRequest) -> dict:
    method = _normalize_method(payload.method)
    target_url = _parse_and_validate_url(payload.url)
    headers = _sanitize_headers(payload.headers)
    request_body = payload.body.encode("utf-8")

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=False,
        ) as client:
            async with client.stream(
                method,
                target_url,
                headers=headers,
                content=request_body,
            ) as response:
                chunks = []
                total_size = 0
                async for chunk in response.aiter_bytes():
                    total_size += len(chunk)
                    if total_size > settings.max_response_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail="Response too large",
                        )
                    chunks.append(chunk)
                raw_body = b"".join(chunks)
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                content_type = response.headers.get("content-type", "text/plain")
                formatted_body, parsed_json = _format_response_body(content_type, raw_body)

                return {
                    "ok": True,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "target_url": target_url,
                    "method": method,
                    "response_headers": dict(response.headers),
                    "response_body": formatted_body,
                    "response_json": parsed_json,
                }
    except httpx.TimeoutException:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "error": "Upstream timeout",
        }
    except httpx.RequestError as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "error": f"Upstream request failed: {str(exc)}",
        }
