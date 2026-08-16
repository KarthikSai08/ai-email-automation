from pathlib import Path

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
)


MODEL_PATH = Path(
    r"D:\Ai_Ml_Projects\Email_Automation\models\deberta"
)

MAX_LENGTH = 256

CONFIDENCE_THRESHOLD = 0.70


tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH
)

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_PATH
)

device = torch.device("cpu")

model.to(device)
model.eval()


def get_prediction(subject, body):

    """Run the model and return (predicted_label, confidence)."""

    text = (
        f"Subject: {subject}\n\n"
        f"Body: {body}"
    )

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_LENGTH,
        padding=True,
    )

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.inference_mode():

        outputs = model(
            **inputs
        )

    probabilities = torch.softmax(
        outputs.logits,
        dim=-1
    )

    confidence, predicted_id = torch.max(
        probabilities,
        dim=-1
    )

    confidence = confidence.item()

    predicted_id = predicted_id.item()

    department = model.config.id2label[
        predicted_id
    ]

    return department, confidence


def classify_email(subject, body):

    department, confidence = get_prediction(
        subject,
        body
    )

    print(
        f"Model prediction: {department}"
    )

    print(
        f"Confidence: {confidence:.4f}"
    )

    if confidence < CONFIDENCE_THRESHOLD:

        print(
            "Confidence below threshold."
        )

        return "UNKNOWN"

    return department