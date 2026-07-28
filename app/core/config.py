from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/library"

    KEYCLOAK_URL: str = "http://localhost:8080"
    KEYCLOAK_PUBLIC_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "library"
    KEYCLOAK_CLIENT_ID: str = "library-backend"
    KEYCLOAK_CLIENT_SECRET: str = "library-backend-secret"

    FINE_PER_DAY: int = 5000
    DEFAULT_BORROW_DAYS: int = 14

    KEYCLOAK_ROLE_ID_ADMIN: str = ""
    KEYCLOAK_ROLE_ID_LIBRARIAN: str = ""
    KEYCLOAK_ROLE_ID_READER: str = ""

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def keycloak_role_ids(self) -> dict[str, str]:
        return {
            "admin": self.KEYCLOAK_ROLE_ID_ADMIN,
            "librarian": self.KEYCLOAK_ROLE_ID_LIBRARIAN,
            "reader": self.KEYCLOAK_ROLE_ID_READER,
        }

    @property
    def keycloak_issuer_candidates(self) -> list[str]:
        """Các issuer hợp lệ có thể xuất hiện trong token, tùy nơi Keycloak
        được gọi (nội bộ Docker hay từ ngoài trình duyệt)."""
        realm_path = f"/realms/{self.KEYCLOAK_REALM}"
        return [
            f"{self.KEYCLOAK_URL.rstrip('/')}{realm_path}",
            f"{self.KEYCLOAK_PUBLIC_URL.rstrip('/')}{realm_path}",
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
