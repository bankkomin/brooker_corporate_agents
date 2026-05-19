"""SharePoint/OneDrive connector — syncs documents from SharePoint folders to the RAG pipeline."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class SharePointFile:
    file_id: str
    name: str
    path: str
    size: int
    modified_at: datetime
    content_hash: str
    download_url: str


@dataclass
class SyncResult:
    folder_path: str
    dept_id: str
    files_checked: int
    files_new: int
    files_updated: int
    files_skipped: int
    errors: list[str] = field(default_factory=list)


class SharePointConnector:
    """Syncs documents from SharePoint/OneDrive to the local vault and RAG pipeline."""

    def __init__(
        self,
        graph_client,
        site_id: str | None = None,  # SharePoint site ID
        drive_id: str | None = None,  # OneDrive drive ID
        vault_root: str = "/vault",
        hash_store_path: str = "/app/data/sharepoint_hashes.json",
    ):
        self.graph_client = graph_client
        self.site_id = site_id
        self.drive_id = drive_id
        self.vault_root = Path(vault_root)
        self.hash_store_path = Path(hash_store_path)
        self._hashes = self._load_hashes()

    def _load_hashes(self) -> dict:
        """Load file hash store for incremental sync."""
        import json
        if self.hash_store_path.exists():
            return json.loads(self.hash_store_path.read_text())
        return {}

    def _save_hashes(self):
        import json
        self.hash_store_path.parent.mkdir(parents=True, exist_ok=True)
        self.hash_store_path.write_text(json.dumps(self._hashes, indent=2))

    async def list_folder(self, folder_path: str) -> list[SharePointFile]:
        """List files in a SharePoint/OneDrive folder."""
        try:
            if self.site_id:
                items = await self.graph_client.list_site_drive_items(
                    self.site_id, folder_path
                )
            elif self.drive_id:
                items = await self.graph_client.list_drive_items(
                    self.drive_id, folder_path
                )
            else:
                log.error("No site_id or drive_id configured")
                return []

            files = []
            for item in items:
                if "file" not in item:  # skip folders
                    continue
                files.append(SharePointFile(
                    file_id=item["id"],
                    name=item["name"],
                    path=f"{folder_path}/{item['name']}",
                    size=item.get("size", 0),
                    modified_at=datetime.fromisoformat(
                        item.get("lastModifiedDateTime", "").rstrip("Z")
                    ),
                    content_hash=item.get("file", {}).get("hashes", {}).get("sha256Hash", ""),
                    download_url=item.get("@microsoft.graph.downloadUrl", ""),
                ))
            return files

        except Exception:
            log.exception("Failed to list SharePoint folder: %s", folder_path)
            return []

    async def sync_folder(
        self,
        folder_path: str,
        dept_id: str,
        rag_ingestion_url: str = "http://rag-ingestion:3004",
    ) -> SyncResult:
        """Incrementally sync a SharePoint folder to the vault and RAG pipeline."""
        import httpx

        result = SyncResult(
            folder_path=folder_path,
            dept_id=dept_id,
            files_checked=0,
            files_new=0,
            files_updated=0,
            files_skipped=0,
        )

        files = await self.list_folder(folder_path)
        result.files_checked = len(files)

        local_dir = self.vault_root / dept_id / "entities" / "sharepoint"
        local_dir.mkdir(parents=True, exist_ok=True)

        for sp_file in files:
            try:
                # Check if file has changed
                stored_hash = self._hashes.get(sp_file.file_id)
                current_hash = sp_file.content_hash or sp_file.modified_at.isoformat()

                if stored_hash == current_hash:
                    result.files_skipped += 1
                    continue

                is_new = stored_hash is None

                # Download file
                data = await self._download_file(sp_file)
                if data is None:
                    result.errors.append(f"Download failed: {sp_file.name}")
                    continue

                # Save to vault
                local_path = local_dir / sp_file.name
                local_path.write_bytes(data)

                # Ingest into RAG
                async with httpx.AsyncClient(timeout=60.0) as client:
                    with open(local_path, "rb") as f:
                        resp = await client.post(
                            f"{rag_ingestion_url}/ingest/document",
                            files={"file": (sp_file.name, f)},
                            data={
                                "collection": f"{dept_id}_docs",
                                "source": f"sharepoint:{folder_path}/{sp_file.name}",
                            },
                        )
                    if resp.status_code != 200:
                        result.errors.append(f"Ingest failed for {sp_file.name}: HTTP {resp.status_code}")

                # Update hash store
                self._hashes[sp_file.file_id] = current_hash

                if is_new:
                    result.files_new += 1
                else:
                    result.files_updated += 1

            except Exception as e:
                result.errors.append(f"{sp_file.name}: {e}")
                log.exception("Failed to sync %s", sp_file.name)

        self._save_hashes()

        log.info(
            "SharePoint sync %s → %s: %d checked, %d new, %d updated, %d skipped, %d errors",
            folder_path, dept_id, result.files_checked, result.files_new,
            result.files_updated, result.files_skipped, len(result.errors),
        )

        return result

    async def _download_file(self, sp_file: SharePointFile) -> bytes | None:
        """Download file content from SharePoint."""
        import httpx

        if sp_file.download_url:
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.get(sp_file.download_url)
                    resp.raise_for_status()
                    return resp.content
            except Exception:
                log.exception("Download failed for %s", sp_file.name)

        # Fallback: use Graph API content endpoint
        try:
            return await self.graph_client.download_file(sp_file.file_id)
        except Exception:
            log.exception("Graph API download failed for %s", sp_file.name)

        return None
