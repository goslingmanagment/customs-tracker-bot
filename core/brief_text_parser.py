"""Utilities for extracting original brief sections from source text."""

from __future__ import annotations

import re

_SECTION_LABELS = {
    "description_original": (
        "описание задания",
        "task description",
    ),
    "outfit_original": (
        "одежда",
        "наряд",
        "outfit",
    ),
    "notes_original": (
        "заметки",
        "notes",
    ),
}

_STOP_LABELS = (
    "описание заказа",
    "order description",
    "дата",
    "date",
    "покупатель",
    "buyer",
    "фан",
    "fan",
    "ссылка",
    "link",
    "оплата",
    "payment",
    "сумма",
    "amount",
    "длительность",
    "duration",
    "срочность",
    "urgency",
    "priority",
    "дедлайн",
    "deadline",
    "сроки",
)


def _normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _clean_header_prefix(line: str) -> str:
    # Drop leading emojis/symbols, keep letters and numbers.
    cleaned = re.sub(r"^[^0-9A-Za-zА-Яа-яЁё]+", "", line.strip())
    return _normalize_spaces(cleaned)


def _split_inline_value(text: str, label: str) -> str | None:
    rest = text[len(label):].lstrip()
    if rest.startswith((":", "-", "—")):
        rest = rest[1:].lstrip()
    return rest or None


def _line_header_label(line: str) -> tuple[str, str | None] | None:
    cleaned = _clean_header_prefix(line)
    if not cleaned:
        return None

    lowered = cleaned.casefold()
    for section, labels in _SECTION_LABELS.items():
        for label in labels:
            if lowered == label:
                return section, None
            if lowered.startswith((f"{label}:", f"{label} -", f"{label} —", f"{label} ")):
                inline = _split_inline_value(cleaned, cleaned[: len(label)])
                return section, inline
    return None


def _is_stop_header(line: str) -> bool:
    if _line_header_label(line) is not None:
        return True

    cleaned = _clean_header_prefix(line)
    if not cleaned:
        return False

    lowered = cleaned.casefold()
    for label in _STOP_LABELS:
        if lowered == label:
            return True
        if lowered.startswith((f"{label}:", f"{label} -", f"{label} —", f"{label} ")):
            return True
    return False


def _join_block(lines: list[str]) -> str | None:
    if not lines:
        return None

    joined = "\n".join(line.rstrip() for line in lines).strip()
    return joined or None


def parse_original_brief_sections(raw_text: str | None) -> dict[str, str | None]:
    """Extract original description/outfit/notes blocks from a source brief."""
    result: dict[str, str | None] = {
        "description_original": None,
        "outfit_original": None,
        "notes_original": None,
    }
    if not raw_text:
        return result

    lines = raw_text.splitlines()
    idx = 0
    while idx < len(lines):
        matched = _line_header_label(lines[idx])
        if not matched:
            idx += 1
            continue

        section_name, inline_text = matched
        block_lines: list[str] = []
        if inline_text:
            block_lines.append(inline_text)

        idx += 1
        while idx < len(lines):
            line = lines[idx]
            if _is_stop_header(line):
                break
            block_lines.append(line)
            idx += 1

        block_value = _join_block(block_lines)
        if block_value:
            existing = result[section_name]
            if existing:
                result[section_name] = f"{existing}\n\n{block_value}"
            else:
                result[section_name] = block_value

    return result
