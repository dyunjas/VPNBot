"""Bounded incident aggregation. No network, settings or logging side effects."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


def redact(text: str) -> str:
    # Strip entire quoted values, including spaces; never send URL credentials/query.
    text = re.sub(r"(?i)(bearer\s+)\S+", r"\1[REDACTED]", text)
    text = re.sub(r'''(?i)(["']?(?:password|secret|token|access_token|refresh_token|api_token|bot_token|authorization|cookie|initData|signature|otp|totp_secret)["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;}]+)''', r"\1[REDACTED]", text)
    text = re.sub(r"(?i)(https?|postgres(?:ql)?(?:\+\w+)?|socks[45])://[^\s/@]+:[^\s/@]+@", r"\1://[REDACTED]@", text)
    text = re.sub(r"(https?://[^\s?#]+)\?[^\s]+", r"\1?[REDACTED]", text)
    text = re.sub(r"(/auth/deeplink/)[A-Za-z0-9_-]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?<!\d)\d{6,}:[A-Za-z0-9_-]{20,}", "[REDACTED BOT TOKEN]", text)
    text = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED JWT]", text)
    text = re.sub(r"(?is)\[parameters:.*?(?:\]\s*\n|$)", "[parameters: REDACTED]\n", text)
    return text


def category(record: logging.LogRecord, message: str) -> str:
    if record.levelno >= logging.CRITICAL or getattr(record, "incident_critical", False):
        return "critical"
    if getattr(record, "security_event", False):
        return "security"
    if re.search(r"database (?:connection|initialization) failed|bot crashed|failed to start application", message, re.I):
        return "critical"
    exc = record.exc_info[1] if record.exc_info else None
    seen = set()
    while exc and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, (ConnectionError, TimeoutError)) or type(exc).__name__ in {
            "ClientConnectionError", "ClientConnectorError", "ClientOSError", "ServerDisconnectedError",
            "ServerTimeoutError", "TelegramNetworkError", "ConnectTimeout", "ReadTimeout", "ConnectError",
        }:
            return "network"
        exc = exc.__cause__ or exc.__context__
    if re.search(r"timed?\s*out|timeout|connection (?:reset|refused|closed|lost)|network is unreachable|cannot connect to host|failed to fetch updates|temporary failure in name resolution", message, re.I):
        return "network"
    return "error"


def fingerprint(kind: str, context: str, source: str, message: str) -> str:
    # Collapse volatile IDs, timestamps, IPs and UUIDs, but keep distinct errors.
    message = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|\b(?:\d{1,3}\.){3}\d{1,3}\b|\b\d+\b|0x[0-9a-f]+", "#", message, flags=re.I)
    if kind == "network":
        message = "network outage"
    return hashlib.sha256(f"{kind}|{context}|{source}|{message}".encode()).hexdigest()


@dataclass
class Event:
    kind: str
    key: str
    context: str
    source: str
    message: str
    trace: str = ""
    peer: str = ""
    created: float = 0


@dataclass
class Incident:
    event: Event
    first: float
    last: float
    due: float
    count: int = 0
    samples: list[str] = field(default_factory=list)
    peers: set[str] = field(default_factory=set)

    def add(self, event: Event):
        self.count += 1
        self.last = event.created
        if event.message not in self.samples and len(self.samples) < 3:
            self.samples.append(event.message)
        if event.peer and len(self.peers) < 5:
            self.peers.add(event.peer)


class IncidentBuffer:
    def __init__(self, *, window=120, critical_repeat=300, max_groups=200, now=0):
        self.window, self.critical_repeat, self.max_groups = window, critical_repeat, max_groups
        self.next_flush = now + window
        self.groups: dict[str, Incident] = {}
        self.overflow = 0
        self.critical_times: list[float] = []

    def add(self, event: Event, now: float) -> list[Incident]:
        item = self.groups.get(event.key)
        if item is None:
            # Expired cooldown entries do not consume the cardinality budget forever.
            self.groups = {k:v for k,v in self.groups.items() if v.count or v.due > now}
            if len(self.groups) >= self.max_groups:
                self.overflow += 1
                return []
            item = Incident(event, event.created, event.created, now + self.critical_repeat)
            self.groups[event.key] = item
            item.add(event)
            self.critical_times = [t for t in self.critical_times if t > now - self.window]
            if event.kind == "critical" and len(self.critical_times) < 3:
                self.critical_times.append(now)
                report = self._snapshot(item)
                return [report]
            # New critical incidents above the immediate budget go into the next digest.
            if event.kind == "critical": item.due = self.next_flush
        else:
            if not item.count: item.first = event.created
            item.add(event)
        return []

    @staticmethod
    def _snapshot(item):
        result = Incident(item.event, item.first, item.last, item.due, item.count, list(item.samples), set(item.peers))
        item.count = 0
        item.samples.clear()
        item.peers.clear()
        return result

    def flush(self, now: float) -> tuple[list[Incident], int]:
        if now < self.next_flush: return [], 0
        result = []
        for key,item in list(self.groups.items()):
            if item.event.kind == "critical" and now < item.due: continue
            if item.count:
                result.append(self._snapshot(item))
                item.due = now + self.critical_repeat
            if item.event.kind != "critical" or (not item.count and item.due <= now):
                del self.groups[key]
        overflow, self.overflow = self.overflow, 0
        self.next_flush = now + self.window
        return result, overflow


TITLES = {"critical":"🚨 КРИТИЧЕСКИЙ СБОЙ", "security":"🛡 Попытки доступа", "network":"🌐 Сетевые ошибки", "error":"⚠️ Ошибки приложения"}


def render(incidents: list[Incident], overflow: int = 0) -> tuple[str, str]:
    counts = {kind:sum(i.count for i in incidents if i.event.kind == kind) for kind in TITLES}
    title = TITLES["critical"] if counts["critical"] else "📋 Сводка событий"
    lines = [title, "", *[f"{TITLES[kind]}: {count}" for kind,count in counts.items() if count]]
    if incidents:
        start = datetime.fromtimestamp(min(i.first for i in incidents),timezone.utc)
        end = datetime.fromtimestamp(max(i.last for i in incidents),timezone.utc)
        lines.append(f"Период: {start:%d.%m %H:%M:%S} — {end:%H:%M:%S} UTC")
    if overflow: lines.append(f"Событий сверх лимита детализации: {overflow}")
    summary = "\n".join(lines)
    details = [summary]
    for item in sorted(incidents,key=lambda i:(list(TITLES).index(i.event.kind),-i.count)):
        details.append(f"\n{TITLES[item.event.kind]} · {item.count} раз\nКонтекст: {item.event.context}\nИсточник: {item.event.source}")
        if item.peers: details.append("Адреса (до 5): " + ", ".join(sorted(item.peers)))
        details.extend(item.samples)
        if item.event.trace: details.append("Traceback (первый пример):\n" + item.event.trace)
    return summary, "\n".join(details)
