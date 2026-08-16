import base64
import os
import re

from .config import CREDENTIALS_FILE, TOKEN_FILE

# pyrefly: ignore [missing-import]
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]


def get_gmail_service():

    creds = None

    token_file = TOKEN_FILE
    credentials_file = CREDENTIALS_FILE

    if os.path.exists(token_file):

        creds = Credentials.from_authorized_user_file(
            token_file,
            SCOPES
        )

    if not creds or not creds.valid:

        if creds and creds.expired and creds.refresh_token:

            creds.refresh(
                Request()
            )

        else:

            from google_auth_oauthlib.flow import (
                InstalledAppFlow
            )

            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file,
                SCOPES
            )

            creds = flow.run_local_server(
                port=0
            )

        with open(
            token_file,
            "w"
        ) as token:

            token.write(
                creds.to_json()
            )

    return build(
        "gmail",
        "v1",
        credentials=creds
    )


def decode_body(data):

    if not data:
        return ""

    padding = "=" * (
        -len(data) % 4
    )

    return base64.urlsafe_b64decode(
        data + padding
    ).decode(
        "utf-8",
        errors="replace"
    )


def get_header(headers, name):

    for header in headers:

        if header["name"].lower() == name.lower():

            return header["value"]

    return ""


def get_email(service, message_id):

    message = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full"
        )
        .execute()
    )

    payload = message.get(
        "payload",
        {}
    )

    headers = payload.get(
        "headers",
        []
    )

    email_from = get_header(
        headers,
        "From"
    )

    subject = get_header(
        headers,
        "Subject"
    )

    date = get_header(
        headers,
        "Date"
    )

    automation_header = get_header(
        headers,
        "X-Email-Automation"
    )

    body_parts = []

    attachments = []


    def process_part(part):

        mime_type = part.get(
            "mimeType",
            ""
        )

        filename = part.get(
            "filename",
            ""
        )

        body = part.get(
            "body",
            {}
        )

        data = body.get(
            "data"
        )

        attachment_id = body.get(
            "attachmentId"
        )


        # Attachment
        if filename:

            attachments.append(
                {
                    "filename": filename,
                    "mime_type": mime_type,
                    "attachment_id": attachment_id,
                    "size": body.get(
                        "size",
                        0
                    )
                }
            )


        # Plain text body
        elif mime_type == "text/plain" and data:

            body_parts.append(
                decode_body(data)
            )


        # HTML body
        elif mime_type == "text/html" and data:

            html = decode_body(
                data
            )

            # Only use HTML if plain text
            # wasn't already found.
            if not body_parts:

                text = re.sub(
                    r"<[^>]+>",
                    " ",
                    html
                )

                text = re.sub(
                    r"\s+",
                    " ",
                    text
                )

                body_parts.append(
                    text.strip()
                )


        # Process nested MIME parts
        for child in part.get(
            "parts",
            []
        ):

            process_part(child)


    process_part(payload)


    body = "\n".join(
        body_parts
    ).strip()


    return {
        "id": message.get(
            "id"
        ),

        "thread_id": message.get(
            "threadId"
        ),

        "from": email_from,

        "subject": subject,

        "date": date,

        "body": body,

        "attachments": attachments,

        "label_ids": message.get(
            "labelIds",
            []
        ),

        "automation_header": automation_header
    }


def download_attachment(
    service,
    message_id,
    attachment_id
):

    attachment = (
        service.users()
        .messages()
        .attachments()
        .get(
            userId="me",
            messageId=message_id,
            id=attachment_id
        )
        .execute()
    )

    data = attachment.get(
        "data",
        ""
    )

    padding = "=" * (
        -len(data) % 4
    )

    return base64.urlsafe_b64decode(
        data + padding
    )


if __name__ == "__main__":

    service = get_gmail_service()

    print(
        "Gmail authentication successful."
    )