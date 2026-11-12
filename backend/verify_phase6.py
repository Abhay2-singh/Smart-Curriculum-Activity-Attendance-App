"""Verify production configuration and sanitized health responses without external services."""

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.database import get_db
from app.main import app


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify_production_settings() -> None:
    valid = Settings(
        APP_ENV="production",
        JWT_SECRET_KEY="test-secret-" + "x" * 40,
        ALLOWED_ORIGINS="https://portal.example.edu",
    )
    require(valid.allowed_origins_list == ["https://portal.example.edu"], "Allowed origin parsing failed")

    for values, expected_error in (
        (
            {"APP_ENV": "production", "JWT_SECRET_KEY": "", "ALLOWED_ORIGINS": "https://portal.example.edu"},
            "JWT_SECRET_KEY",
        ),
        (
            {"APP_ENV": "production", "JWT_SECRET_KEY": "short", "ALLOWED_ORIGINS": "https://portal.example.edu"},
            "32 characters",
        ),
        (
            {"APP_ENV": "production", "JWT_SECRET_KEY": "x" * 40, "ALLOWED_ORIGINS": "*"},
            "ALLOWED_ORIGINS",
        ),
    ):
        try:
            Settings(**values)
        except ValidationError as exc:
            require(expected_error in str(exc), f"Unexpected configuration failure: {exc}")
        else:
            raise AssertionError(f"Unsafe production configuration was accepted: {expected_error}")


class HealthySession:
    def execute(self, _statement):
        return 1


class BrokenSession:
    def execute(self, _statement):
        raise SQLAlchemyError("private connection detail")


def verify_health_endpoints() -> None:
    app.dependency_overrides[get_db] = lambda: HealthySession()
    try:
        with TestClient(app) as client:
            require(client.get("/api/health").status_code == 200, "Basic health endpoint failed")
            healthy = client.get("/api/health/database")
            require(
                healthy.status_code == 200 and healthy.json()["database"] == "connected",
                "Database health success response failed",
            )

            app.dependency_overrides[get_db] = lambda: BrokenSession()
            failed = client.get("/api/health/database")
            require(failed.status_code == 503, "Database failure must report HTTP 503")
            body = failed.text
            require("private connection detail" not in body, "Health endpoint exposed database internals")
            require("error_details" not in body, "Health endpoint exposed raw error details")
    finally:
        app.dependency_overrides.clear()


verify_production_settings()
verify_health_endpoints()
print("Phase 6 configuration and health security checks passed.")
