"""Email ingestion pipeline — reads committee emails and ingests attachments into RAG."""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    message_id: str
    subject: str
    sender: str
    recipients: list[str]
    body_text: str
    body_html: str
    received_at: datetime
    attachments: list[dict] = field(default_factory=list)  # [{filename, content_type, size, data}]
    thread_id: str | None = None


@dataclass
class IngestionResult:
    message_id: str
    subject: str
    body_ingested: bool
    attachments_ingested: int
    errors: list[str] = field(default_factory=list)


class EmailIngestionPipeline:
    """Reads emails from a monitored inbox and ingests content into the RAG pipeline."""

    def __init__(
        self,
        graph_client,  # Microsoft Graph API client
        rag_ingestion_url: str = "http://rag-ingestion:3004",
        vault_root: str = "/vault",
        supported_extensions: set[str] | None = None,
    ):
        self.graph_client = graph_client
        self.rag_url = rag_ingestion_url
        self.vault_root = Path(vault_root)
        self.supported_extensions = supported_extensions or {
            ".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".md",
        }

    async def fetch_unread_emails(
        self,
        folder: str = "Inbox",
        max_messages: int = 50,
    ) -> list[EmailMessage]:
        """Fetch unread emails from the monitored inbox."""
        try:
            messages = await self.graph_client.get_messages(
                folder=folder,
                filter="isRead eq false",
                top=max_messages,
                select="id,subject,from,toRecipients,body,receivedDateTime,hasAttachments,conversationId",
                orderby="receivedDateTime desc",
            )

            result = []
            for msg in messages:
                email = EmailMessage(
                    message_id=msg["id"],
                    subject=msg.get("subject", ""),
                    sender=msg.get("from", {}).get("emailAddress", {}).get("address", ""),
                    recipients=[
                        r.get("emailAddress", {}).get("address", "")
                        for r in msg.get("toRecipients", [])
                    ],
                    body_text=msg.get("body", {}).get("content", ""),
                    body_html=msg.get("body", {}).get("content", "") if msg.get("body", {}).get("contentType") == "html" else "",
                    received_at=datetime.fromisoformat(msg["receivedDateTime"].rstrip("Z")),
                    thread_id=msg.get("conversationId"),
                )

                # Fetch attachments if present
                if msg.get("hasAttachments"):
                    email.attachments = await self._fetch_attachments(msg["id"])

                result.append(email)

            return result

        except Exception as e:
            log.exception("Failed to fetch emails")
            return []

    async def _fetch_attachments(self, message_id: str) -> list[dict]:
        """Fetch attachments for a specific message."""
        try:
            attachments = await self.graph_client.get_attachments(message_id)
            result = []
            for att in attachments:
                ext = Path(att.get("name", "")).suffix.lower()
                if ext in self.supported_extensions:
                    result.append({
                        "filename": att["name"],
                        "content_type": att.get("contentType", ""),
                        "size": att.get("size", 0),
                        "data": att.get("contentBytes", ""),  # base64 encoded
                    })
                else:
                    log.info("Skipping unsupported attachment: %s", att.get("name"))
            return result
        except Exception:
            log.exception("Failed to fetch attachments for %s", message_id)
            return []

    async def ingest_email(
        self,
        email: EmailMessage,
        dept_id: str,
    ) -> IngestionResult:
        """Ingest an email's body and attachments into the RAG pipeline."""
        import httpx

        result = IngestionResult(
            message_id=email.message_id,
            subject=email.subject,
            body_ingested=False,
            attachments_ingested=0,
        )

        # 1. Ingest email body as a document
        if email.body_text.strip():
            body_content = _clean_email_body(email.body_text)
            if len(body_content) > 50:  # skip very short emails
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(
                            f"{self.rag_url}/ingest/document",
                            json={
                                "content": body_content,
                                "source": f"email:{email.sender}:{email.subject}",
                                "doc_type": "email",
                                "collection": f"{dept_id}_docs",
                                "metadata": {
                                    "subject": email.subject,
                                    "sender": email.sender,
                                    "date": email.received_at.isoformat(),
                                    "thread_id": email.thread_id,
                                },
                            },
                        )
                        if resp.status_code == 200:
                            result.body_ingested = True
                        else:
                            result.errors.append(f"Body ingest failed: HTTP {resp.status_code}")
                except Exception as e:
                    result.errors.append(f"Body ingest error: {e}")

        # 2. Save and ingest attachments
        for att in email.attachments:
            try:
                # Save to vault
                att_dir = self.vault_root / dept_id / "entities" / "email-attachments"
                att_dir.mkdir(parents=True, exist_ok=True)
                att_path = att_dir / _safe_filename(att["filename"])

                import base64
                data = base64.b64decode(att["data"])
                att_path.write_bytes(data)

                # Ingest via RAG pipeline
                async with httpx.AsyncClient(timeout=60.0) as client:
                    with open(att_path, "rb") as f:
                        resp = await client.post(
                            f"{self.rag_url}/ingest/document",
                            files={"file": (att["filename"], f, att["content_type"])},
                            data={
                                "collection": f"{dept_id}_docs",
                                "source": f"email-attachment:{email.subject}:{att['filename']}",
                            },
                        )
                    if resp.status_code == 200:
                        result.attachments_ingested += 1
                    else:
                        result.errors.append(f"Attachment {att['filename']}: HTTP {resp.status_code}")
            except Exception as e:
                result.errors.append(f"Attachment {att['filename']}: {e}")

        # 3. Mark email as read
        try:
            await self.graph_client.mark_as_read(email.message_id)
        except Exception:
            log.warning("Failed to mark email %s as read", email.message_id)

        return result

    async def run_ingestion_cycle(self, dept_mapping: dict[str, list[str]]) -> list[IngestionResult]:
        """Run a full ingestion cycle — fetch and ingest all unread emails.

        Args:
            dept_mapping: Maps sender email domains/addresses to department IDs.
                         e.g., {"finance@brooker.com": "finance", "@brooker.com": "cac"}
        """
        emails = await self.fetch_unread_emails()
        results = []

        for email in emails:
            dept_id = _resolve_department(email.sender, email.recipients, dept_mapping)
            result = await self.ingest_email(email, dept_id)
            results.append(result)
            log.info(
                "Ingested email '%s': body=%s, attachments=%d, errors=%d",
                email.subject, result.body_ingested, result.attachments_ingested, len(result.errors),
            )

        return results


def _clean_email_body(text: str) -> str:
    """Remove email signatures, reply chains, and HTML artifacts."""
    # Remove HTML tags if present
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove excessive whitespace
    text = re.sub(r"\s+", " ", text)
    # Remove common signature markers
    for marker in ["--", "Sent from", "Best regards", "Kind regards", "Thanks,"]:
        idx = text.rfind(marker)
        if idx > len(text) * 0.7:  # only if near the end
            text = text[:idx]
    # Remove reply chains
    for marker in ["From:", "-----Original Message-----", "On .+ wrote:"]:
        match = re.search(marker, text)
        if match and match.start() > len(text) * 0.5:
            text = text[:match.start()]
    return text.strip()


def _safe_filename(filename: str) -> str:
    """Sanitize filename for filesystem storage."""
    safe = re.sub(r'[^\w\s.-]', '_', filename)
    return safe[:200]  # limit length


def _resolve_department(sender: str, recipients: list[str], mapping: dict) -> str:
    """Resolve which department an email belongs to."""
    # Check exact sender match first
    if sender in mapping:
        return mapping[sender]
    # Check domain match
    domain = "@" + sender.split("@")[-1] if "@" in sender else ""
    if domain in mapping:
        return mapping[domain]
    # Check recipients
    for recip in recipients:
        if recip in mapping:
            return mapping[recip]
    return "cac"  # default
