"""
Utility functions for the TaskFlow API.
"""

import re
from datetime import datetime, timedelta
from typing import Optional


def validate_email(email: str) -> bool:
    """
    Validate an email address format.
    
    Args:
        email: Email string to validate
        
    Returns:
        True if valid format, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format a datetime object to ISO 8601 string."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def calculate_due_date(days_from_now: int) -> datetime:
    """Calculate a due date from the current time."""
    return datetime.utcnow() + timedelta(days=days_from_now)


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to a maximum length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def sanitize_input(text: str) -> str:
    """
    Basic input sanitization to prevent injection attacks.
    Strips HTML tags and excessive whitespace.
    """
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean
