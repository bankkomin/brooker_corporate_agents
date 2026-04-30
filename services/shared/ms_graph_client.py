"""Microsoft Graph API client wrapper for email and SharePoint access."""
import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@dataclass
class GraphConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    user_email: str = "support.brookstorybook@brookergroup.com"


class MSGraphClient:
    """Async Microsoft Graph API client."""

    def __init__(self, config: GraphConfig):
        self.config = config
        self._token: str | None = None
        self._token_expires: float = 0

    async def _ensure_token(self):
        """Get or refresh OAuth2 token."""
        import time
        if self._token and time.time() < self._token_expires - 60:
            return

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{self.config.tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expires = time.time() + data.get("expires_in", 3600)

    async def _request(self, method: str, path: str, **kwargs) -> dict | list | bytes:
        await self._ensure_token()
        url = f"{GRAPH_BASE}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()

            if resp.headers.get("content-type", "").startswith("application/json"):
                data = resp.json()
                return data.get("value", data)
            return resp.content

    # --- Email methods ---

    async def get_messages(self, folder: str = "Inbox", **params) -> list:
        query = "&".join(f"${k}={v}" for k, v in params.items())
        path = f"/users/{self.config.user_email}/mailFolders/{folder}/messages"
        if query:
            path += f"?{query}"
        return await self._request("GET", path)

    async def get_attachments(self, message_id: str) -> list:
        return await self._request(
            "GET", f"/users/{self.config.user_email}/messages/{message_id}/attachments"
        )

    async def mark_as_read(self, message_id: str):
        await self._request(
            "PATCH",
            f"/users/{self.config.user_email}/messages/{message_id}",
            json={"isRead": True},
        )

    # --- SharePoint/OneDrive methods ---

    async def list_site_drive_items(self, site_id: str, folder_path: str) -> list:
        path = f"/sites/{site_id}/drive/root:/{folder_path}:/children"
        return await self._request("GET", path)

    async def list_drive_items(self, drive_id: str, folder_path: str) -> list:
        path = f"/drives/{drive_id}/root:/{folder_path}:/children"
        return await self._request("GET", path)

    async def download_file(self, item_id: str) -> bytes:
        return await self._request("GET", f"/drives/items/{item_id}/content")
