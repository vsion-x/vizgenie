"""
Streamlit notification system for background job events
Uses asyncio-safe queue for thread-safe UI updates
Python 3.12 compatible
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from enum import StrEnum  # Python 3.11+ native StrEnum
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)


class NotificationType(StrEnum):
    """Notification types"""
    UNKNOWN_PATTERN     = "unknown_pattern_detected"
    RCA_TRIGGERED       = "rca_triggered"
    RCA_COMPLETE        = "rca_complete"
    ANOMALY_DETECTED    = "anomaly_detected"
    ERROR               = "error"


class NotificationSeverity(StrEnum):
    """Notification severity levels"""
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"


@dataclass
class Notification:
    """Single notification item"""
    id:           str
    type:         NotificationType
    severity:     NotificationSeverity
    title:        str
    message:      str
    timestamp:    datetime                = field(default_factory=datetime.now)
    data:         Dict[str, Any]          = field(default_factory=dict)
    read:         bool                    = False
    action_label: Optional[str]           = None
    action_key:   Optional[str]           = None

    # ------------------------------------------------------------------ #
    # Convenience helpers                                                  #
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id":           self.id,
            "type":         self.type,
            "severity":     self.severity,
            "title":        self.title,
            "message":      self.message,
            "timestamp":    self.timestamp.isoformat(),
            "data":         self.data,
            "read":         self.read,
            "action_label": self.action_label,
            "action_key":   self.action_key,
        }


class NotificationStore:
    """
    Thread-safe notification store for Streamlit
    Uses deque for O(1) append / bounded memory
    """

    MAX_NOTIFICATIONS = 100

    def __init__(self) -> None:
        self._notifications: deque[Notification] = deque(maxlen=self.MAX_NOTIFICATIONS)
        self._unread_count: int = 0

    # ------------------------------------------------------------------ #
    # Write                                                                #
    # ------------------------------------------------------------------ #

    def add(self, notification: Notification) -> None:
        self._notifications.appendleft(notification)   # newest first
        if not notification.read:
            self._unread_count += 1

    # ------------------------------------------------------------------ #
    # Read                                                                 #
    # ------------------------------------------------------------------ #

    def get_all(self) -> list[Notification]:
        return list(self._notifications)

    def get_unread(self) -> list[Notification]:
        return [n for n in self._notifications if not n.read]

    @property
    def unread_count(self) -> int:
        return self._unread_count

    # ------------------------------------------------------------------ #
    # Mutate                                                               #
    # ------------------------------------------------------------------ #

    def mark_read(self, notification_id: str) -> None:
        for n in self._notifications:
            if n.id == notification_id and not n.read:
                n.read = True
                self._unread_count = max(0, self._unread_count - 1)
                break

    def mark_all_read(self) -> None:
        for n in self._notifications:
            n.read = True
        self._unread_count = 0

    def clear(self) -> None:
        self._notifications.clear()
        self._unread_count = 0


# ──────────────────────────────────────────────────────────────────────── #
#  RCA report store                                                         #
# ──────────────────────────────────────────────────────────────────────── #

class RCAReportStore:
    """Stores RCA reports for Streamlit display"""

    MAX_REPORTS = 50

    def __init__(self) -> None:
        self._reports: deque[Dict[str, Any]] = deque(maxlen=self.MAX_REPORTS)

    def add(self, report: Dict[str, Any]) -> None:
        report.setdefault("timestamp", datetime.now().isoformat())
        self._reports.appendleft(report)

    def get_all(self) -> list[Dict[str, Any]]:
        return list(self._reports)

    def get_latest(self) -> Optional[Dict[str, Any]]:
        return self._reports[0] if self._reports else None

    def clear(self) -> None:
        self._reports.clear()


# ──────────────────────────────────────────────────────────────────────── #
#  Global singletons                                                        #
# ──────────────────────────────────────────────────────────────────────── #

_notification_store = NotificationStore()
_rca_report_store   = RCAReportStore()
_id_counter         = 0

def get_notification_store() -> NotificationStore:
    return _notification_store


def get_rca_store() -> RCAReportStore:
    return _rca_report_store

    """Return (title, message, action_label, action_key)."""

    match notif_type:
        case NotificationType.UNKNOWN_PATTERN:
            count   = payload.get("count", 0)
            samples = payload.get("samples", [])
            title   = f"⚠️ {count} Unknown Log Pattern(s) Detected"
            message = (
                f"Found {count} log entries that don't match any known pattern.\n\n"
                f"**Sample logs:**\n"
                + "\n".join(f"- `{s[:100]}`" for s in samples[:3])
            )
            return title, message, "Learn Patterns", "start_learning"

        case NotificationType.ANOMALY_DETECTED:
            severity = payload.get("severity", "unknown").upper()
            atype    = payload.get("anomaly_type", "unknown")
            details  = payload.get("details", {})
            title    = f"🚨 {severity} Anomaly: {atype}"
            message  = (
                f"**Type**: {atype}\n"
                f"**Severity**: {severity}\n"
                f"**Details**: {details}\n"
                f"**Time**: {payload.get('timestamp', 'N/A')}"
            )
            return title, message, "View Details", f"anomaly_{atype}"

        case NotificationType.RCA_COMPLETE:
            atype   = payload.get("message", "unknown")
            title   = f"✅ RCA Complete: {atype}"
            message = (
                "Root cause analysis has completed.\n"
                "Check the RCA Reports tab for details and resolution steps."
            )
            return title, message, "View RCA Report", "view_rca"

        case NotificationType.RCA_TRIGGERED:
            title   = "🔍 RCA Investigation Started"
            message = f"Investigating: {payload.get('message', 'anomaly detected')}"
            return title, message, None, None

        case NotificationType.MONITOR_STARTED:
            ds = payload.get("datasource_uid", "unknown")
            return (
                f"✅ Monitor Started: {ds}",
                f"Background monitoring is now active for datasource {ds}.",
                None, None,
            )

        case NotificationType.MONITOR_STOPPED:
            ds = payload.get("datasource_uid", "unknown")
            return (
                f"⏹️ Monitor Stopped: {ds}",
                f"Background monitoring stopped for datasource {ds}.",
                None, None,
            )

        case NotificationType.PATTERN_LEARNED:
            count = payload.get("count", 0)
            return (
                f"🧠 {count} New Pattern(s) Learned",
                f"Successfully extracted and saved {count} log patterns.",
                None, None,
            )

        case NotificationType.ERROR:
            return (
                "❌ Error",
                payload.get("message", "An error occurred."),
                None, None,
            )

        case _:
            return (
                "ℹ️ Info",
                payload.get("message", ""),
                None, None,
            )