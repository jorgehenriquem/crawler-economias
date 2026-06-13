import os
from pathlib import Path

PORTAL_URL = "https://portal.minhaseconomias.com.br"
API_URL = "https://api.minhaseconomias.com.br"

LOGIN_URL = f"{PORTAL_URL}/login"
SESSION_ALIVE_URL = f"{API_URL}/api/authentication/v2/session/alive"
TRANSACTIONS_URL = f"{API_URL}/financial-core/v2/transactions"

COOKIES_FILE = Path(os.environ.get("ME_COOKIES_FILE", "~/.config/me-crawler/cookies.json")).expanduser()
OUTPUT_DIR   = Path(os.environ.get("ME_OUTPUT_DIR", "output")).expanduser()

STATUSES = "[CONFIRMED, PENDING]"
DEFAULT_PAGE_SIZE = 100
DEFAULT_SYNC_DAYS = 30
LOGIN_TIMEOUT_MS = 120_000
REQUEST_TIMEOUT = 30

MONGO_URI = os.environ.get("ME_MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("ME_MONGO_DB", "minhas_economias")
