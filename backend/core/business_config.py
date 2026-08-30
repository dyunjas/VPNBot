from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class BusinessSetting:
    key: str
    label: str
    type: str
    default: str
    min_value: int | None = None
    max_value: int | None = None
    description: str = ""


BUSINESS_SETTINGS: tuple[BusinessSetting, ...] = (
    BusinessSetting(
        key="TRAFFIC_PRICE_PER_GB_RUB",
        label="Цена 1 GB трафика",
        type="decimal",
        default="2",
        min_value=0,
        description="Стоимость докупки трафика в RUB за 1 GB.",
    ),
    BusinessSetting(
        key="MIN_TRAFFIC_PURCHASE_GB",
        label="Минимальная докупка GB",
        type="int",
        default="1",
        min_value=1,
        description="Минимальное количество GB при докупке трафика.",
    ),
    BusinessSetting(
        key="DEVICE_SLOT_PRICE_RUB",
        label="Цена 1 слота устройства",
        type="decimal",
        default="50",
        min_value=0,
        description="Стоимость докупки одного дополнительного устройства в RUB.",
    ),
    BusinessSetting(
        key="MIN_WITHDRAW_AMOUNT_RUB",
        label="Минимальная сумма вывода",
        type="int",
        default="500",
        min_value=1,
        description="Минимальная сумма заявки на внешний вывод реферального баланса.",
    ),
    BusinessSetting(
        key="MIN_REFERRAL_TRANSFER_AMOUNT_RUB",
        label="Минимальный перевод реф. баланса",
        type="int",
        default="50",
        min_value=1,
        description="Минимальная сумма перевода с реферального баланса на основной.",
    ),
    BusinessSetting(
        key="REFERRAL_BONUS_HOURS",
        label="Бонус за приглашение, часов",
        type="int",
        default="24",
        min_value=0,
        description="На сколько часов продлевать подписку пригласившему за нового реферала.",
    ),
    BusinessSetting(
        key="SUBSCRIPTION_RENEWAL_WINDOW_DAYS",
        label="Окно продления подписки, дней",
        type="int",
        default="3",
        min_value=0,
        description="За сколько дней до окончания разрешено продлевать активную подписку.",
    ),
    BusinessSetting(
        key="CRYPTO_INVOICE_EXPIRES_IN_SEC",
        label="Срок CryptoBot инвойса, сек",
        type="int",
        default="900",
        min_value=60,
        description="Время жизни инвойса CryptoBot.",
    ),
    BusinessSetting(
        key="PALLY_INVOICE_TTL_SEC",
        label="Срок Pally платежа, сек",
        type="int",
        default="600",
        min_value=60,
        description="Время жизни платежа Pally.",
    ),
    BusinessSetting(
        key="PAYMENT_CRYPTOBOT_ENABLED",
        label="CryptoBot включён",
        type="bool",
        default="true",
        description="Разрешить пользователям создавать платежи через CryptoBot.",
    ),
    BusinessSetting(
        key="PAYMENT_PALLY_ENABLED",
        label="Pally включён",
        type="bool",
        default="true",
        description="Разрешить пользователям создавать платежи через Pally.",
    ),
    BusinessSetting(
        key="PAYMENT_PLATEGA_ENABLED",
        label="Platega включён",
        type="bool",
        default="true",
        description="Разрешить пользователям создавать платежи через Platega.",
    ),
)

BUSINESS_SETTINGS_BY_KEY = {setting.key: setting for setting in BUSINESS_SETTINGS}
PAYMENT_SETTING_ALIASES = {"cryptobot": "PAYMENT_CRYPTO_ENABLED"}


def _read_env_lines() -> list[str]:
    if not ENV_PATH.exists():
        return []
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _parse_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in _read_env_lines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _coerce_value(setting: BusinessSetting, value: object) -> str:
    raw = str(value if value is not None else "").strip()
    if raw == "":
        raw = setting.default

    if setting.type == "int":
        parsed = int(raw)
        if setting.min_value is not None and parsed < setting.min_value:
            raise ValueError(f"{setting.key} must be >= {setting.min_value}")
        if setting.max_value is not None and parsed > setting.max_value:
            raise ValueError(f"{setting.key} must be <= {setting.max_value}")
        return str(parsed)

    if setting.type == "decimal":
        parsed = Decimal(raw.replace(",", "."))
        if setting.min_value is not None and parsed < Decimal(setting.min_value):
            raise ValueError(f"{setting.key} must be >= {setting.min_value}")
        return str(parsed.normalize())

    if setting.type == "bool":
        normalized = raw.lower()
        if normalized not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            raise ValueError(f"{setting.key} must be boolean")
        return "true" if normalized in {"true", "1", "yes", "on"} else "false"

    return raw


def get_business_value(key: str) -> str:
    setting = BUSINESS_SETTINGS_BY_KEY[key]
    return _parse_env().get(key, setting.default)


def get_business_int(key: str) -> int:
    setting = BUSINESS_SETTINGS_BY_KEY[key]
    return int(_coerce_value(setting, get_business_value(key)))


def get_business_decimal(key: str) -> Decimal:
    setting = BUSINESS_SETTINGS_BY_KEY[key]
    return Decimal(_coerce_value(setting, get_business_value(key)))


def get_business_bool(key: str) -> bool:
    return _coerce_value(BUSINESS_SETTINGS_BY_KEY[key], get_business_value(key)) == "true"


def is_payment_method_enabled(method: str) -> bool:
    key = f"PAYMENT_{method.upper()}_ENABLED"
    alias = PAYMENT_SETTING_ALIASES.get(method.lower())
    raw_values = _parse_env()
    if alias and alias in raw_values and key not in raw_values:
        return raw_values[alias].strip().lower() in {"true", "1", "yes", "on"}
    return get_business_bool(key)


def list_business_settings() -> list[dict[str, object]]:
    values = _parse_env()
    items: list[dict[str, object]] = []
    for setting in BUSINESS_SETTINGS:
        value = values.get(setting.key, setting.default)
        items.append(
            {
                "key": setting.key,
                "label": setting.label,
                "type": setting.type,
                "value": _coerce_value(setting, value),
                "default": setting.default,
                "min": setting.min_value,
                "max": setting.max_value,
                "description": setting.description,
            }
        )
    return items


def update_business_settings(updates: dict[str, object]) -> list[dict[str, object]]:
    normalized: dict[str, str] = {}
    for key, value in updates.items():
        setting = BUSINESS_SETTINGS_BY_KEY.get(key)
        if not setting:
            raise KeyError(key)
        normalized[key] = _coerce_value(setting, value)

    lines = _read_env_lines()
    seen: set[str] = set()
    next_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            next_lines.append(line)
            continue
        key, _ = stripped.split("=", 1)
        key = key.strip()
        if key in normalized:
            next_lines.append(f"{key}={normalized[key]}")
            seen.add(key)
        else:
            next_lines.append(line)

    missing = [key for key in normalized if key not in seen]
    if missing:
        if next_lines and next_lines[-1].strip():
            next_lines.append("")
        next_lines.append("# Business Logic Configuration")
        for key in missing:
            next_lines.append(f"{key}={normalized[key]}")

    ENV_PATH.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8")
    return list_business_settings()
