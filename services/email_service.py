import os
import requests
from services.logging_service import LoggingService


class EmailService:

    def __init__(self):
        self.api_key = os.getenv("MAILGUN_API_KEY")
        self.domain = os.getenv("MAILGUN_DOMAIN")
        self.teacher_email = os.getenv("TEACHER_EMAIL")

        self.from_email = os.getenv("MAILGUN_FROM") or (
            f"CurioNest <postmaster@{self.domain}>"
        )

        self.logger = LoggingService()

    def send_escalation(self, subject, body):

        # ✅ Configuration validation (CRITICAL for Render)
        if not self.api_key or not self.domain or not self.teacher_email:
            self.logger.log("MAILGUN_CONFIG_ERROR", {
                "api_key_present": bool(self.api_key),
                "domain_present": bool(self.domain),
                "teacher_email_present": bool(self.teacher_email)
            })
            return

        self.logger.log("EMAIL_DISPATCH_ATTEMPT", {
            "subject": subject,
            "recipient": self.teacher_email
        })

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

            # ✅ Deterministic response logging
            self.logger.log("MAILGUN_STATUS", response.status_code)
            self.logger.log("MAILGUN_RESPONSE", response.text)

            # ✅ Failure classification (VERY IMPORTANT)
            if response.status_code != 200:
                self.logger.log("MAILGUN_NON_SUCCESS", {
                    "status": response.status_code,
                    "response": response.text
                })

        except requests.exceptions.Timeout:
            self.logger.log("MAILGUN_TIMEOUT", "Request timed out")

        except requests.exceptions.ConnectionError:
            self.logger.log("MAILGUN_CONNECTION_ERROR", "Network failure")

        except Exception as e:
            self.logger.log("MAILGUN_EXCEPTION", str(e))
