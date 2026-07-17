import secrets
import string
from app.config import settings

def generate_slug(n: int = 7) -> str:
    """Step 9: Secure slug generation"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))