import smtplib
from email.mime.text import MIMEText
import httpx
from ..config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMS_API_URL, SMS_API_KEY


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print("SMTP not configured; skipping email")
        return False
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    try:
        s = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_USER, [to_email], msg.as_string())
        s.quit()
        return True
    except Exception as e:
        print("Email send error:", e)
        return False


def send_sms(phone_number: str, message: str) -> bool:
    if not SMS_API_URL or not SMS_API_KEY:
        print("SMS API not configured; skipping SMS")
        return False
    try:
        with httpx.Client() as client:
            resp = client.post(SMS_API_URL, json={"to": phone_number, "message": message, "api_key": SMS_API_KEY}, timeout=10)
            return resp.status_code == 200
    except Exception as e:
        print("SMS send error:", e)
        return False
