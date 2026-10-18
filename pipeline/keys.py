"""Load API keys from the environment or a local .env. Keys are never printed, logged or returned in errors."""
import os

from . import config

KEY_NAMES = ("OPENAI_API_KEY", "TYPESAFE_API_KEY", "ANTHROPIC_API_KEY")


def load_dotenv(path=None):
    """Minimal .env reader (KEY=VALUE lines). Existing environment variables win."""
    path = path or config.ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name and value and name not in os.environ:
            os.environ[name] = value


class MissingKeyError(RuntimeError):
    """A required API key is absent: the run stops before any request is sent."""


def require(name):
    load_dotenv()
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingKeyError(f"{name} is not set. Add it to .env (see .env.example); it is never printed or logged.")
    return value


def redact(text):
    """Remove any loaded key value from a string before it is logged or shown."""
    text = str(text)
    for name in KEY_NAMES:
        value = os.environ.get(name)
        if value and len(value) > 8:
            text = text.replace(value, f"<{name} redacted>")
    return text
