import os

from dotenv import load_dotenv

from .read_mail import get_gmail_service

load_dotenv()

TOPIC_NAME = os.getenv(
    "PUBSUB_TOPIC",
    "projects/your-project-id/topics/gmail-new-mail",
)


def start_gmail_watch():

    service = get_gmail_service()

    response = (
        service.users()
        .watch(userId="me", body={"topicName": TOPIC_NAME, "labelIds": ["INBOX"]})
        .execute()
    )

    print("Gmail watch started")
    print("History ID:", response["historyId"])
    print("Expiration:", response["expiration"])


if __name__ == "__main__":
    start_gmail_watch()