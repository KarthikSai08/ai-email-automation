import json
import os
import sys
import threading

from dotenv import load_dotenv
from google.cloud import pubsub_v1

from .classifier.classifier import classify_email
from .classifier.forward_mail import forward_email
from .classifier.mail_config import DEFAULT_DEPARTMENT, DEFAULT_EMAIL, DEPARTMENTS
from .config import HISTORY_FILE, PROCESSED_FILE
from .read_mail import get_email, get_gmail_service

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-project-id")
SUBSCRIPTION_ID = os.getenv("PUBSUB_SUBSCRIPTION_ID", "your-subscription-id")


def get_last_history_id():

    if HISTORY_FILE.exists():
        return HISTORY_FILE.read_text().strip()

    return None


def save_history_id(history_id):

    HISTORY_FILE.write_text(str(history_id))


def get_processed_messages():

    if not PROCESSED_FILE.exists():
        return set()

    with open(PROCESSED_FILE) as file:
        return {line.strip() for line in file if line.strip()}


def save_processed_message(message_id):

    with open(PROCESSED_FILE, "a") as file:
        file.write(message_id + "\n")


def get_new_messages(service, start_history_id):

    messages = set()

    page_token = None

    while True:
        response = (
            service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
                pageToken=page_token,
            )
            .execute()
        )

        for history in response.get("history", []):
            for item in history.get("messagesAdded", []):
                message_id = item["message"]["id"]

                messages.add(message_id)

        page_token = response.get("nextPageToken")

        if not page_token:
            break

    return messages


def process_email(service, message_id):

    email = get_email(service, message_id)

    # Messages sent by this automation (carry the X-Email-Automation
    # header) must never be re-classified or forwarded again, otherwise
    # the listener loops on its own forwarded emails forever.
    if email["automation_header"]:
        print("Skipping: message was sent by the automation itself.")

        return

    print()
    print("========================================")
    print("NEW EMAIL")
    print("========================================")
    print("From    :", email["from"])
    print("Subject :", email["subject"])
    print("Body    :", email["body"][:500])
    print("========================================")

    department = classify_email(email["subject"], email["body"])

    print("Classification:", department)

    department_email = DEPARTMENTS.get(department, DEFAULT_EMAIL)

    if department == DEFAULT_DEPARTMENT:
        print("Unknown department. Sending to default address.")

    print("Forwarding to:", department_email)

    result = forward_email(service, email, department_email, department)

    print("Forwarded successfully:", result["id"])


def process_notification(service, notification_history_id, lock):

    with lock:
        previous_history_id = get_last_history_id()

        print()
        print("Notification History ID:", notification_history_id)

        print("Previous History ID:", previous_history_id)

        # First notification after starting the listener.
        if previous_history_id is None:
            save_history_id(notification_history_id)

            print("Initial history ID saved.")

            return

        # Ignore old/duplicate notifications.
        if int(notification_history_id) <= int(previous_history_id):
            print("Old/duplicate notification ignored.")

            return

        message_ids = get_new_messages(service, previous_history_id)

        print("Messages found:", len(message_ids))

        processed_messages = get_processed_messages()

        for message_id in message_ids:
            if message_id in processed_messages:
                print("Already processed:", message_id)

                continue

            process_email(service, message_id)

            save_processed_message(message_id)

            print("Processed:", message_id)

        save_history_id(notification_history_id)

        print("Saved History ID:", notification_history_id)


def main():

    gmail_service = get_gmail_service()

    subscriber = pubsub_v1.SubscriberClient()

    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    lock = threading.Lock()

    def callback(message):

        try:
            data = message.data.decode("utf-8")

            notification = json.loads(data)

            history_id = notification["historyId"]

            process_notification(gmail_service, history_id, lock)

            message.ack()

        except Exception as error:
            print()
            print("ERROR:", error)

            message.nack()

    print("Waiting for new Gmail emails...")

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)

    try:
        streaming_pull_future.result()

    except KeyboardInterrupt:
        print("\nStopping listener...")

        streaming_pull_future.cancel()

        try:
            streaming_pull_future.result(timeout=5)
        except Exception:  # noqa: S110 - cancel timeout is expected on shutdown
            pass

        subscriber.close()

        print("Listener stopped.")


if __name__ == "__main__":
    main()
