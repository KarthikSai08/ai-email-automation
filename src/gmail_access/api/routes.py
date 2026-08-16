from functools import lru_cache

from fastapi import APIRouter, HTTPException

from ..classifier.classifier import (
    CONFIDENCE_THRESHOLD,
    classify_email,
    get_prediction,
)
from ..classifier.forward_mail import forward_email
from ..classifier.mail_config import (
    DEFAULT_DEPARTMENT,
    DEFAULT_EMAIL,
    DEPARTMENTS,
)
from ..config import HISTORY_FILE, PROCESSED_FILE
from ..read_mail import get_email, get_gmail_service
from .schemas import (
    ClassifyRequest,
    ClassifyResponse,
    EmailClassifyResponse,
    ForwardRequest,
    ForwardResponse,
    StatsResponse,
)

router = APIRouter()


@lru_cache
def gmail_service():

    return get_gmail_service()


@router.get("/health")
def health():

    try:

        profile = (
            gmail_service()
            .users()
            .getProfile(userId="me")
            .execute()
        )

    except Exception as error:  # noqa: BLE001 - surface any auth/API failure

        raise HTTPException(
            status_code=503,
            detail=f"Gmail API unavailable: {error}",
        ) from error

    return {
        "status": "ok",
        "email": profile.get("emailAddress"),
        "model": "loaded",
    }


@router.post("/classify", response_model=ClassifyResponse)
def classify(request: ClassifyRequest):

    predicted, confidence = get_prediction(
        request.subject,
        request.body,
    )

    below_threshold = confidence < CONFIDENCE_THRESHOLD

    return ClassifyResponse(
        predicted_department=predicted,
        department="UNKNOWN" if below_threshold else predicted,
        confidence=confidence,
        below_threshold=below_threshold,
    )


@router.post("/forward", response_model=ForwardResponse)
def forward(request: ForwardRequest):

    department = request.department or DEFAULT_DEPARTMENT

    destination = (
        request.destination
        or DEPARTMENTS.get(department)
        or DEFAULT_EMAIL
    )

    if not destination:

        raise HTTPException(
            status_code=400,
            detail=(
                "No destination address: provide 'destination', configure "
                f"DEPARTMENT_{department}, or set DEFAULT_EMAIL."
            ),
        )

    email = {
        "from": request.from_,
        "subject": request.subject,
        "date": request.date,
        "body": request.body,
        "attachments": [],
        "id": None,
    }

    result = forward_email(
        gmail_service(),
        email,
        destination,
        department,
    )

    return ForwardResponse(
        message_id=result["id"],
        thread_id=result.get("threadId", ""),
    )


@router.post("/emails/{message_id}/classify", response_model=EmailClassifyResponse)
def classify_message(message_id: str):

    email = get_email(
        gmail_service(),
        message_id,
    )

    predicted, confidence = get_prediction(
        email["subject"],
        email["body"],
    )

    below_threshold = confidence < CONFIDENCE_THRESHOLD

    return EmailClassifyResponse(
        **email,
        predicted_department=predicted,
        department="UNKNOWN" if below_threshold else predicted,
        confidence=confidence,
        below_threshold=below_threshold,
    )


@router.post("/emails/{message_id}/forward", response_model=ForwardResponse)
def forward_message(message_id: str):

    service = gmail_service()

    email = get_email(
        service,
        message_id,
    )

    if email["automation_header"]:

        raise HTTPException(
            status_code=400,
            detail="Message was sent by the automation itself; refusing to forward.",
        )

    department = classify_email(
        email["subject"],
        email["body"],
    )

    destination = DEPARTMENTS.get(
        department,
        DEFAULT_EMAIL,
    )

    if not destination:

        raise HTTPException(
            status_code=400,
            detail=(
                f"No destination address configured for {department} "
                "and no DEFAULT_EMAIL set."
            ),
        )

    result = forward_email(
        service,
        email,
        destination,
        department,
    )

    return ForwardResponse(
        message_id=result["id"],
        thread_id=result.get("threadId", ""),
    )


@router.get("/stats", response_model=StatsResponse)
def stats():

    history_id = (
        HISTORY_FILE.read_text().strip()
        if HISTORY_FILE.exists()
        else None
    )

    processed_count = (
        len(PROCESSED_FILE.read_text().splitlines())
        if PROCESSED_FILE.exists()
        else 0
    )

    return StatsResponse(
        history_id=history_id,
        processed_count=processed_count,
    )
