"""
# jobs/smart_monitor.py
Smart Monitor
Lightweight monitoring using learned patterns
Triggers RCA for new errors
"""

import logging
import asyncio
import threading
from typing import Dict, Set
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class SmartMonitor:
    """Simple pattern-based monitor"""
    
    STATS_FILE = Path("data/monitor_stats.json")
    
    def __init__(self):
        self.running = False
        self.task = None
        self.loki_url = ""
        self.interval = 15
        
        # ✅ FIX: Store credentials during init (before thread starts)
        self.grafana_url = ""
        self.grafana_api_key = ""
        self.datasources = []
        self.loki_uid = ""
        
        # Track seen errors to avoid duplicate RCAs
        self.seen_errors: Set[str] = set()
        
        # RCA threshold - trigger RCA when error count reaches this
        self.rca_threshold = 5
        
        # Stats
        self.stats = {
            "total_logs": 0,
            "errors_found": 0,
            "rca_count": 0,
        }
        
        self._load_stats()
    
    def _load_stats(self):
        """Load stats from disk"""
        if self.STATS_FILE.exists():
            try:
                self.stats = json.loads(self.STATS_FILE.read_text())
            except:
                pass
    
    def _save_stats(self):
        """Save stats to disk"""
        self.STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.STATS_FILE.write_text(json.dumps(self.stats, indent=2))
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")
    
    def start(self, loki_url: str, interval: int):
        """Start monitoring"""
        if self.running:
            logger.warning("Monitor already running")
            return
        
        self.loki_url = loki_url
        self.interval = interval
        self.running = True
        
        # ✅ FIX: Get credentials NOW (in main thread) before starting background thread
        self._cache_credentials()
        
        # Start background thread
        self.task = threading.Thread(target=self._run_monitor_loop, daemon=True)
        self.task.start()
        
        logger.info(f"✅ Monitor started — checking every {interval}s")
    
    def _cache_credentials(self):
        """Cache credentials from session state before thread starts"""
        try:
            import streamlit as st
            
            self.grafana_url = st.session_state.get("grafana_url", "")
            self.grafana_api_key = st.session_state.get("grafana_api_key", "")
            self.datasources = st.session_state.get("available_datasources", [])
            
            # Get Loki UID
            for ds in self.datasources:
                if ds.get("type") == "loki":
                    self.loki_uid = ds.get("uid", "")
                    break
            
            logger.info(f"Cached credentials: Grafana={'present' if self.grafana_url else 'missing'}, Loki UID={self.loki_uid}")
        
        except Exception as e:
            logger.error(f"Failed to cache credentials: {e}")
    
    def _run_monitor_loop(self):
        """Run monitor loop in thread"""
        asyncio.run(self._monitor_loop())
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Monitor stopped")
    
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self.running
    
    def get_stats(self) -> Dict:
        """Get monitor stats"""
        return self.stats
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        from tools.loki_tools import query_loki_logs
        from tools.error_analyzer import get_error_analyzer
        
        analyzer = get_error_analyzer()
        
        while self.running:
            try:
                logger.info(f"🔍 Monitor cycle starting (interval: {self.interval}s)...")
                
                # Fetch logs
                logs = await query_loki_logs(
                    loki_url=self.loki_url,
                    filter='{container=~".+"}',
                    time_range="1m",
                    limit=50
                )
                
                logger.info(f"📦 Fetched {len(logs) if logs else 0} logs")
                
                if not logs:
                    logger.info("No logs found, waiting...")
                    await asyncio.sleep(self.interval)
                    continue
                
                self.stats["total_logs"] += len(logs)
                logger.info(f"📈 Total logs checked so far: {self.stats['total_logs']}")
                
                # Analyze logs
                new_errors, updated_errors = analyzer.analyze_logs(logs)
                
                logger.info(f"📊 Analysis complete: {len(new_errors)} new, {len(updated_errors)} updated")
                
                if new_errors or updated_errors:
                    self.stats["errors_found"] += len(new_errors) + len(updated_errors)
                    logger.info(f"🚨 Found errors (total: {self.stats['errors_found']})")
                    
                    # Trigger RCA for NEW errors
                    for error_pattern in new_errors:
                        logger.info(f"🔍 Processing NEW error: {error_pattern.error_type}")
                        await self._trigger_rca(error_pattern)
                    
                    # Trigger RCA for recurring errors crossing threshold
                    for error_pattern in updated_errors:
                        if (error_pattern.occurrence_count >= self.rca_threshold and 
                            not error_pattern.rca_generated):
                            logger.info(f"🚨 THRESHOLD REACHED: {error_pattern.error_type} (×{error_pattern.occurrence_count})")
                            await self._trigger_rca(error_pattern)
                        else:
                            logger.info(f"♻️ Recurring error: {error_pattern.error_type} (×{error_pattern.occurrence_count})")
                else:
                    logger.info("✅ No new errors found in this cycle")
                
                self._save_stats()
                
                await asyncio.sleep(self.interval)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}", exc_info=True)
                await asyncio.sleep(self.interval)
    
    async def _trigger_rca(self, error_pattern):
        """Trigger RCA for a new error pattern"""
        
        signature = f"{error_pattern.error_type}|{error_pattern.pattern_id}"
        
        if signature in self.seen_errors:
            logger.info(f"⏭️ Skipping RCA for already analyzed pattern: {error_pattern.error_type}")
            return
        
        self.seen_errors.add(signature)
        
        logger.info(f"🚨 Triggering RCA for error: {error_pattern.error_type}")
        
        from graphs.rca_graph import invoke_rca_agent
        from utils.streamlit_notifier import get_rca_store
        
        # ✅ FIX: Use cached credentials instead of accessing session state
        context = {
            "error_pattern": {
                "pattern_id": error_pattern.pattern_id,
                "error_type": error_pattern.error_type,
                "error_code": error_pattern.error_code,
                "error_message": error_pattern.error_message,
                "stack_trace": error_pattern.stack_trace,
                "affected_endpoints": error_pattern.affected_endpoints,
                "affected_modules": error_pattern.affected_modules,
                "occurrence_count": error_pattern.occurrence_count,
                "first_seen": error_pattern.first_seen.isoformat(),
                "sample_logs": [s.get("log", "") for s in error_pattern.sample_logs],
            },
            "anomaly": {
                "timestamp": error_pattern.first_seen,
                "severity": self._determine_severity(error_pattern),
                "severity_level": self._determine_severity_level(error_pattern),
                "anomaly_type": "application_error",
                "details": {
                    "error_type": error_pattern.error_type,
                    "error_message": error_pattern.error_message,
                    "affected_components": len(error_pattern.affected_endpoints),
                },
                "evidence": {
                    "stack_trace": error_pattern.stack_trace,
                    "sample_count": len(error_pattern.sample_logs),
                },
            },
            # ✅ FIX: Use cached values instead of async getters
            "available_datasources": self.datasources,
            "datasource_uid": self.loki_uid,
            "datasource_type": "loki",
            "grafana_url": self.grafana_url,
            "grafana_api_key": self.grafana_api_key,
        }
        
        try:
            rca_result = await invoke_rca_agent(context)
            
            # Mark pattern as RCA generated
            from tools.error_analyzer import get_error_analyzer
            analyzer = get_error_analyzer()
            analyzer.mark_rca_generated(error_pattern.pattern_id, rca_result)
            
            # Store RCA
            rca_store = get_rca_store()
            rca_store.add({
                "timestamp": datetime.now().isoformat(),
                "error_type": error_pattern.error_type,
                "error_code": error_pattern.error_code,
                "pattern_id": error_pattern.pattern_id,
                "rca": rca_result,
            })
            
            self.stats["rca_count"] += 1
            self._save_stats()
            
            logger.info(f"✅ RCA generated for {error_pattern.error_type}")
        
        except Exception as e:
            logger.error(f"RCA generation failed: {e}", exc_info=True)
    
    def _determine_severity(self, error_pattern) -> str:
        """Determine severity based on error type and count"""
        error_type_lower = error_pattern.error_type.lower()
        
        if any(x in error_type_lower for x in ["memory", "oom", "fatal", "critical", "deadlock"]):
            return "critical"
        
        if any(x in error_type_lower for x in ["database", "connection", "timeout", "null"]):
            return "high"
        
        if error_pattern.occurrence_count >= 10:
            return "high"
        elif error_pattern.occurrence_count >= 5:
            return "medium"
        
        return "medium"
    
    def _determine_severity_level(self, error_pattern) -> int:
        """Map severity to numeric level"""
        severity_map = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        severity = self._determine_severity(error_pattern)
        return severity_map.get(severity, 3)


# ── Global instance ────────────────────────────────────────────────────

_monitor = None

def get_monitor() -> SmartMonitor:
    global _monitor
    if _monitor is None:
        _monitor = SmartMonitor()
    return _monitor