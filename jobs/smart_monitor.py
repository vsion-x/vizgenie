"""
# jobs/smart_monitor.py
Smart Monitor
Fetches logs from registered log sources every N seconds.
Triggers RCA agent on new / recurring errors.
"""

import asyncio
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Set

logger = logging.getLogger(__name__)


class SmartMonitor:
    """Pattern-based log monitor — source-agnostic."""

    STATS_FILE = Path("data/monitor_stats.json")

    def __init__(self) -> None:
        self.running   = False
        self.task: threading.Thread | None = None
        self.interval  = 20  # seconds

        # Track which error signatures have already had RCA generated
        self.seen_errors: Set[str] = set()

        # Trigger RCA when occurrence_count hits this
        self.rca_threshold = 5

        self.stats = {"total_logs": 0, "errors_found": 0, "rca_count": 0}
        self._last_fetch_time: datetime | None = None   # tracks sliding window
        self._load_stats()

    # ── lifecycle ────────────────────────────────────────────────────

    def start(self, interval: int = 20) -> None:
        if self.running and self.task and self.task.is_alive():
            logger.warning("Monitor already running")
            return
        self.interval = interval
        self.running  = True
        self.task     = threading.Thread(
            target=self._run_monitor_loop, daemon=True
        )
        self.task.start()
        logger.info(f"✅ Monitor started — checking every {interval}s")

    def stop(self) -> None:
        self.running = False
        logger.info("Monitor stopped")

    def is_running(self) -> bool:
        # Check both the flag AND thread liveness
        # Thread may still be alive even if flag was reset by a Streamlit rerun
        return self.running and self.task is not None and self.task.is_alive()

    def get_stats(self) -> Dict:
        return self.stats

    # ── internal loop ────────────────────────────────────────────────

    def _run_monitor_loop(self) -> None:
        asyncio.run(self._monitor_loop())

    async def _monitor_loop(self) -> None:
        from tools.error_analyzer    import get_error_analyzer
        from tools.log_source_manager import get_log_source_registry
        from datetime import timezone

        analyzer = get_error_analyzer()
        registry = get_log_source_registry()

        while self.running:
            try:
                now = datetime.now(timezone.utc)

                # First run: 1-minute lookback
                # Subsequent runs: exactly from where we left off + 5s buffer
                # to account for CloudWatch ingestion lag
                if self._last_fetch_time is None:
                    time_range = "1m"
                else:
                    elapsed = int((now - self._last_fetch_time).total_seconds()) + 5
                    time_range = f"{max(elapsed, 10)}s"  # minimum 10s window

                self._last_fetch_time = now   # record before fetch

                logger.info(
                    f"🔍 Monitor cycle — window: {time_range} "
                    f"| sources: {len(registry.list_sources())}"
                )

                logs = await registry.fetch_all_logs(
                    time_range=time_range,
                    filters=None,
                    limit=50,
                )

                logger.info(f"📦 Fetched {len(logs)} logs")

                if not logs:
                    logger.info("No logs — waiting…")
                    await asyncio.sleep(self.interval)
                    continue

                self.stats["total_logs"] += len(logs)

                new_errors, updated_errors = analyzer.analyze_logs(logs)
                logger.info(
                    f"📊 {len(new_errors)} new, {len(updated_errors)} updated"
                )

                if new_errors or updated_errors:
                    self.stats["errors_found"] += (
                        len(new_errors) + len(updated_errors)
                    )

                    # New errors → immediate RCA
                    for pattern in new_errors:
                        logger.info(f"🔍 New error: {pattern.error_type}")
                        await self._trigger_rca(pattern)

                    # Recurring errors → RCA when threshold reached
                    for pattern in updated_errors:
                        if (
                            pattern.occurrence_count >= self.rca_threshold
                            and not pattern.rca_generated
                        ):
                            logger.info(
                                f"🚨 Threshold reached: {pattern.error_type} "
                                f"(×{pattern.occurrence_count})"
                            )
                            await self._trigger_rca(pattern)
                        else:
                            logger.debug(
                                f"♻️  Recurring: {pattern.error_type} "
                                f"(×{pattern.occurrence_count})"
                            )
                else:
                    logger.info("✅ No new errors")

                self._save_stats()
                await asyncio.sleep(self.interval)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error(f"Monitor error: {exc}", exc_info=True)
                await asyncio.sleep(self.interval)

    # ── RCA trigger ──────────────────────────────────────────────────

    async def _trigger_rca(self, error_pattern) -> None:
        signature = f"{error_pattern.error_type}|{error_pattern.pattern_id}"

        if signature in self.seen_errors:
            logger.info(
                f"⏭️  Skipping duplicate RCA: {error_pattern.error_type}"
            )
            return

        self.seen_errors.add(signature)
        logger.info(f"🚨 Triggering RCA for: {error_pattern.error_type}")

        from graphs.rca_graph           import invoke_rca_agent
        from utils.streamlit_notifier   import get_rca_store
        from tools.log_source_manager   import get_log_source_registry

        registry = get_log_source_registry()

        context = {
            "error_pattern": {
                "pattern_id":        error_pattern.pattern_id,
                "error_type":        error_pattern.error_type,
                "error_code":        error_pattern.error_code,
                "error_message":     error_pattern.error_message,
                "stack_trace":       error_pattern.stack_trace,
                "affected_endpoints": error_pattern.affected_endpoints,
                "affected_modules":   error_pattern.affected_modules,
                "occurrence_count":  error_pattern.occurrence_count,
                "first_seen":        error_pattern.first_seen.isoformat(),
                "sample_logs": [
                    s.get("log", "") if isinstance(s, dict) else str(s)
                    for s in error_pattern.sample_logs
                ],
            },
            "anomaly": {
                "timestamp":      error_pattern.first_seen,
                "severity":       self._determine_severity(error_pattern),
                "severity_level": self._determine_severity_level(error_pattern),
                "anomaly_type":   "application_error",
                "details": {
                    "error_type":          error_pattern.error_type,
                    "error_message":       error_pattern.error_message,
                    "affected_components": len(error_pattern.affected_endpoints),
                },
                "evidence": {
                    "stack_trace":  error_pattern.stack_trace,
                    "sample_count": len(error_pattern.sample_logs),
                },
            },
            # Pass source names so RCA context knows what's available
            "available_datasources": registry.get_source_info(),
            "datasource_uid":   "",
            "datasource_type":  "cloudwatch",
            # Grafana fields disabled — kept empty for schema compat
            "grafana_url":     "",
            "grafana_api_key": "",
        }

        try:
            rca_result = await invoke_rca_agent(context)

            # Mark pattern as done
            from tools.error_analyzer import get_error_analyzer
            get_error_analyzer().mark_rca_generated(
                error_pattern.pattern_id, rca_result
            )

            # Store report for UI
            rca_store = get_rca_store()
            rca_store.add({
                "timestamp":  datetime.now().isoformat(),
                "error_type": error_pattern.error_type,
                "error_code": error_pattern.error_code,
                "pattern_id": error_pattern.pattern_id,
                "rca":        rca_result,
            })

            self.stats["rca_count"] += 1
            self._save_stats()
            logger.info(f"✅ RCA complete for {error_pattern.error_type}")

        except Exception as exc:
            logger.error(f"RCA generation failed: {exc}", exc_info=True)

    # ── severity helpers ─────────────────────────────────────────────

    def _determine_severity(self, p) -> str:
        t = p.error_type.lower()
        if any(x in t for x in ["memory", "oom", "fatal", "critical", "deadlock"]):
            return "critical"
        if any(x in t for x in ["database", "connection", "timeout", "null"]):
            return "high"
        if p.occurrence_count >= 10:
            return "high"
        if p.occurrence_count >= 5:
            return "medium"
        return "medium"

    def _determine_severity_level(self, p) -> int:
        return {"critical": 1, "high": 2, "medium": 3, "low": 4}.get(
            self._determine_severity(p), 3
        )

    # ── stats persistence ────────────────────────────────────────────

    def _load_stats(self) -> None:
        """
        Load stats and last fetch time from disk.

        File structure:
            {
                "stats": {"total_logs": 0, "errors_found": 0, "rca_count": 0},
                "last_fetch_time": "2026-02-18T22:24:52+00:00"
            }

        NOTE: stats are stored under a "stats" key — NOT at the top level.
        This lets us add other top-level keys (like last_fetch_time) without
        polluting the stats dict that get_stats() returns to the UI.
        """
        if not self.STATS_FILE.exists():
            return
        try:
            data = json.loads(self.STATS_FILE.read_text())

            # stats live under "stats" key
            self.stats = data.get(
                "stats",
                {"total_logs": 0, "errors_found": 0, "rca_count": 0},
            )

            # restore last fetch position for sliding window
            last_time = data.get("last_fetch_time")
            if last_time:
                from datetime import timezone
                dt = datetime.fromisoformat(last_time)
                # ensure timezone-aware so arithmetic with datetime.now(utc) works
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                self._last_fetch_time = dt
                logger.debug(f"Restored last_fetch_time: {self._last_fetch_time}")

        except Exception as exc:
            logger.warning(f"Could not load stats — starting fresh: {exc}")
            self.stats = {"total_logs": 0, "errors_found": 0, "rca_count": 0}
            self._last_fetch_time = None

    def _save_stats(self) -> None:
        """
        Persist stats and last fetch time.
        Wraps stats under a "stats" key so _load_stats can find them unambiguously.
        """
        self.STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            data: dict = {
                "stats": self.stats,   # nested — matches _load_stats expectation
            }
            if self._last_fetch_time is not None:
                data["last_fetch_time"] = self._last_fetch_time.isoformat()

            self.STATS_FILE.write_text(json.dumps(data, indent=2))
        except Exception as exc:
            logger.error(f"Failed to save stats: {exc}")


# ── global singleton ──────────────────────────────────────────────────
# @st.cache_resource persists the instance across Streamlit script reruns
# within a single browser session — this keeps the monitor thread alive.

try:
    import streamlit as st

    @st.cache_resource
    def get_monitor() -> SmartMonitor:
        return SmartMonitor()

except ImportError:
    # Non-Streamlit context (tests, CLI)
    _monitor: SmartMonitor | None = None

    def get_monitor() -> SmartMonitor:  # type: ignore[misc]
        global _monitor
        if _monitor is None:
            _monitor = SmartMonitor()
        return _monitor