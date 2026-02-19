"""add original brief section fields to tasks

Revision ID: 0003_add_original_brief_sections
Revises: 0002_add_ai_retry_queue
Create Date: 2026-02-19 03:30:00.000000
"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_add_original_brief_sections"
down_revision: Union[str, Sequence[str], None] = "0002_add_ai_retry_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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
    return _normalize_spaces(re.sub(r"^[^0-9A-Za-zА-Яа-яЁё]+", "", line.strip()))


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


def _parse_original_sections(raw_text: str | None) -> dict[str, str | None]:
    result = {
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


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("description_original", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("outfit_original", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("notes_original", sa.Text(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, raw_text FROM tasks")).fetchall()
    for row in rows:
        parsed = _parse_original_sections(row.raw_text)
        conn.execute(
            sa.text(
                """
                UPDATE tasks
                SET description_original = :description_original,
                    outfit_original = :outfit_original,
                    notes_original = :notes_original
                WHERE id = :task_id
                """
            ),
            {
                "task_id": row.id,
                "description_original": parsed["description_original"],
                "outfit_original": parsed["outfit_original"],
                "notes_original": parsed["notes_original"],
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("notes_original")
        batch_op.drop_column("outfit_original")
        batch_op.drop_column("description_original")
