import httpx
from fastapi.testclient import TestClient

from app import main


class DummyResponse:
    def __init__(self, status_code: int, headers: dict[str, str], chunks: list[bytes]):
        self.status_code = status_code
        self.headers = headers
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class DummyClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def stream(self, method, url, headers, content):
        body = b'{"message":"ok"}'
        return DummyResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            chunks=[body],
        )


class TimeoutClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def stream(self, method, url, headers, content):
        raise httpx.TimeoutException("timed out")


def test_homepage_renders():
    client = TestClient(main.app)
    response = client.get("/")
    assert response.status_code == 200
    assert "API Integration Playground" in response.text


def test_proxy_rejects_invalid_method():
    client = TestClient(main.app)
    response = client.post(
        "/api/proxy-request",
        json={
            "method": "TRACE",
            "url": "https://example.com",
            "headers": {},
            "body": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported HTTP method"


def test_proxy_rejects_localhost():
    client = TestClient(main.app)
    response = client.post(
        "/api/proxy-request",
        json={
            "method": "GET",
            "url": "http://127.0.0.1:8000",
            "headers": {},
            "body": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Blocked IP range"


def test_proxy_success(monkeypatch):
    monkeypatch.setattr(
        main,
        "httpx",
        type(
            "HttpxModule",
            (),
            {
                "AsyncClient": DummyClient,
                "TimeoutException": httpx.TimeoutException,
                "RequestError": httpx.RequestError,
            },
        ),
    )
    monkeypatch.setattr(main, "_resolve_and_validate_host", lambda _: None)

    client = TestClient(main.app)
    response = client.post(
        "/api/proxy-request",
        json={
            "method": "GET",
            "url": "https://example.com",
            "headers": {"x-test": "1"},
            "body": "",
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["status_code"] == 200
    assert payload["response_json"]["message"] == "ok"


def test_proxy_timeout(monkeypatch):
    monkeypatch.setattr(
        main,
        "httpx",
        type(
            "HttpxModule",
            (),
            {
                "AsyncClient": TimeoutClient,
                "TimeoutException": httpx.TimeoutException,
                "RequestError": httpx.RequestError,
            },
        ),
    )
    monkeypatch.setattr(main, "_resolve_and_validate_host", lambda _: None)

    client = TestClient(main.app)
    response = client.post(
        "/api/proxy-request",
        json={
            "method": "GET",
            "url": "https://example.com",
            "headers": {},
            "body": "",
        },
    )
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error"] == "Upstream timeout"
