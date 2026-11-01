"""
link_extractor.py
Robust extraction and normalization of URLs and hyperlinks from:
- Plain text
- Telegram Bot API Message objects (entities, text links, captions)
- Telethon Message objects (entities, text URLs, captions)
"""

import re
from typing import Any, List, Optional, Set
from urllib.parse import urlparse

# Regular expression matching web URLs and Telegram links
URL_REGEX = re.compile(
    r"""(?xi)
    \b
    (
        (?:https?://|ftp://|www\d{0,3}\.|t\.me/)
        [^\s<>"'()]+
        (?:\([^\s<>"'()]+\)|[^\s<>"'()~!@#$%^&*()_+=\[\]{}|\\;:'",.<>?/])
    )
    """
)


def clean_url(url: str) -> str:
    """
    Clean and normalize an extracted URL:
    - Strips whitespace and surrounding/trailing punctuation.
    - Preserves balanced parentheses (e.g., Wikipedia URLs).
    - Prepend 'https://' to 'www.' and 't.me/' if protocol is missing.
    """
    if not url:
        return ""

    url = url.strip()

    # Strip surrounding paired characters e.g. (url), [url], <url>, "url", 'url'
    surrounding_pairs = [
        ("(", ")"),
        ("[", "]"),
        ("{", "}"),
        ("<", ">"),
        ('"', '"'),
        ("'", "'"),
    ]
    changed = True
    while changed:
        changed = False
        url = url.strip()
        for start_char, end_char in surrounding_pairs:
            if url.startswith(start_char) and url.endswith(end_char):
                inner = url[1:-1].strip()
                if start_char == "(" and inner.count(")") > inner.count("("):
                    continue
                url = inner
                changed = True
                break

    # Strip trailing punctuation commonly attached at sentence end
    trailing_chars = ".,;:!?\"'»«”’"
    while url and url[-1] in trailing_chars:
        url = url[:-1]

    # Handle unmatched trailing closing parenthesis e.g. "https://example.com)"
    if url.endswith(")"):
        open_paren_count = url.count("(")
        close_paren_count = url.count(")")
        if close_paren_count > open_paren_count:
            url = url[:-1]

    # Handle unmatched trailing closing bracket e.g. "https://example.com]"
    if url.endswith("]"):
        open_bracket_count = url.count("[")
        close_bracket_count = url.count("]")
        if close_bracket_count > open_bracket_count:
            url = url[:-1]

    # Add https:// prefix if needed
    lower_url = url.lower()
    if lower_url.startswith("www."):
        url = "https://" + url
    elif lower_url.startswith("t.me/"):
        url = "https://" + url

    return url.strip()


def is_valid_url(url: str) -> bool:
    """
    Check if a string looks like a valid web URL.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme in ("http", "https", "ftp") and parsed.netloc)
    except Exception:
        return False


def deduplicate_preserve_order(items: List[str]) -> List[str]:
    """
    Deduplicate a list while preserving the original order.
    """
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        cleaned = clean_url(item)
        if cleaned and cleaned not in seen and is_valid_url(cleaned):
            seen.add(cleaned)
            result.append(cleaned)
    return result


def extract_links_from_text(text: Optional[str]) -> List[str]:
    """
    Extract all URLs from a plain text string using regex.
    """
    if not text:
        return []

    found = URL_REGEX.findall(text)
    links: List[str] = []
    for match in found:
        url = match if isinstance(match, str) else match[0]
        cleaned = clean_url(url)
        if cleaned:
            links.append(cleaned)

    return deduplicate_preserve_order(links)


def extract_links_from_telegram_message(message: Any) -> List[str]:
    """
    Extract links from a python-telegram-bot Message object.
    Inspects:
    1. Text and text entities (MessageEntityType.URL, MessageEntityType.TEXT_LINK)
    2. Caption and caption entities (for media like photos, videos, files)
    3. Regex fallback to ensure no raw links are overlooked.
    """
    extracted_raw: List[str] = []

    # 1. Parse text entities if present
    if getattr(message, "text", None):
        try:
            # parse_entities handles UTF-16 surrogate pairs properly
            entities_dict = message.parse_entities(types=["url", "text_link"])
            for entity, entity_text in entities_dict.items():
                if getattr(entity, "type", None) == "text_link" and getattr(entity, "url", None):
                    extracted_raw.append(entity.url)
                elif getattr(entity, "type", None) == "url":
                    extracted_raw.append(entity_text)
        except Exception:
            pass
        # Fallback/supplement with regex on message.text
        extracted_raw.extend(extract_links_from_text(message.text))

    # 2. Parse caption entities if present (e.g. photos, videos with captions)
    if getattr(message, "caption", None):
        try:
            caption_entities_dict = message.parse_caption_entities(types=["url", "text_link"])
            for entity, entity_text in caption_entities_dict.items():
                if getattr(entity, "type", None) == "text_link" and getattr(entity, "url", None):
                    extracted_raw.append(entity.url)
                elif getattr(entity, "type", None) == "url":
                    extracted_raw.append(entity_text)
        except Exception:
            pass
        # Fallback/supplement with regex on message.caption
        extracted_raw.extend(extract_links_from_text(message.caption))

    return deduplicate_preserve_order(extracted_raw)


def extract_links_from_telethon_message(message: Any) -> List[str]:
    """
    Extract links from a Telethon Message object.
    Inspects:
    1. message.entities (MessageEntityTextUrl, MessageEntityUrl)
    2. message.message / message.raw_text using regex
    """
    extracted_raw: List[str] = []
    text = getattr(message, "message", "") or getattr(message, "raw_text", "") or ""

    entities = getattr(message, "entities", None)
    if entities and text:
        text_encoded = text.encode("utf-16-le")
        for ent in entities:
            ent_type = ent.__class__.__name__
            if ent_type == "MessageEntityTextUrl" and getattr(ent, "url", None):
                extracted_raw.append(ent.url)
            elif ent_type == "MessageEntityUrl":
                try:
                    # Telethon offsets are in UTF-16 code units (2 bytes each in utf-16-le)
                    start = ent.offset * 2
                    end = (ent.offset + ent.length) * 2
                    raw_sub = text_encoded[start:end].decode("utf-16-le")
                    extracted_raw.append(raw_sub)
                except Exception:
                    pass

    # Regex extraction from full text
    if text:
        extracted_raw.extend(extract_links_from_text(text))

    return deduplicate_preserve_order(extracted_raw)


def extract_links(item: Any) -> List[str]:
    """
    Universal link extractor.
    Accepts:
    - str: plain text
    - python-telegram-bot Message
    - Telethon Message
    """
    if item is None:
        return []
    if isinstance(item, str):
        return extract_links_from_text(item)

    # Check for python-telegram-bot Message
    if hasattr(item, "parse_entities") or hasattr(item, "parse_caption_entities"):
        return extract_links_from_telegram_message(item)

    # Check for Telethon Message
    if hasattr(item, "raw_text") or hasattr(item, "entities"):
        return extract_links_from_telethon_message(item)

    # If it has .text or .caption attribute
    if hasattr(item, "text") or hasattr(item, "caption"):
        return extract_links_from_telegram_message(item)

    return []
