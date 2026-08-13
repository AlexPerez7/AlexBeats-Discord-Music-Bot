import os

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("El token del bot no está configurado (DISCORD_BOT_TOKEN).")

COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
DEFAULT_VOLUME = _int_env("DEFAULT_VOLUME", 50) / 100
INACTIVITY_TIMEOUT_SECONDS = _int_env("INACTIVITY_TIMEOUT_SECONDS", 300)

_dev_guild_id = os.getenv("DEV_GUILD_ID")
DEV_GUILD_ID = int(_dev_guild_id) if _dev_guild_id else None

FFMPEG_PATH = os.getenv("FFMPEG_PATH") or "ffmpeg"
