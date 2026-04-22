import secrets
import string
from datetime import timedelta

from django.utils import timezone


def generate_token(prefix: str, length: int = 5) -> str:
    alphabet = string.ascii_uppercase + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(length))
    year = timezone.now().year
    return f"{prefix}-{year}-{body}"


def default_sla_resolution_deadline(priority: str):
    """Return timedelta from now for resolution SLA (simplified policy)."""
    mapping = {
        "low": timedelta(days=5),
        "normal": timedelta(days=3),
        "high": timedelta(days=1),
        "critical": timedelta(hours=8),
    }
    return timezone.now() + mapping.get(priority, mapping["normal"])
