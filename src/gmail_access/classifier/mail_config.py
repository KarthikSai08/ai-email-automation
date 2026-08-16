import os

from dotenv import load_dotenv

load_dotenv()

DEPARTMENTS = {
    department: address
    for department in [
        "HR",
        "STORE",
        "DELIVERY",
        "CRM",
        "FINANCE",
        "PURCHASE",
        "RECYCLE",
        "SALES",
        "SPAM",
        "SUPPORT",
    ]
    if (address := os.getenv(f"DEPARTMENT_{department}", ""))
}

DEFAULT_DEPARTMENT = os.getenv("DEFAULT_DEPARTMENT", "PERSONAL")
DEFAULT_EMAIL = os.getenv("DEFAULT_EMAIL", "")