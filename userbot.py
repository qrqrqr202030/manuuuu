"""
userbot.py
Telethon MTProto Client Runner (Userbot).
Use this if you DO NOT have administrator permissions in the source channel.
Your personal Telegram account (logged in via Telethon) listens to messages
in the source channel, extracts ONLY the links, and posts them to your destination channel.

Requirements:
- TELEGRAM_API_ID and TELEGRAM_API_HASH from https://my.telegram.org
"""

import os
import sys
import asyncio
import logging
from typing import List, Union
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import RPCError

import config
from link_extractor import extract_links

# Configure logging
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("TelegramUserbot")


async def start_cloud_health_server() -> None:
    """
    If running in a cloud container (Render, Koyeb, Railway), listen on $PORT
    to keep the cloud service active and satisfy health checks.
    """
    port_str = os.getenv("PORT", "").strip()
    if not port_str:
        return

    try:
        port = int(port_str)
        async def handle_ping(reader, writer):
            await reader.read(100)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nOK")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handle_ping, "0.0.0.0", port)
        logger.info("Cloud healthcheck HTTP server running on port %d", port)
    except Exception as e:
        logger.warning("Could not start cloud health server on port %s: %s", port_str, e)


def validate_configuration() -> None:
    if not config.TELEGRAM_API_ID or not config.TELEGRAM_API_HASH:
        logger.error(
            "\n" + "=" * 60 + "\n"
            "MISSING TELEGRAM_API_ID or TELEGRAM_API_HASH!\n"
            "To use userbot.py, get your API ID & Hash from https://my.telegram.org\n"
            "and set TELEGRAM_API_ID and TELEGRAM_API_HASH in your .env file.\n"
            + "=" * 60
        )
        sys.exit(1)

    if not config.SOURCE_CHANNELS:
        logger.warning("WARNING: SOURCE_CHANNEL_ID is empty! No channels to listen to.")

    if not config.DESTINATION_CHANNELS:
        logger.warning("WARNING: DESTINATION_CHANNEL_ID is empty! Nowhere to post links.")


async def resolve_target(client: TelegramClient, target: Union[int, str]):
    """
    Resolve a channel/group by ID, username, or dialog title.
    """
    # 1. Try get_entity directly (works for @usernames, numerical IDs, phone, etc.)
    try:
        return await client.get_entity(target)
    except Exception:
        pass

    # 2. Try looking through the user's active dialogs by exact or partial title match
    target_str = str(target).strip().lower()
    async for dialog in client.iter_dialogs():
        title = (dialog.name or getattr(dialog.entity, "title", "") or "").strip().lower()
        if title == target_str:
            return dialog.entity

    # Try partial match if exact match wasn't found
    async for dialog in client.iter_dialogs():
        title = (dialog.name or getattr(dialog.entity, "title", "") or "").strip().lower()
        if target_str in title:
            return dialog.entity

    raise ValueError(f"Could not find channel or group matching '{target}' in your Telegram chats.")


async def main() -> None:
    validate_configuration()

    # Start cloud web port if $PORT is provided
    await start_cloud_health_server()

    # Use StringSession if available, else local session file
    session_target = (
        StringSession(config.TELETHON_STRING_SESSION)
        if config.TELETHON_STRING_SESSION
        else config.TELETHON_SESSION_NAME
    )

    logger.info("Initializing Telethon Userbot client...")
    client = TelegramClient(
        session_target,
        config.TELEGRAM_API_ID,
        config.TELEGRAM_API_HASH,
    )

    await client.connect()
    if not await client.is_user_authorized():
        print("\n" + "=" * 65)
        print("  TELEGRAM USERBOT LOGIN (ONE-TIME SETUP)")
        print("=" * 65)
        print("  To read deals from @mamadeals1 without requiring admin rights,")
        print("  this script connects using YOUR personal Telegram account.\n")
        print("  👉 Enter your personal Telegram PHONE NUMBER (with country code).")
        print("     Examples: +15551234567 or +5511987654321")
        print("     ⚠️  DO NOT enter a bot token here!")
        print("=" * 65 + "\n")

    await client.start(phone=lambda: input("Enter your phone number (with country code, e.g. +1...): "))
    me = await client.get_me()
    logger.info("Logged in as: %s (@%s)", me.first_name, me.username or "no_username")

    # Resolve source chats
    sources = config.SOURCE_CHANNELS
    logger.info("Resolving source channels: %s", sources)
    resolved_sources = []
    for s in sources:
        try:
            entity = await resolve_target(client, s)
            resolved_sources.append(entity)
            logger.info("Successfully resolved source: '%s' (ID: %s)", getattr(entity, "title", s), getattr(entity, "id", ""))
        except Exception as e:
            logger.warning("Could not pre-resolve source '%s': %s. Using raw identifier.", s, e)
            resolved_sources.append(s)

    logger.info("Resolving destination channels/groups: %s", config.DESTINATION_CHANNELS)
    resolved_destinations = []
    for d in config.DESTINATION_CHANNELS:
        try:
            entity = await resolve_target(client, d)
            resolved_destinations.append(entity)
            logger.info("Successfully resolved destination: '%s' (ID: %s)", getattr(entity, "title", d), getattr(entity, "id", ""))
        except Exception as e:
            logger.warning("Could not pre-resolve destination '%s': %s. Using raw identifier.", d, e)
            resolved_destinations.append(d)

    @client.on(events.NewMessage(chats=resolved_sources or sources))
    async def handler(event):
        chat = await event.get_chat()
        chat_title = getattr(chat, "title", str(event.chat_id))
        logger.info("Received message #%s from '%s'", event.id, chat_title)

        links = extract_links(event.message)
        if not links:
            logger.info("Message #%s contains no links. Skipping.", event.id)
            return

        logger.info("Found %d link(s) in message #%s. Forwarding...", len(links), event.id)

        link_preview = not config.DISABLE_WEB_PAGE_PREVIEW

        for dest in (resolved_destinations or config.DESTINATION_CHANNELS):
            try:
                if config.SEND_MODE == "individual":
                    for link in links:
                        await client.send_message(
                            dest,
                            link,
                            link_preview=link_preview,
                        )
                else:
                    payload = "\n".join(links)
                    await client.send_message(
                        dest,
                        payload,
                        link_preview=link_preview,
                    )
                logger.info("Delivered link(s) to destination '%s'", getattr(dest, "title", dest))
            except RPCError as e:
                logger.error("Failed to send message to destination: %s", e)

    logger.info("Userbot is running and listening for new posts. Press Ctrl+C to stop.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
