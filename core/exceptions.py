"""Custom exception hierarchy."""

from dataclasses import dataclass, field


class BotError(Exception):
    """Base for all bot exceptions."""


class InvalidTransitionError(BotError):
    """Raised when a task status transition is not allowed."""

    def __init__(self, from_status: str, to_status: str, allowed: list[str]):
        self.from_status = from_status
        self.to_status = to_status
        self.allowed = allowed
        super().__init__(
            f"Invalid transition: {from_status} → {to_status}. Allowed: {allowed}"
        )


class TaskNotFoundError(BotError):
    pass


class DuplicateTaskError(BotError):
    pass


class AITransientError(BotError):
    """Retryable AI failure (rate-limit, connection, timeout)."""


class AIPermanentError(BotError):
    """Non-retryable AI failure (malformed response, invalid JSON)."""


class ConfigurationError(BotError):
    pass


@dataclass(slots=True)
class StartupConfigError(Exception):
    """Raised when startup configuration is invalid and startup must stop."""

    code: str
    title: str
    details: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    exit_code: int = 2

    def render_terminal(self) -> str:
        lines: list[str] = [f"ERROR: {self.title}"]
        if self.details:
            lines.append("")
            lines.append("Details:")
            for detail in self.details:
                lines.append(f"- {detail}")
        if self.hints:
            lines.append("")
            lines.append("How to fix:")
            for index, hint in enumerate(self.hints, start=1):
                lines.append(f"{index}. {hint}")
        return "\n".join(lines)
