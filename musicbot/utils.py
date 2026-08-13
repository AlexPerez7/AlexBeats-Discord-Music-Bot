from enum import Enum


class LoopMode(Enum):
    OFF = "off"
    SONG = "song"
    QUEUE = "queue"


def format_duration(seconds) -> str:
    """Formatea una duración en segundos como 'm:ss' o 'h:mm:ss'."""
    if seconds is None:
        return "En vivo"

    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
