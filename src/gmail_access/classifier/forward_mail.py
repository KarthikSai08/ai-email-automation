import base64
from email.message import EmailMessage
# pyrefly: ignore [missing-import]
from googleapiclient.errors import HttpError
from ..read_mail import download_attachment


def forward_email(
    service,
    email,
    destination,
    department
):

    message = EmailMessage()

    message["To"] = destination

    message["Subject"] = (
        f"[{department} Department] "
        f"{email['subject']}"
    )

    message["X-Email-Automation"] = (
        "EmailAutomation"
    )

    body = f"""
Department: {department}

Original Sender:
{email['from']}

Original Subject:
{email['subject']}

Original Date:
{email['date']}

----------------------------------------

{email['body']}
"""

    message.set_content(
        body
    )

    # Add original attachments
    for attachment in email.get(
        "attachments",
        []
    ):

        attachment_id = attachment.get(
            "attachment_id"
        )

        if not attachment_id:
            continue

        data = download_attachment(
            service,
            email["id"],
            attachment_id
        )

        filename = attachment[
            "filename"
        ]

        mime_type = attachment[
            "mime_type"
        ]

        if "/" in mime_type:

            maintype, subtype = (
                mime_type.split(
                    "/",
                    1
                )
            )

        else:

            maintype = "application"
            subtype = "octet-stream"

        message.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=filename
        )

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    result = (
        service.users()
        .messages()
        .send(
            userId="me",
            body={
                "raw": encoded_message
            }
        )
        .execute()
    )

    return result