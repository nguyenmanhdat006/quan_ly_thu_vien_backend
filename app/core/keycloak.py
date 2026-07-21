import time
import uuid
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import settings


class KeycloakError(Exception):
    """Lỗi khi gọi Keycloak, kèm status code gốc để router quyết định phản hồi."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class KeycloakClient:
    """Bọc mọi tương tác với Keycloak: lấy/refresh token service account (cache
    trong memory), login/refresh/logout người dùng, và Admin REST API tạo/sửa/xóa
    user, gán role, đặt lại mật khẩu, bật/tắt tài khoản."""

    def __init__(self) -> None:
        self._base_url = settings.KEYCLOAK_URL.rstrip("/")
        self._realm = settings.KEYCLOAK_REALM
        self._client_id = settings.KEYCLOAK_CLIENT_ID
        self._client_secret = settings.KEYCLOAK_CLIENT_SECRET
        self._admin_token: str | None = None
        self._admin_token_expires_at: float = 0.0

    @property
    def _token_endpoint(self) -> str:
        return f"{self._base_url}/realms/{self._realm}/protocol/openid-connect/token"

    @property
    def _logout_endpoint(self) -> str:
        return f"{self._base_url}/realms/{self._realm}/protocol/openid-connect/logout"

    @property
    def _admin_users_endpoint(self) -> str:
        return f"{self._base_url}/admin/realms/{self._realm}/users"

    @property
    def jwks_uri(self) -> str:
        return f"{self._base_url}/realms/{self._realm}/protocol/openid-connect/certs"

    async def _get_admin_token(self) -> str:
        """Lấy access token của service account (client_credentials), cache trong
        memory và tự làm mới trước khi hết hạn 10 giây."""
        now = time.time()
        if self._admin_token and now < self._admin_token_expires_at - 10:
            return self._admin_token

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
        if resp.status_code != 200:
            raise KeycloakError(502, "Không thể xác thực với Keycloak (service account)")

        data = resp.json()
        self._admin_token = data["access_token"]
        self._admin_token_expires_at = now + data.get("expires_in", 60)
        return self._admin_token

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """Đăng nhập user bằng username/password (Direct Access Grant)."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._token_endpoint,
                data={
                    "grant_type": "password",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "username": username,
                    "password": password,
                },
            )
        if resp.status_code == 401 or resp.status_code == 400:
            raise KeycloakError(401, "Sai tên đăng nhập hoặc mật khẩu")
        if resp.status_code != 200:
            raise KeycloakError(502, "Không thể kết nối tới dịch vụ xác thực")
        return resp.json()

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        """Làm mới access token bằng refresh token."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._token_endpoint,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": refresh_token,
                },
            )
        if resp.status_code != 200:
            raise KeycloakError(401, "Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại")
        return resp.json()

    async def logout(self, refresh_token: str) -> None:
        """Thu hồi refresh token (đăng xuất)."""
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                self._logout_endpoint,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": refresh_token,
                },
            )

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        full_name: str,
        password: str,
        role: str,
    ) -> uuid.UUID:
        """Tạo user trên Keycloak + gán role realm tương ứng. Trả về keycloak_user_id.
        Raise KeycloakError(409) nếu trùng username/email.
        Nếu gán role thất bại, tự xóa user để rollback (compensating transaction)."""
        token = await self._get_admin_token()
        first_name, _, last_name = full_name.partition(" ")
        last_name = last_name or first_name

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                self._admin_users_endpoint,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "username": username,
                    "email": email,
                    "firstName": first_name,
                    "lastName": last_name,
                    "enabled": True,
                    "emailVerified": True,
                    "credentials": [
                        {"type": "password", "value": password, "temporary": False}
                    ],
                },
            )

        if resp.status_code == 409:
            raise KeycloakError(409, "Tên đăng nhập hoặc email đã tồn tại")
        if resp.status_code != 201:
            raise KeycloakError(502, f"Tạo tài khoản Keycloak thất bại: {resp.text}")

        location = resp.headers.get("Location", "")
        keycloak_user_id_str = location.rstrip("/").rsplit("/", 1)[-1]
        try:
            keycloak_user_id = uuid.UUID(keycloak_user_id_str)
        except ValueError as exc:
            raise KeycloakError(502, "Không đọc được ID người dùng từ Keycloak") from exc

        try:
            await self.assign_realm_role(keycloak_user_id, role)
        except KeycloakError:
            # Rollback: xóa user vừa tạo nếu gán role thất bại
            await self.delete_user(keycloak_user_id)
            raise

        return keycloak_user_id

    async def assign_realm_role(self, keycloak_user_id: uuid.UUID, role: str) -> None:
        """Gán realm role cho user bằng role ID cố định."""
        # Role ID mapping từ realm library
        role_ids = {
            "admin": "c1b06faa-6f54-4873-9b3a-398d455afc2b",
            "librarian": "48479d5e-550d-4b85-93c3-589d00666641",
            "reader": "d253c69c-a567-4af1-816c-499f0c4f74b0",
        }
        
        if role not in role_ids:
            raise KeycloakError(400, f"Role '{role}' không được hỗ trợ")
        
        token = await self._get_admin_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self._admin_users_endpoint}/{keycloak_user_id}/role-mappings/realm",
                headers={"Authorization": f"Bearer {token}"},
                json=[{"id": role_ids[role], "name": role}],
            )
        if resp.status_code not in (204, 201, 200):
            raise KeycloakError(502, f"Gán vai trò '{role}' trên Keycloak thất bại: {resp.text}")

    async def delete_user(self, keycloak_user_id: uuid.UUID) -> None:
        """Xóa user trên Keycloak (dùng để rollback khi tạo user thất bại)."""
        token = await self._get_admin_token()
        async with httpx.AsyncClient(timeout=10) as client:
            await client.delete(
                f"{self._admin_users_endpoint}/{keycloak_user_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

    async def set_enabled(self, keycloak_user_id: uuid.UUID, enabled: bool) -> None:
        """Bật/tắt tài khoản trên Keycloak."""
        token = await self._get_admin_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(
                f"{self._admin_users_endpoint}/{keycloak_user_id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"enabled": enabled},
            )
        if resp.status_code not in (204, 200):
            raise KeycloakError(502, "Cập nhật trạng thái tài khoản Keycloak thất bại")

    async def update_profile(
        self, keycloak_user_id: uuid.UUID, *, email: str | None = None, full_name: str | None = None
    ) -> None:
        """Cập nhật email hoặc full_name trên Keycloak."""
        token = await self._get_admin_token()
        payload: dict[str, Any] = {}
        if email is not None:
            payload["email"] = email
        if full_name is not None:
            first_name, _, last_name = full_name.partition(" ")
            payload["firstName"] = first_name
            payload["lastName"] = last_name or first_name
        if not payload:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(
                f"{self._admin_users_endpoint}/{keycloak_user_id}",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
        if resp.status_code not in (204, 200):
            raise KeycloakError(502, "Cập nhật hồ sơ Keycloak thất bại")

    async def reset_password(self, keycloak_user_id: uuid.UUID, new_password: str) -> None:
        """Đặt lại mật khẩu người dùng (yêu cầu admin)."""
        token = await self._get_admin_token()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(
                f"{self._admin_users_endpoint}/{keycloak_user_id}/reset-password",
                headers={"Authorization": f"Bearer {token}"},
                json={"type": "password", "value": new_password, "temporary": False},
            )
        if resp.status_code not in (204, 200):
            raise KeycloakError(502, "Đặt lại mật khẩu trên Keycloak thất bại")

    async def update_realm_role(self, keycloak_user_id: uuid.UUID, old_role: str, new_role: str) -> None:
        """Đổi role: gỡ role cũ, gán role mới."""
        if old_role == new_role:
            return
        token = await self._get_admin_token()
        async with httpx.AsyncClient(timeout=10) as client:
            # Gỡ role cũ
            await client.request(
                "DELETE",
                f"{self._admin_users_endpoint}/{keycloak_user_id}/role-mappings/realm",
                headers={"Authorization": f"Bearer {token}"},
                json=[{"name": old_role}],
            )
        # Gán role mới
        await self.assign_realm_role(keycloak_user_id, new_role)


keycloak_client = KeycloakClient()


def raise_from_keycloak_error(exc: KeycloakError) -> None:
    """Helper: convert KeycloakError thành HTTPException."""
    raise HTTPException(status_code=exc.status_code, detail=exc.detail)