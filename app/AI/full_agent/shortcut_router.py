import re

ROOM_RE = re.compile(r"\broom\s+([A-Z]?\d{3,4})\b", re.IGNORECASE)
