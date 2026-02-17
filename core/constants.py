"""All magic numbers, enums, and string sets in one place."""

from datetime import timedelta

# --- Task statuses ---

VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["awaiting_confirmation", "cancelled"],
    "awaiting_confirmation": ["processing", "cancelled"],
    "processing": ["finished", "cancelled"],
    "finished": ["delivered"],
    "delivered": [],
    "cancelled": [],
}

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_PLATFORMS = {"fansly", "onlyfans"}
POSTPONE_ALLOWED_STATUSES = {"awaiting_confirmation", "processing"}

# --- AI ---

DEFAULT_AI_MODEL = "claude-sonnet-4-5-20250929"
AI_MAX_INLINE_RETRIES = 2
AI_RETRY_BASE_DELAY = 2.0  # seconds
AI_API_TIMEOUT = 30.0  # seconds

TEXT_FIELDS = (
    "fan_link", "fan_name", "payment_note",
    "duration", "description", "outfit", "notes",
)
AMOUNT_FIELDS = ("amount_total", "amount_paid", "amount_remaining")

# --- Scheduler ---

RETRY_BACKOFF_MINUTES = [2, 5, 10, 20, 40]
MAX_RETRY_ATTEMPTS = 5
MAX_RETRY_WINDOW = timedelta(hours=2)
OVERDUE_CHECK_INTERVAL = timedelta(minutes=30)
HOURLY_CHECK_INTERVAL = timedelta(hours=1)
RETRY_SCAN_INTERVAL = timedelta(minutes=1)
MORNING_DIGEST_HOUR = 9

# --- Pre-filter ---

BRIEF_EMOJIS = {"📦", "🎬", "👗", "📝", "🔥", "📅"}

BRIEF_KEYWORDS = [
    "описание заказа", "оплата", "длительность", "срочность",
    "дедлайн", "покупатель", "deadline", "buyer",
    "payment", "duration", "urgency", "order description",
]

DIRECT_MARKERS = ["📦 описание заказа", "📦 order"]

MIN_BRIEF_TEXT_LENGTH = 30
MIN_HEURISTIC_SCORE = 2

# --- Postpone ---

POSTPONE_TTL_SECONDS = 120

# --- Reply detection ---

SHOT_KEYWORDS = [
    "снято", "отснято", "готово", "готов", "готова", "done", "shot",
    "filmed", "записала", "сняла", "загружу", "будет загружено",
]
DELIVERED_KEYWORDS = [
    "отправлено", "доставлено", "sent", "delivered",
    "отправила", "скинула",
]
