import resend
import os
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.getenv("RESEND_API_PASSWORD")

params: resend.Emails.SendParams = {
    "from": "Acme <noreply@kantikoala.app>",
    "to": ["aryananand.chess@gmail.com"],
    "subject": "hello world",
    "html": "<strong>it works!</strong>",
}

email = resend.Emails.send(params)
print(email)