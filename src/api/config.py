from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "auth.db"))

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.example.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

SMS_API_URL = os.getenv("SMS_API_URL", "")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
FRONT_PASSWORD = os.getenv("FRONT_PASSWORD", "")
