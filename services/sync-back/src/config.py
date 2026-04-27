"""Settings from environment variables."""
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://agents:changeme@postgres:5432/corporate_agents")
STAGING_PATH = os.environ.get("STAGING_PATH", "/data/staging")
ARCHIVE_PATH = os.environ.get("ARCHIVE_PATH", "/data/archive")
MIRROR_PATH = os.environ.get("MIRROR_PATH", "/data/mirror")
EMAIL_NOTIFIER_URL = os.environ.get("EMAIL_NOTIFIER_URL", "http://email-notifier:3005")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
