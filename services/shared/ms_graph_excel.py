"""Read Microsoft Excel Online workbooks via MS Graph (app-only / client creds).

Lets agents read live Excel data from OneDrive/SharePoint instead of a local
file. Auth uses the MS_GRAPH_* client-credentials app registration (shared with
the email integration). Read-only — this module never writes workbooks.

Env:
  MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, MS_GRAPH_CLIENT_SECRET
  MS_GRAPH_SENDER_EMAIL  — default user whose OneDrive we read from

Permissions observed on the current app registration:
  - OneDrive Files: WORKS (read a user's drive items + workbook)
  - SharePoint Sites + /search: 403 (needs Sites.Read.All admin consent)

Typical use:
    from services.shared.ms_graph_excel import GraphExcel
    gx = GraphExcel.from_env()
    sheets = await gx.read_workbook_by_path("ALCO_Tracker.xlsx")  # in sender's OneDrive
    # -> {"Liquidity": [["LCR","118.5"], ...], ...}
"""
from __future__ import annotations

import base64
import os
import time
import urllib.parse

import httpx

_GRAPH = "https://graph.microsoft.com/v1.0"


class GraphExcel:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 default_user: str = "") -> None:
        self._tenant = tenant_id
        self._cid = client_id
        self._secret = client_secret
        self._default_user = default_user
        self._token = ""
        self._token_exp = 0.0

    @classmethod
    def from_env(cls) -> "GraphExcel":
        return cls(
            tenant_id=os.environ["MS_GRAPH_TENANT_ID"],
            client_id=os.environ["MS_GRAPH_CLIENT_ID"],
            client_secret=os.environ["MS_GRAPH_CLIENT_SECRET"],
            default_user=os.getenv("MS_GRAPH_SENDER_EMAIL", ""),
        )

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        resp = await client.post(
            f"https://login.microsoftonline.com/{self._tenant}/oauth2/v2.0/token",
            data={
                "client_id": self._cid,
                "client_secret": self._secret,
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        resp.raise_for_status()
        tok = resp.json()
        self._token = tok["access_token"]
        self._token_exp = time.time() + int(tok.get("expires_in", 3600))
        return self._token

    async def _get(self, client: httpx.AsyncClient, path: str) -> dict:
        token = await self._get_token(client)
        r = await client.get(f"{_GRAPH}{path}", headers={"Authorization": f"Bearer {token}"})
        r.raise_for_status()
        return r.json()

    def _drive_root(self, user: str | None) -> str:
        u = user or self._default_user
        if not u:
            raise ValueError("no user given and MS_GRAPH_SENDER_EMAIL unset")
        return f"/users/{urllib.parse.quote(u)}/drive"

    async def list_children(self, folder: str = "root", user: str | None = None) -> list[dict]:
        """List files/folders in a OneDrive folder ('root' or 'root:/sub/path:')."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            seg = folder if folder == "root" else folder
            data = await self._get(client, f"{self._drive_root(user)}/{seg}/children"
                                            "?$select=name,file,folder,size,lastModifiedDateTime&$top=100")
            return data.get("value", [])

    async def list_worksheets(self, path: str, user: str | None = None) -> list[str]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            p = urllib.parse.quote(path)
            data = await self._get(client, f"{self._drive_root(user)}/root:/{p}:/workbook/worksheets?$select=name")
            return [w["name"] for w in data.get("value", [])]

    @staticmethod
    def _share_id(share_url: str) -> str:
        """Encode a sharing URL into a Graph shares id (u!<base64url>)."""
        b64 = base64.urlsafe_b64encode(share_url.encode()).decode().rstrip("=")
        return "u!" + b64

    async def read_workbook_by_share_url(self, share_url: str,
                                         sheet: str | None = None) -> dict[str, list[list]]:
        """Read a workbook from a SharePoint/OneDrive sharing link.

        Resolves the link → driveId+itemId → workbook usedRange. Works with the
        app's Files permission; no Sites.Read.All needed.
        Returns {sheet_name: [[cell,...], ...]}.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            sid = self._share_id(share_url)
            item = await self._get(client, f"/shares/{sid}/driveItem?$select=id,name,parentReference")
            drive_id = item["parentReference"]["driveId"]
            item_id = item["id"]
            base = f"/drives/{drive_id}/items/{item_id}/workbook"
            if sheet:
                names = [sheet]
            else:
                ws = await self._get(client, f"{base}/worksheets?$select=name")
                names = [w["name"] for w in ws.get("value", [])]
            out: dict[str, list[list]] = {}
            for name in names:
                ur = await self._get(
                    client,
                    f"{base}/worksheets/{urllib.parse.quote(name)}/usedRange(valuesOnly=true)?$select=values",
                )
                out[name] = ur.get("values", []) or []
            return out

    async def read_workbook_by_path(self, path: str, user: str | None = None,
                                    sheet: str | None = None) -> dict[str, list[list]]:
        """Read a workbook's used range. Returns {sheet_name: [[cell,...], ...]}.

        path: OneDrive-relative path, e.g. "ALCO_Tracker.xlsx" or "Treasury/ALCO.xlsx".
        sheet: read only this sheet if given, else all sheets.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            base = f"{self._drive_root(user)}/root:/{urllib.parse.quote(path)}:/workbook"
            if sheet:
                names = [sheet]
            else:
                ws = await self._get(client, f"{base}/worksheets?$select=name")
                names = [w["name"] for w in ws.get("value", [])]
            out: dict[str, list[list]] = {}
            for name in names:
                ur = await self._get(
                    client,
                    f"{base}/worksheets/{urllib.parse.quote(name)}/usedRange(valuesOnly=true)?$select=values",
                )
                out[name] = ur.get("values", []) or []
            return out
