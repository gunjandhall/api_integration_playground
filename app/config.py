import os


class Settings:
    app_name: str = "API Integration Playground"
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10"))
    max_response_bytes: int = int(os.getenv("MAX_RESPONSE_BYTES", "1048576"))


settings = Settings()
