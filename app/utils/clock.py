from datetime import datetime
from zoneinfo import ZoneInfo


def now():
    """All agenda times refer to Brasilia, independently of the server/PC timezone."""
    return datetime.now(ZoneInfo('America/Sao_Paulo')).replace(tzinfo=None)
