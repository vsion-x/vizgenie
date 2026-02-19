"""
# tools/log_source_manager.py
Generic log source manager — cloud-agnostic
Supports: AWS CloudWatch (active), Datadog / New Relic (stubs)
Includes persistence so credentials survive Streamlit reruns.
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone   # ✅ timezone required for UTC fix
from pathlib import Path
from typing import Dict, List, Optional
import re

logger = logging.getLogger(__name__)

SOURCES_FILE = Path("data/log_sources.json")


# ══════════════════════════════════════════════════════════════════════
#  Abstract base
# ══════════════════════════════════════════════════════════════════════

class LogSource(ABC):
    """Abstract base for all log sources."""

    SOURCE_TYPE: str = "base"

    @abstractmethod
    async def fetch_logs(self, time_range: str, filters: Optional[Dict] = None, limit: int = 100) -> List[Dict]:
        """Returns list of dicts: {timestamp, log, level, ...}"""

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Returns (success, message)."""

    @abstractmethod
    def to_config(self) -> Dict:
        """Serialise to JSON-safe dict for persistence."""

    @classmethod
    @abstractmethod
    def from_config(cls, config: Dict) -> "LogSource":
        """Deserialise from persisted config dict."""

    def _parse_time_range(self, time_range: str) -> tuple[datetime, datetime]:
        """
        Parse time range string into (start, end) as timezone-aware UTC datetimes.

        IMPORTANT: Uses datetime.now(timezone.utc) NOT datetime.utcnow().
        utcnow() returns a naive datetime; Python's .timestamp() then treats it as
        LOCAL time, sending a wrong epoch ms to CloudWatch on non-UTC servers
        (e.g. IST UTC+5:30 shifts end_ms 5.5h into the future → MalformedQueryException).

        5-second buffer prevents CloudWatch rejecting queries where end_time
        lands exactly on 'now' due to clock skew between app server and AWS.
        """
        match = re.match(r"(\d+)([smhd])", time_range)
        if not match:
            delta = timedelta(hours=1)
        else:
            value, unit = int(match.group(1)), match.group(2)
            delta = {
                "s": timedelta(seconds=value),
                "m": timedelta(minutes=value),
                "h": timedelta(hours=value),
                "d": timedelta(days=value),
            }[unit]

        end   = datetime.now(timezone.utc) - timedelta(seconds=5)  # ✅ timezone-aware UTC
        start = end - delta
        return start, end


# ══════════════════════════════════════════════════════════════════════
#  CloudWatch - AWS Standard Authentication
# ══════════════════════════════════════════════════════════════════════

class CloudWatchSource(LogSource):
    """
    AWS CloudWatch Logs source via boto3.

    Uses standard AWS credential names:
    - AWS_ACCESS_KEY_ID
    - AWS_SECRET_ACCESS_KEY
    - AWS_SESSION_TOKEN (optional, for STS temporary credentials)
    """

    SOURCE_TYPE = "cloudwatch"

    def __init__(
        self,
        aws_access_key_id:     str,
        aws_secret_access_key: str,
        region:                str,
        log_group_names:       List[str],
        aws_session_token:     Optional[str] = None,
    ) -> None:
        self.aws_access_key_id     = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_session_token     = aws_session_token or None
        self.region                = region
        if isinstance(log_group_names, str):
            log_group_names = [log_group_names]
        self.log_group_names = log_group_names
        self._client         = None

    # ── serialise ───────────────────────────────────────────────────

    def to_config(self) -> Dict:
        cfg = {
            "type":                  self.SOURCE_TYPE,
            "aws_access_key_id":     self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
            "region":                self.region,
            "log_group_names":       self.log_group_names,
        }
        if self.aws_session_token:
            cfg["aws_session_token"] = self.aws_session_token
        return cfg

    @classmethod
    def from_config(cls, config: Dict) -> "CloudWatchSource":
        """
        Load from saved config.
        Falls back to old key names (access_key_id / secret_access_key) so
        existing data/log_sources.json files load without requiring re-configuration.
        """
        return cls(
            aws_access_key_id=config.get(
                "aws_access_key_id", config.get("access_key_id", "")
            ),
            aws_secret_access_key=config.get(
                "aws_secret_access_key", config.get("secret_access_key", "")
            ),
            region=config["region"],
            log_group_names=config.get("log_group_names", []),
            aws_session_token=config.get("aws_session_token"),
        )

    # ── boto3 client ─────────────────────────────────────────────────

    def _get_client(self):
        """
        Lazy-init boto3 CloudWatch Logs client.
        Session token is only injected when present — passing None to boto3 causes auth failure.
        """
        if self._client is None:
            import boto3

            session_config = {
                "aws_access_key_id":     self.aws_access_key_id,
                "aws_secret_access_key": self.aws_secret_access_key,
                "region_name":           self.region,
            }
            if self.aws_session_token:
                session_config["aws_session_token"] = self.aws_session_token

            self._client = boto3.client("logs", **session_config)

            cred_type = "temporary (STS)" if self.aws_session_token else "long-term (IAM)"
            logger.info(
                f"✅ Initialized CloudWatch client for region {self.region} ({cred_type})"
            )

        return self._client

    # ── connection test ──────────────────────────────────────────────

    async def test_connection(self) -> tuple[bool, str]:
        """
        Verify credentials and that EVERY configured log group exists with exact name matching.

        Why exact match matters: describe_log_groups uses prefix search, so searching
        'my-app' also returns 'my-app-staging'. A prefix match passing here but failing
        in start_query() with MalformedQueryException is confusing to debug.

        Also reports retention period for each group so users know their valid query window.
        """
        try:
            client = self._get_client()
            confirmed: list[str] = []
            missing:   list[str] = []

            for group in self.log_group_names:
                resp  = client.describe_log_groups(logGroupNamePrefix=group, limit=5)
                found = resp.get("logGroups", [])

                # Exact match required
                exact = [g for g in found if g["logGroupName"] == group]

                if exact:
                    retention = exact[0].get("retentionInDays", "Never expire")
                    confirmed.append(f"{group} (retention: {retention}d)")
                    logger.info(f"✅ Log group confirmed: {group} | retention: {retention}d")
                else:
                    missing.append(group)
                    suggestions = [g["logGroupName"] for g in found[:3]]
                    if suggestions:
                        logger.warning(
                            f"⚠️  Log group '{group}' not found. "
                            f"Similar groups in AWS: {suggestions}"
                        )
                    else:
                        logger.warning(f"⚠️  Log group '{group}' not found in {self.region}")

            if missing:
                return False, (
                    f"Log group(s) not found: {missing}. "
                    "Check exact name in AWS Console → CloudWatch → Log groups. "
                    "Names are case-sensitive and may need a leading '/' "
                    "(e.g. /aws/lambda/my-function)."
                )

            return True, f"✅ Connected — {len(confirmed)} group(s): {', '.join(confirmed)}"

        except Exception as exc:
            error_msg = str(exc)
            if "InvalidClientTokenId" in error_msg or "SignatureDoesNotMatch" in error_msg:
                return False, "❌ Invalid AWS credentials (check access key ID and secret key)"
            elif "ExpiredToken" in error_msg:
                return False, "❌ AWS session token has expired — generate new temporary credentials"
            elif "AccessDenied" in error_msg:
                return False, "❌ Access denied — IAM user/role lacks CloudWatch Logs permissions"
            elif "UnrecognizedClientException" in error_msg:
                return False, f"❌ Invalid region '{self.region}' or credentials"
            else:
                return False, f"❌ Connection failed: {error_msg}"

    # ── fetch logs ───────────────────────────────────────────────────

    async def fetch_logs(
        self,
        time_range: str = "1h",
        filters:    Optional[Dict] = None,
        limit:      int = 100,
    ) -> List[Dict]:
        """
        Fetch logs from CloudWatch Logs Insights.

        Flow:
          1. _parse_time_range() → UTC-aware start/end → epoch ms
          2. start_query()       → queryId (async job, returns immediately)
          3. Poll get_query_results() every 1s until status=Complete (max 30s)
          4. Normalize field-dict records → standard log dicts
        """
        import asyncio

        client = self._get_client()
        start_time, end_time = self._parse_time_range(time_range)

        start_ms = int(start_time.timestamp() * 1000)
        end_ms   = int(end_time.timestamp()   * 1000)

        # Log actual UTC window — makes timezone issues immediately visible
        logger.info(
            f"CloudWatch query window: "
            f"{start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} → "
            f"{end_time.strftime('%Y-%m-%d %H:%M:%S UTC')} "
            f"({start_ms} → {end_ms} ms)"
        )

        query    = self._build_query(filters, limit)
        all_logs: List[Dict] = []

        for group in self.log_group_names:
            try:
                logger.info(f"📡 Starting CloudWatch query for log group: {group}")

                resp     = client.start_query(
                    logGroupName=group,
                    startTime=start_ms,
                    endTime=end_ms,
                    queryString=query,
                    limit=limit,
                )
                query_id = resp["queryId"]
                logger.debug(f"Query ID: {query_id}")

                for attempt in range(30):
                    result = client.get_query_results(queryId=query_id)
                    status = result["status"]

                    if status == "Complete":
                        logger.info(f"✅ Query complete for {group}")
                        break
                    elif status in ("Failed", "Cancelled"):
                        logger.error(f"❌ Query {status} for {group}")
                        break

                    await asyncio.sleep(1)
                else:
                    logger.error(f"⏱️ Query timeout for {group} (30s limit)")
                    continue

                # CloudWatch result format: [[{"field": "@timestamp", "value": "..."}, ...], ...]
                records = result.get("results", [])
                logger.info(f"📦 Fetched {len(records)} logs from {group}")

                for record in records:
                    entry: Dict = {"_source": "cloudwatch", "_log_group": group}

                    for field in record:
                        name, value = field["field"], field["value"]
                        if name == "@timestamp":
                            entry["timestamp"] = value
                        elif name == "@message":
                            entry["log"] = value
                        elif name == "@logStream":
                            entry["_log_stream"] = value
                        else:
                            entry[name] = value

                    if "log" in entry:
                        entry["level"] = self._extract_level(entry["log"])

                    all_logs.append(entry)

            except Exception as exc:
                err_str = str(exc)

                if "MalformedQueryException" in err_str:
                    # Common cause: time window outside log group's retention period.
                    # If UTC fix is applied, this means the group genuinely has
                    # shorter retention than the requested time_range.
                    logger.error(
                        f"❌ CloudWatch time window rejected for '{group}':\n"
                        f"   {err_str}\n"
                        f"   Query window: "
                        f"{start_time.strftime('%Y-%m-%d %H:%M UTC')} → "
                        f"{end_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
                        f"   Check the log group's retention period in AWS Console."
                    )
                else:
                    logger.error(f"❌ CloudWatch fetch failed for '{group}': {exc}")

        logger.info(f"📊 Total logs fetched: {len(all_logs)}")
        return all_logs

    # ── helpers ──────────────────────────────────────────────────────

    def _build_query(self, filters: Optional[Dict], limit: int) -> str:
        """Build CloudWatch Logs Insights query string."""
        q = "fields @timestamp, @message, @logStream, @log"
        if filters and filters.get("level"):
            q += f" | filter level = '{filters['level']}'"
        q += " | sort @timestamp desc"
        return q

    @staticmethod
    def _extract_level(text: str) -> str:
        """Extract log level from unstructured log text (critical → debug priority)."""
        upper = text.upper()
        for lvl in ("CRITICAL", "ERROR", "WARNING", "WARN", "INFO", "DEBUG"):
            if lvl in upper:
                return lvl
        return "INFO"


# ══════════════════════════════════════════════════════════════════════
#  Registry
# ══════════════════════════════════════════════════════════════════════

_SOURCE_REGISTRY: Dict[str, type] = {
    CloudWatchSource.SOURCE_TYPE: CloudWatchSource
}


class LogSourceRegistry:
    """Global in-memory registry with JSON persistence. Singleton."""

    _instance: Optional["LogSourceRegistry"] = None

    def __new__(cls) -> "LogSourceRegistry":
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.sources: Dict[str, LogSource] = {}
            inst._load()
            cls._instance = inst
        return cls._instance

    def add_source(self, name: str, source: LogSource) -> None:
        self.sources[name] = source
        self._save()
        logger.info(f"Registered log source: {name} ({source.SOURCE_TYPE})")

    def remove_source(self, name: str) -> None:
        if name in self.sources:
            del self.sources[name]
            self._save()
            logger.info(f"Removed log source: {name}")

    def get_source(self, name: str) -> Optional[LogSource]:
        return self.sources.get(name)

    def list_sources(self) -> List[str]:
        return list(self.sources.keys())

    def clear(self) -> None:
        self.sources.clear()
        self._save()

    async def fetch_all_logs(
        self,
        time_range: str = "1h",
        filters:    Optional[Dict] = None,
        limit:      int = 100,
    ) -> List[Dict]:
        """Fetch from every registered source and merge."""
        all_logs: List[Dict] = []

        for name, source in self.sources.items():
            try:
                logs = await source.fetch_logs(time_range, filters, limit)
                for log in logs:
                    log.setdefault("_source", name)
                all_logs.extend(logs)
                logger.info(f"Fetched {len(logs)} logs from '{name}'")
            except NotImplementedError:
                logger.warning(f"Source '{name}' not implemented yet — skipping")
            except Exception as exc:
                logger.error(f"Failed to fetch from '{name}': {exc}")

        logger.info(f"Total logs fetched: {len(all_logs)}")
        return all_logs

    def _save(self) -> None:
        SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {name: src.to_config() for name, src in self.sources.items()}
            SOURCES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            logger.debug(f"Saved {len(data)} log source(s) to {SOURCES_FILE}")
        except Exception as exc:
            logger.error(f"Failed to save log sources: {exc}")

    def _load(self) -> None:
        if not SOURCES_FILE.exists():
            return
        try:
            data: Dict = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
            for name, config in data.items():
                source_type = config.get("type", "")
                cls = _SOURCE_REGISTRY.get(source_type)
                if cls is None:
                    logger.warning(f"Unknown source type '{source_type}' for '{name}' — skipping")
                    continue
                try:
                    self.sources[name] = cls.from_config(config)
                    logger.info(f"Loaded log source: {name} ({source_type})")
                except Exception as exc:
                    logger.error(f"Failed to load source '{name}': {exc}")
        except Exception as exc:
            logger.error(f"Failed to read {SOURCES_FILE}: {exc}")

    def get_source_info(self) -> List[Dict]:
        return [
            {
                "name":   name,
                "type":   src.SOURCE_TYPE,
                "groups": getattr(src, "log_group_names", []),
                "region": getattr(src, "region", "N/A"),
            }
            for name, src in self.sources.items()
        ]


def get_log_source_registry() -> LogSourceRegistry:
    return LogSourceRegistry()