# config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

# --- Load .env file (if present) ---
BASE_DIR = Path(__file__).resolve().parent
dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)

# --- Helpers ---
def _get_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "on")

def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default

# ======================================================
# Flask core
# ======================================================
SECRET_KEY  = os.getenv("FLASK_SECRET", "dev_secret")
FLASK_ENV   = os.getenv("FLASK_ENV", "production")
FLASK_DEBUG = _get_bool("FLASK_DEBUG", False)

# Provide conventional flags
DEBUG   = FLASK_DEBUG
TESTING = _get_bool("FLASK_TESTING", False)

# ======================================================
# Session / Cookie settings
# ======================================================
# Effective only if you set session.permanent = True in your blueprints (you do).
PERMANENT_SESSION_LIFETIME   = timedelta(days=_get_int("PERMANENT_SESSION_DAYS", 7))
REMEMBER_COOKIE_DURATION     = timedelta(days=_get_int("REMEMBER_COOKIE_DAYS", 7))
SESSION_REFRESH_EACH_REQUEST = _get_bool("SESSION_REFRESH_EACH_REQUEST", True)

SESSION_COOKIE_NAME    = os.getenv("SESSION_COOKIE_NAME", "tourist_session")
SESSION_COOKIE_SECURE  = _get_bool("SESSION_COOKIE_SECURE", False)      # True in HTTPS prod
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")   # 'Lax' is fine for same-site
SESSION_COOKIE_DOMAIN  = os.getenv("SESSION_COOKIE_DOMAIN") or None     # Set if using subdomains

# ======================================================
# Uploads
# ======================================================
UPLOAD_FOLDER      = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_CONTENT_LENGTH = 4 * 1024 * 1024  # 4 MB

# ======================================================
# Database
# ======================================================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "tourist_transport")

# If you set DATABASE_URL (e.g. from Railway/Render/Heroku), it overrides the pieces above
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
else:
    SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

SQLALCHEMY_TRACK_MODIFICATIONS = False

# ======================================================
# Socket.IO
# ======================================================
ENABLE_SOCKETIO = _get_bool("ENABLE_SOCKETIO", True)

# For multi-process or Docker setups, set a message queue (like Redis):
# .env example: SOCKETIO_MESSAGE_QUEUE=redis://localhost:6379/0
SOCKETIO_MESSAGE_QUEUE = os.getenv("SOCKETIO_MESSAGE_QUEUE") or None

# ======================================================
# Server binding defaults (can be read by app.py or flask run)
# ======================================================
HOST = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
PORT = _get_int("FLASK_RUN_PORT", 5000)

# ======================================================
# Auth policy for your current DB contents
# ======================================================.
PLAINTEXT_PASSWORDS = _get_bool("PLAINTEXT_PASSWORDS", True)
ALLOW_ADMIN_PLAINTEXT_SET = _get_bool("ALLOW_ADMIN_PLAINTEXT_SET", True)

# --- Third-party keys / feature flags ---
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "AIzaSyCNIGJvxyt270FnAKekyDx0VjAZqOMrDB4")

# ======================================================
# Email (Mailgun)
# ======================================================

# ▶️ Feature flag: set to True only when you actually want to send emails
EMAIL_ENABLED = _get_bool("EMAIL_ENABLED", True)

EMAIL_PROVIDER = "MAILGUN"

MAIL_FROM_EMAIL = os.getenv("MAIL_FROM_EMAIL", "mymcaproject2025@gmail.com")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "Tourist Transport")

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN  = os.getenv("MAILGUN_DOMAIN")
MAILGUN_BASE_URL = os.getenv("MAILGUN_BASE_URL", "https://api.mailgun.net")

# Only require keys if email sending is enabled
if EMAIL_ENABLED:
    if not MAILGUN_API_KEY:
        raise RuntimeError("MAILGUN_API_KEY missing. Set it in .env or disable email by EMAIL_ENABLED=false")
    if not MAILGUN_DOMAIN:
        raise RuntimeError("MAILGUN_DOMAIN missing. Set it in .env or disable email by EMAIL_ENABLED=false")


