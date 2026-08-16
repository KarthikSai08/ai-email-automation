import os

from dotenv import load_dotenv
from fastapi import FastAPI

from .routes import router

load_dotenv()

app = FastAPI(
    title="Email Automation API",
    description=(
        "Classify and forward Gmail messages using the fine-tuned "
        "DeBERTa model, and inspect listener state."
    ),
    version="0.1.0",
)

app.include_router(router)


def run():

    import uvicorn

    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))

    uvicorn.run(
        "gmail_access.api.main:app",
        host=host,
        port=port,
    )
