"""
VizGenie - Main Streamlit application
Python 3.12 compatible
"""

import asyncio
import logging
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# ──────────────────────────────────────────────────────────────────────── #
#  Page config MUST be the very first Streamlit call                        #
# ──────────────────────────────────────────────────────────────────────── #

st.set_page_config(
    page_title="VizGenie",
    page_icon="🎩",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────── #
#  Bootstrap                                                                #
# ──────────────────────────────────────────────────────────────────────── #

load_dotenv()

from utils.logger import setup_logging
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_to_file=True,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────── #
#  CSS                                                                      #
# ──────────────────────────────────────────────────────────────────────── #

st.markdown("""
<style>
/* ── General ─────────────────────────────── */
.stApp { background-color: #f8f9fa; }

/* ── Sidebar ─────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #e9ecef;
}

/* ── Buttons ─────────────────────────────── */
.stButton > button {
    background-color : #4CAF50 !important;
    color            : white   !important;
    border           : 1px solid #45a049 !important;
    border-radius    : 8px     !important;
    font-weight      : 500     !important;
    transition       : all 0.2s ease !important;
}
.stButton > button:hover {
    background-color : #45a049 !important;
    transform        : translateY(-1px);
    box-shadow       : 0 2px 6px rgba(0,0,0,.15) !important;
}

/* ── Metric cards ─────────────────────────── */
[data-testid="metric-container"] {
    background    : #ffffff;
    border        : 1px solid #e9ecef;
    border-radius : 8px;
    padding       : 12px;
    box-shadow    : 0 1px 3px rgba(0,0,0,.05);
}

/* ── Notification badge ───────────────────── */
.notif-badge {
    background    : #ff4444;
    color         : white;
    border-radius : 50%;
    padding       : 0 6px;
    font-size     : 11px;
    font-weight   : bold;
    margin-left   : 4px;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────── #
#  Session-state initialisation                                             #
# ──────────────────────────────────────────────────────────────────────── #

_DEFAULTS: dict = {
    # Credentials
    "groq_api_key":       "",
    "grafana_url":        "",
    "grafana_api_key":    "",
    "prometheus_url":     "",
    "postgres_url":       "",
    "loki_url":           "",
    # Validation flags
    "groq_validated":     False,
    "grafana_validated":  False,
    # Datasources
    "available_datasources": [],
    # UI
    "active_page":        "home",  # Changed from "dashboard" to "home"
    "trigger_learning":   False,
    "selected_rca_report": 0,
    # Misc
    "dummy_loaded":       False,
    "grafana_datasources": [],
}


def _init_session() -> None:
    for key, default in _DEFAULTS.items():
        st.session_state.setdefault(key, default)


# ──────────────────────────────────────────────────────────────────────── #
#  Async helper                                                             #
# ──────────────────────────────────────────────────────────────────────── #

def _run_async(coro):
    """
    Streamlit runs in a non-main thread on Windows.
    asyncio.get_event_loop() raises RuntimeError there.
    Solution: always create a fresh event loop in the thread.
    """
    import asyncio

    try:
        # Try getting the running loop (works if called from async context)
        loop = asyncio.get_running_loop()
        import concurrent.futures
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=60)
    except RuntimeError:
        # No running loop (Streamlit script thread on Windows) — create one
        return asyncio.run(coro)


# ──────────────────────────────────────────────────────────────────────── #
#  Sidebar navigation                                                       #
# ──────────────────────────────────────────────────────────────────────── #

def _render_sidebar() -> None:
    with st.sidebar:

        if Path("assets/vizgenielogo.svg").exists():
            st.image("assets/vizgenielogo.svg", width=180)
        else:
            st.title("🎩 VizGenie")
        st.caption("Natural Language → Grafana Dashboards")
        st.divider()

        pages = {
            "🏠 Home": "home",
            "🔌 Connections": "connections",
            "📜 Loki": "loki",
        }

        for label, key in pages.items():
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state["active_page"] = key

        st.divider()

        # Connection status strip
        _render_sidebar_status()


def _render_sidebar_status() -> None:
    st.caption("**Connection Status**")

    statuses = {
        "Groq":       st.session_state.get("groq_validated",    False),
        "Grafana":    st.session_state.get("grafana_validated",  False),
        "Prometheus": bool(st.session_state.get("prometheus_url")),
        "PostgreSQL": bool(st.session_state.get("postgres_url")),
        "Loki":       bool(st.session_state.get("loki_url")),
    }

    for name, ok in statuses.items():
        icon = "🟢" if ok else "🔴"
        required = " *" if name in ("Groq", "Grafana") else ""
        st.caption(f"{icon} {name}{required}")

    st.caption("\\* mandatory")


# ──────────────────────────────────────────────────────────────────────── #
#  Connection settings page                                                 #
# ──────────────────────────────────────────────────────────────────────── #

def _render_connections() -> None:
    st.header("🔐 Connection Settings")
    st.caption("Groq and Grafana are **mandatory**. All others are optional.")

    # ── Mandatory ──────────────────────────────────────────────────────
    st.subheader("Mandatory Services")
    col_groq, col_grafana = st.columns(2)

    with col_groq:
        _render_groq_config()

    with col_grafana:
        _render_grafana_config()

    st.divider()

    # ── Optional ───────────────────────────────────────────────────────
    st.subheader("Optional Datasources")

    with st.expander("📈 Prometheus"):
        _render_prometheus_config()

    with st.expander("🗄️ PostgreSQL"):
        _render_postgres_config()

    with st.expander("📜 Loki"):
        _render_loki_config()

    st.divider()
    
    st.subheader("⚠️ Reset")
    if st.button("🗑️ Clear All Connections", type="secondary"):
        from utils.credentials_store import clear_credentials
        clear_credentials()
        st.success("✅ All credentials cleared")
        st.rerun()
    
    
    # ── Save ───────────────────────────────────────────────────────────
    if st.session_state.get("grafana_datasources") and st.button(
            "Save Settings", key="btn_save_settings"
        ):
            mapped_ds_list = []

            for ds in st.session_state["grafana_datasources"]:
                ds_type = ds.get("type", "").lower()

                session_key_map = {
                    "prometheus": "prometheus_url",
                    "loki":       "loki_url",
                    "postgres":   "postgres_url",
                }

                ds_copy      = ds.copy()
                session_key  = session_key_map.get(ds_type)

                if session_key and st.session_state.get(session_key):
                    ds_copy["url"] = st.session_state[session_key]

                mapped_ds_list.append(ds_copy)

            _auto_register_datasources(mapped_ds_list)
            from utils.credentials_store import save_credentials
            save_credentials()
            st.success("✅ Settings saved")

            # ── Load Prometheus metrics into VectorDB after UID is known ───
            if st.session_state.pop("pending_metrics_load", False):
                prom_url = st.session_state.get("prometheus_url", "")
                prom_uid = next(
                    (ds["uid"] for ds in st.session_state.get("available_datasources", [])
                    if ds.get("type") == "prometheus"),
                    None,
                )
                if prom_url and prom_uid:
                    _load_prometheus_metrics(prom_url, prom_uid)

            # ── Always re-load if Prometheus already registered ────────────
            else:
                prom_url = st.session_state.get("prometheus_url", "")
                prom_uid = next(
                    (ds["uid"] for ds in st.session_state.get("available_datasources", [])
                    if ds.get("type") == "prometheus"),
                    None,
                )
                if prom_url and prom_uid:
                    _load_prometheus_metrics(prom_url, prom_uid)


def _render_groq_config() -> None:
    import aiohttp

    with st.container(border=True):
        st.markdown("**🤖 Groq (LLM)**")

        key = st.text_input(
            "API Key",
            type="password",
            value=st.session_state["groq_api_key"],
            placeholder="gsk_…",
            key="groq_key_widget",
        )

        if st.button("Test Groq", key="btn_test_groq"):
            from utils.validators import validate_groq_key
            valid, err = validate_groq_key(key)

            if not valid:
                st.error(f"❌ {err}")
                st.session_state["groq_validated"] = False
            else:
                # Live API test
                async def _test():
                    url  = "https://api.groq.com/openai/v1/chat/completions"
                    hdrs = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type":  "application/json",
                    }
                    payload = {
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 5,
                    }
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=payload, headers=hdrs, timeout=aiohttp.ClientTimeout(total=10)) as r:
                            return r.status

                status = _run_async(_test())

                if status == 200:
                    st.session_state["groq_api_key"]   = key
                    st.session_state["groq_validated"] = True
                    # Initialise LLM handler
                    from llm.retry_handler import initialize_llm_handler
                    initialize_llm_handler(key.split(","))
                    from utils.credentials_store import save_credentials
                    save_credentials()
                    st.success("✅ Groq connected")
                else:
                    st.session_state["groq_validated"] = False
                    st.error(f"❌ Groq returned HTTP {status}")

        icon = "🟢" if st.session_state["groq_validated"] else "🔴"
        st.caption(f"{icon} Status")


def _render_grafana_config() -> None:
    import aiohttp

    with st.container(border=True):
        st.markdown("**📊 Grafana**")

        g_url = st.text_input(
            "URL",
            value=st.session_state["grafana_url"],
            placeholder="http://localhost:3000",
            key="grafana_url_widget",
        )
        g_key = st.text_input(
            "API Key",
            type="password",
            value=st.session_state["grafana_api_key"],
            placeholder="glsa_…",
            key="grafana_key_widget",
        )

        if st.button("Test Grafana", key="btn_test_grafana"):
            from utils.validators import validate_url, validate_grafana_key

            url_ok, url_err = validate_url(g_url)
            key_ok, key_err = validate_grafana_key(g_key)

            if not url_ok:
                st.error(f"❌ URL: {url_err}")
            elif not key_ok:
                st.error(f"❌ Key: {key_err}")
            else:
                async def _test():
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            f"{g_url}/api/datasources",
                            headers={"Authorization": f"Bearer {g_key}"},
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as r:
                            return r.status, await r.json() if r.status == 200 else []

                status, ds_list = _run_async(_test())

                if status == 200:
                    st.session_state.update({
                        "grafana_url":       g_url,
                        "grafana_api_key":   g_key,
                        "grafana_validated": True,
                    })

                    st.session_state["grafana_datasources"] = ds_list

                    from utils.credentials_store import save_credentials
                    save_credentials()

                    st.success(f"✅ Grafana connected — {len(ds_list)} datasource(s) imported")
                else:
                    st.session_state["grafana_validated"] = False
                    st.error(f"❌ Grafana HTTP {status}")

        icon = "🟢" if st.session_state["grafana_validated"] else "🔴"
        st.caption(f"{icon} Status")


def _auto_register_datasources(
    ds_list: list[dict]
) -> None:
    from config.datasource_registry import DatasourceRegistry, DatasourceConfig, DatasourceType

    registry = DatasourceRegistry()
    type_map = {
        "prometheus": DatasourceType.PROMETHEUS,
        "postgres":   DatasourceType.POSTGRESQL,
        "loki":       DatasourceType.LOKI,
    }

    # URL session key mapping
    url_key_map = {
        "prometheus": "prometheus_url",
        "postgres":   "postgres_url",
        "loki":       "loki_url",
    }

    processed = []
    for ds in ds_list:
        ds_type_str = ds.get("type", "").lower()
        if ds_type_str not in type_map:
            continue

        cfg = DatasourceConfig(
            uid=ds.get("uid", ""),
            name=ds_type_str,
            type=type_map[ds_type_str],
            url=ds.get("url", ""),
            config={"database": ds.get("database", ""), "grafana_id": ds.get("id")},
        )
        registry.register(cfg)
        processed.append(cfg.to_dict())

        # ✅ Also write URL into session state so all tools can find it
        url_key = url_key_map.get(ds_type_str)
        if url_key and ds.get("url"):
            st.session_state[url_key] = ds.get("url")

    st.session_state["available_datasources"] = processed


def _render_prometheus_config() -> None:
    import aiohttp

    url = st.text_input(
        "Prometheus URL",
        value=st.session_state["prometheus_url"],
        placeholder="http://localhost:9090",
        key="prom_url_widget",
    )

    if st.button("Test Prometheus", key="btn_test_prom"):
        from utils.validators import validate_url
        ok, err = validate_url(url)
        if not ok:
            st.error(f"❌ {err}")
            return

        async def _test():
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    f"{url}/api/v1/status/config",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as r:
                    return r.status

        status = _run_async(_test())

        if status == 200:
            st.session_state["prometheus_url"] = url
            st.success("✅ Prometheus connected")
            from utils.credentials_store import save_credentials
            save_credentials()

            # ── Find UID from already-registered datasources ───────────
            ds_uid = None
            for ds in st.session_state.get("available_datasources", []):
                if ds.get("type") == "prometheus":
                    ds_uid = ds.get("uid")
                    break

            # ── If UID found → load immediately ───────────────────────
            if ds_uid:
                _load_prometheus_metrics(url, ds_uid)
            else:
                # UID not registered yet → store URL, load on Save Settings
                st.session_state["prometheus_url"]          = url
                st.session_state["pending_metrics_load"]    = True
                st.info("ℹ️ Metrics will load after you click **Save Settings**")
        else:
            st.error(f"❌ HTTP {status}")


def _load_prometheus_metrics(prom_url: str, ds_uid: str) -> None:
    """Fetch all metrics from Prometheus and store in VectorDB"""
    async def _load():
        from tools.prometheus_tools import fetch_prometheus_metrics
        from tools.vectordb_tools   import store_metrics_in_vectordb

        metrics = await fetch_prometheus_metrics(prom_url)
        if not metrics:
            return 0
        count = await store_metrics_in_vectordb(metrics, ds_uid)
        return count

    with st.spinner(f"📦 Loading metrics into VectorDB…"):
        count = _run_async(_load())

    if count:
        st.info(f"📦 {count} metrics stored in VectorDB")
    else:
        st.warning("No new metrics stored (already loaded or Prometheus empty)")


def _render_postgres_config() -> None:
    import aiohttp

    url = st.text_input(
        "Connection String",
        value=st.session_state["postgres_url"],
        placeholder="postgresql://user:pass@host:5432/db",
        key="pg_url_widget",
    )

    if st.button("Test PostgreSQL", key="btn_test_pg"):
        from utils.validators import validate_connection_string
        ok, err = validate_connection_string(url)

        if not ok:
            st.error(f"❌ {err}")
        else:
            async def _test():
                import asyncpg
                try:
                    conn = await asyncpg.connect(url)
                    await conn.close()
                    return True
                except Exception as e:
                    return str(e)

            result = _run_async(_test())
            if result is True:
                st.session_state["postgres_url"] = url
                from utils.credentials_store import save_credentials
                save_credentials()
                st.success("✅ PostgreSQL connected")
            else:
                st.error(f"❌ {result}")


def _render_loki_config() -> None:
    import aiohttp

    url = st.text_input(
        "Loki URL",
        value=st.session_state["loki_url"],
        placeholder="http://localhost:3100",
        key="loki_url_widget",
    )

    if st.button("Test Loki", key="btn_test_loki"):
        from utils.validators import validate_url
        ok, err = validate_url(url)
        if not ok:
            st.error(f"❌ {err}")
        else:
            async def _test():
                async with aiohttp.ClientSession() as s:
                    async with s.get(
                        f"{url}/ready",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as r:
                        return r.status

            status = _run_async(_test())
            if status == 200:
                st.session_state["loki_url"] = url
                from utils.credentials_store import save_credentials
                save_credentials()
                st.success("✅ Loki connected")
            else:
                st.error(f"❌ HTTP {status}")


# ──────────────────────────────────────────────────────────────────────── #
#  Main                                                                     #
# ──────────────────────────────────────────────────────────────────────── #

def main() -> None:
    _init_session()
    from utils.credentials_store import load_credentials
    load_credentials()
    _render_sidebar()

    page = st.session_state.get("active_page", "home")

    match page:
        case "home":
            st.title("🎩 VizGenie")
            st.caption("Transform natural language into Grafana dashboards.")
            if not (st.session_state["groq_validated"] and st.session_state["grafana_validated"]):
                st.warning("⚠️ Configure Groq + Grafana in Connections first.")
            else:
                from ui.query_interface import render_query_interface
                render_query_interface()

        case "loki":
            from ui.loki_screen import render_loki
            render_loki()

        case "connections":
            _render_connections()


if __name__ == "__main__":
    main()