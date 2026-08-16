from pydantic import BaseModel, Field


class ClassifyRequest(BaseModel):

    subject: str
    body: str = ""


class ClassifyResponse(BaseModel):

    predicted_department: str
    department: str
    confidence: float
    below_threshold: bool


class ForwardRequest(BaseModel):

    from_: str = Field(alias="from")
    subject: str
    body: str = ""
    date: str = ""
    department: str = ""
    destination: str = ""

    model_config = {"populate_by_name": True}


class ForwardResponse(BaseModel):

    message_id: str
    thread_id: str


class EmailResponse(BaseModel):

    id: str
    thread_id: str
    from_: str = Field(alias="from")
    subject: str
    date: str
    body: str
    automation_header: str
    attachments: list[dict]

    model_config = {"populate_by_name": True}


class EmailClassifyResponse(EmailResponse):

    predicted_department: str
    department: str
    confidence: float
    below_threshold: bool


class StatsResponse(BaseModel):

    history_id: str | None
    processed_count: int
