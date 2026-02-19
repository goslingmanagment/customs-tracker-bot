#!/usr/bin/env python3
"""Backfill task text fields so AI-generated text is Russian-first."""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.classifier import classify_message
from core.exceptions import AITransientError
from db.engine import async_session
from db.models import Task

TEXT_FIELDS = ("description", "outfit", "notes")


@dataclass
class BackfillFailure:
    task_id: int
    reason: str


@dataclass
class BackfillSummary:
    scanned: int = 0
    changed_candidates: int = 0
    updated: int = 0
    failures: list[BackfillFailure] = field(default_factory=list)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or apply historical backfill for Russian AI text fields "
            "(description, outfit, notes)."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates. Without this flag, script runs in dry-run mode.",
    )
    parser.add_argument(
        "--task-id",
        type=_positive_int,
        help="Process only one task id.",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        help="Maximum number of tasks to scan.",
    )
    return parser.parse_args(argv)


async def _load_tasks(
    session: AsyncSession,
    *,
    task_id: int | None,
    limit: int | None,
) -> list[Task]:
    stmt = select(Task).order_by(Task.id.asc())
    if task_id is not None:
        stmt = stmt.where(Task.id == task_id)
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _extract_text_fields(data: dict) -> dict[str, str | None]:
    normalized: dict[str, str | None] = {}
    for field_name in TEXT_FIELDS:
        value = data.get(field_name)
        if value is None:
            normalized[field_name] = None
            continue
        if not isinstance(value, str):
            normalized[field_name] = None
            continue
        stripped = value.strip()
        normalized[field_name] = stripped or None
    return normalized


def _append_failure(summary: BackfillSummary, task_id: int, reason: str) -> None:
    summary.failures.append(BackfillFailure(task_id=task_id, reason=reason))


async def run_backfill(
    *,
    apply: bool,
    task_id: int | None = None,
    limit: int | None = None,
    session_maker: async_sessionmaker[AsyncSession] = async_session,
) -> BackfillSummary:
    summary = BackfillSummary()

    async with session_maker() as session:
        tasks = await _load_tasks(session, task_id=task_id, limit=limit)
        for task in tasks:
            summary.scanned += 1

            if not isinstance(task.raw_text, str) or not task.raw_text.strip():
                _append_failure(summary, task.id, "raw_text_missing")
                continue

            try:
                result = await classify_message(task.raw_text, has_photo=False)
            except AITransientError as exc:
                _append_failure(summary, task.id, f"classify_transient: {exc}")
                continue
            except Exception as exc:
                _append_failure(summary, task.id, f"classify_error: {exc}")
                continue

            if result is None:
                _append_failure(summary, task.id, "classify_none")
                continue
            if not bool(result.get("is_task", False)):
                _append_failure(summary, task.id, "classify_non_task")
                continue

            data = result.get("data")
            if not isinstance(data, dict):
                _append_failure(summary, task.id, "classify_missing_data")
                continue

            new_values = _extract_text_fields(data)
            changed = any(getattr(task, field_name) != new_values[field_name] for field_name in TEXT_FIELDS)
            if not changed:
                continue

            summary.changed_candidates += 1
            if not apply:
                continue

            try:
                for field_name in TEXT_FIELDS:
                    setattr(task, field_name, new_values[field_name])
                await session.commit()
                summary.updated += 1
            except Exception as exc:
                await session.rollback()
                _append_failure(summary, task.id, f"update_failed: {exc}")

        if not apply:
            await session.rollback()

    return summary


def print_summary(summary: BackfillSummary, *, apply: bool) -> None:
    mode = "apply" if apply else "dry-run"
    print(
        (
            f"[{mode}] scanned={summary.scanned} "
            f"changed_candidates={summary.changed_candidates} "
            f"updated={summary.updated} failures={len(summary.failures)}"
        )
    )
    if summary.failures:
        print("failures:")
        for failure in summary.failures:
            print(f"- task_id={failure.task_id}: {failure.reason}")


async def _amain(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = await run_backfill(
        apply=args.apply,
        task_id=args.task_id,
        limit=args.limit,
    )
    print_summary(summary, apply=args.apply)
    return 1 if summary.failures else 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())
