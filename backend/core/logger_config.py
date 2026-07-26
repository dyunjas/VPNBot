import logging
import os
from logging.handlers import RotatingFileHandler

from backend.core.error_reporter import TelegramErrorReportHandler

LOG_DIR = "logs"
MAX_BYTES = 10_000_000
BACKUP_COUNT = 5

LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

os.makedirs(LOG_DIR, exist_ok=True)


class MessageOrNameFilter(logging.Filter):
    def __init__(
        self,
        *,
        name_prefixes: tuple[str, ...] = (),
        message_tokens: tuple[str, ...] = (),
    ):
        super().__init__()
        self._name_prefixes = tuple(p.lower() for p in name_prefixes if p)
        self._message_tokens = tuple(t.lower() for t in message_tokens if t)

    def filter(self, record: logging.LogRecord) -> bool:
        name = (record.name or "").lower()
        if self._name_prefixes and any(name.startswith(prefix) for prefix in self._name_prefixes):
            return True

        message = record.getMessage().lower()
        return bool(self._message_tokens and any(token in message for token in self._message_tokens))


class BenignNetworkNoiseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage().lower()
        if "invalid http request received" in message:
            return False

        if (
            (record.name or "").lower() == "asyncio"
            and "exception in callback _proactorbasepipetransport._call_connection_lost" in message
            and record.exc_info
            and issubclass(record.exc_info[0], ConnectionResetError)
        ):
            return False

        return True


def _file_handler(filename: str, level: int = logging.DEBUG) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    return handler


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

if logger.hasHandlers():
    logger.handlers.clear()

# Full application log (all categories)
all_handler = _file_handler("app.log")
logger.addHandler(all_handler)

# Legacy full log filename kept for backward compatibility.
legacy_handler = _file_handler("bot.log")
logger.addHandler(legacy_handler)

# Payments
payments_handler = _file_handler("payments.log")
payments_handler.addFilter(
    MessageOrNameFilter(
        message_tokens=(
            "[biz][billing]",
            "[platega]",
            "[pally]",
            "[crypto]",
            "payment",
            "invoice",
        )
    )
)
logger.addHandler(payments_handler)

# Subscriptions
subscriptions_handler = _file_handler("subscriptions.log")
subscriptions_handler.addFilter(
    MessageOrNameFilter(
        message_tokens=(
            "[biz][subscription]",
            "[subscription]",
            "expire checker",
        )
    )
)
logger.addHandler(subscriptions_handler)

# Devices
devices_handler = _file_handler("devices.log")
devices_handler.addFilter(
    MessageOrNameFilter(
        message_tokens=(
            "[biz][device]",
            "device limit",
            "register device",
        )
    )
)
logger.addHandler(devices_handler)

# Aiogram framework and bot update loop
aiogram_handler = _file_handler("aiogram.log")
aiogram_handler.addFilter(
    MessageOrNameFilter(
        name_prefixes=("aiogram",),
        message_tokens=(
            "update id=",
            "handled update",
            "polling",
        ),
    )
)
logger.addHandler(aiogram_handler)

# Business-wide stream
business_handler = _file_handler("business.log")
business_handler.addFilter(MessageOrNameFilter(message_tokens=("[biz]",)))
logger.addHandler(business_handler)

# Other uncategorized/system logs
system_handler = _file_handler("system.log")
system_handler.addFilter(
    MessageOrNameFilter(
        name_prefixes=("uvicorn", "fastapi", "sqlalchemy", "aiohttp"),
        message_tokens=(
            "database",
            "settings successfully loaded",
            "bot started",
            "bot stopped",
            "bot crashed",
            "connection",
            "error",
            "exception",
        ),
    )
)
logger.addHandler(system_handler)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
logger.addHandler(console_handler)

telegram_error_handler = TelegramErrorReportHandler()
telegram_error_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
logger.addHandler(telegram_error_handler)

benign_network_noise_filter = BenignNetworkNoiseFilter()
for handler in logger.handlers:
    handler.addFilter(benign_network_noise_filter)

# Ensure aiogram operational logs are emitted to handlers.
logging.getLogger("aiogram").setLevel(logging.INFO)
