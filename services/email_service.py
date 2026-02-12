import os
import requests
from services.logging_service import LoggingService


class EmailService:
    def __init__(self):
        self.api_key = os.getenv("MAILGUN_API_KEY")

        self.domain = os.getenv("MAILGUN_DOMAIN")
        self.from_email = os.getenv(
            "MAILGUN_FROM",
            f"CurioNest <postmaster@{self.domain}>"
        )
        self.teacher_email = os.getenv("TEACHER_EMAIL")
        self.logger = LoggingService()
    def send_escalation(self, subject, body):
        print("📧 Mailgun escalation triggered")

        try:
            response = requests.post(
                f"https://api.mailgun.net/v3/{self.domain}/messages",
                auth=("api", self.api_key),
                data={
                    "from": self.from_email,
                    "to": [self.teacher_email],
                    "subject": subject,
                    "text": body,
                },
                timeout=5
            )

            print("📨 Mailgun status:", response.status_code)
            print("📨 Mailgun response:", response.text)
            self.logger.log("MAILGUN_STATUS", str(response.status_code))
            self.logger.log("MAILGUN_RESPONSE", response.text)
 
        except Exception as e:
            print("❌ Mailgun exception:", str(e))
