"""Application settings.

Loaded once at import and validated eagerly: a misconfigured deployment must
fail at startup, not at the first request that happens to touch the bad value.

The production guards here are the enforcement half of the environment gating
described in docs/10_SECURITY.md. The documented promise is that the OTP stub
cannot be reached in production even by accident, and a promise that lives only
in prose is not a control.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Rejected as a JWT_SECRET in production. Matches the .env.example placeholder
# so a copied-but-unedited file cannot ship.
_PLACEHOLDER_SECRETS = {
    "change-me-this-is-a-development-placeholder-value",
    "change-me",
    "secret",
    "changeme",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Required ---------------------------------------------------------

    # No default on purpose. If this is unset we do not know whether the
    # process is a laptop or a public server, and every gate below depends on
    # knowing. Guessing "development" is the unsafe guess.
    ENVIRONMENT: Literal["development", "test", "production"]

    DATABASE_URL: str
    JWT_SECRET: str

    # --- Optional ---------------------------------------------------------

    # Absent means "run without a cache", which is a supported mode
    # (ADR-0004), not a misconfiguration.
    REDIS_URL: str | None = None

    JWT_EXPIRE_HOURS: int = Field(default=24, ge=1, le=720)

    RESTAURANT_DASHBOARD_TOKEN: str | None = None

    CORS_ORIGINS: str = ""

    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    NOMINATIM_USER_AGENT: str = (
        "MealsOnWheels/1.0 (+https://github.com/nithishkumar2022020/MealsOnWheels)"
    )
    OVERPASS_URL: str = "https://overpass-api.de/api/interpreter"

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAIL_FROM: str = "noreply@mealsonwheels.example"

    # --- Derived ----------------------------------------------------------

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def otp_stub_allowed(self) -> bool:
        """Whether the constant OTP 123456 is accepted.

        Keyed on ENVIRONMENT alone. Deliberately NOT "is an SMS provider
        configured" — a missing provider must be a 503, never a silent fallback
        to a password everybody knows (docs/05_API_SPEC.md section 3.2).
        """
        return not self.is_production

    @property
    def docs_enabled(self) -> bool:
        return not self.is_production

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # --- Validation -------------------------------------------------------

    @field_validator("DATABASE_URL")
    @classmethod
    def _require_async_driver(cls, v: str) -> str:
        # A sync URL silently blocks the event loop under load rather than
        # failing outright, which is a much harder problem to notice.
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the asyncpg driver "
                "(postgresql+asyncpg://...); got a non-async URL"
            )
        return v

    @model_validator(mode="after")
    def _enforce_production_guards(self) -> Settings:
        if not self.is_production:
            # Outside production the dashboard token still has to exist,
            # otherwise tests would pass against an endpoint that is
            # accidentally open.
            if not self.RESTAURANT_DASHBOARD_TOKEN:
                raise ValueError(
                    "RESTAURANT_DASHBOARD_TOKEN is required when " "ENVIRONMENT is not production"
                )
            return self

        problems: list[str] = []

        if len(self.JWT_SECRET) < 32:
            problems.append("JWT_SECRET must be at least 32 characters in production")
        if self.JWT_SECRET.lower() in _PLACEHOLDER_SECRETS:
            problems.append("JWT_SECRET is still the example placeholder")

        # The shared static token is a demo-grade control. Per-restaurant
        # credentials are Stage 18; until then production must not run the
        # dashboard at all rather than run it on a secret in a config file.
        if self.RESTAURANT_DASHBOARD_TOKEN:
            problems.append(
                "RESTAURANT_DASHBOARD_TOKEN must not be set in production; the "
                "shared static token is demo-only. Per-restaurant auth is "
                "Stage 18 in docs/14_BUILD_PLAN.md"
            )

        if not self.cors_origin_list:
            problems.append("CORS_ORIGINS must be set explicitly in production")
        if "*" in self.cors_origin_list:
            problems.append("CORS_ORIGINS must not include '*' in production")

        if "example.com" in self.NOMINATIM_USER_AGENT:
            # Nominatim blocks generic and placeholder user agents.
            problems.append("NOMINATIM_USER_AGENT still contains a placeholder contact")

        if problems:
            raise ValueError("Refusing to start in production:\n  - " + "\n  - ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    """Cached accessor. Tests clear this with get_settings.cache_clear()."""
    return Settings()  # type: ignore[call-arg]
