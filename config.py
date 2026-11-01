"""
config.py
Configuration loader for Telegram Link Forwarder Bot.
Reads environment variables from .env file or system environment.
"""

import os
from typing import List, Union
from dotenv import load_dotenv

# Load variables from .env if present
load_dotenv()


def parse_channel_list(raw_value: str) -> List[Union[int, str]]:
    """
    Parse a comma-separated list of channel IDs or usernames.
    Examples:
      "-1001234567890, @my_channel, 987654321"
    """
    if not raw_value:
        return []

    results: List[Union[int, str]] = []
    tokens = [t.strip() for t in raw_value.split(",") if t.strip()]
    for token in tokens:
        # Check if it's an integer
        try:
            results.append(int(token))
        except ValueError:
            # Username or title
            results.append(token)
    return results


def to_bool(val: str, default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in ("true", "1", "yes", "y", "on")


# --- Telegram Bot API (bot.py) Settings ---
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Source and Destination channels
SOURCE_CHANNELS: List[Union[int, str]] = parse_channel_list(
    os.getenv("SOURCE_CHANNEL_ID", "")
)
DESTINATION_CHANNELS: List[Union[int, str]] = parse_channel_list(
    os.getenv("DESTINATION_CHANNEL_ID", "")
)

# Behavior toggles
FORWARD_EDITED_POSTS: bool = to_bool(os.getenv("FORWARD_EDITED_POSTS", "false"), default=False)
DISABLE_WEB_PAGE_PREVIEW: bool = to_bool(os.getenv("DISABLE_WEB_PAGE_PREVIEW", "true"), default=True)
SEND_MODE: str = os.getenv("SEND_MODE", "single").strip().lower()  # "single" or "individual"

# --- Telethon Userbot (userbot.py) Settings (Optional) ---
API_ID_RAW = os.getenv("TELEGRAM_API_ID", "").strip()
TELEGRAM_API_ID: int = int(API_ID_RAW) if API_ID_RAW.isdigit() else 0
TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "").strip()
TELETHON_SESSION_NAME: str = os.getenv("TELETHON_SESSION_NAME", "userbot_session").strip()
TELETHON_STRING_SESSION: str = os.getenv("TELETHON_STRING_SESSION", "").strip()
