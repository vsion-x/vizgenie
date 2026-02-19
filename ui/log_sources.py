"""
# ui/log_sources.py
Log Sources management UI
Currently supports: AWS CloudWatch
Coming soon: Datadog, New Relic
"""

import asyncio
import logging

import streamlit as st

from tools.log_source_manager import CloudWatchSource, get_log_source_registry

logger = logging.getLogger(__name__)


def render_log_sources() -> None:
    """Log Sources tab — configure where the monitor fetches logs from."""

    st.header("📜 Log Sources")
    st.caption("Configure cloud log sources for monitoring and RCA")

    registry = get_log_source_registry()

    # ── Active sources ─────────────────────────────────────────────────
    sources = registry.list_sources()

    if sources:
        st.subheader(f"Active Sources ({len(sources)})")

        for name in sources:
            source = registry.get_source(name)
            with st.container(border=True):
                col_info, col_btn = st.columns([5, 1])

                with col_info:
                    st.markdown(f"**{name}**")
                    source_type = getattr(source, "SOURCE_TYPE", "unknown")
                    st.caption(f"Type: `{source_type}`")

                    if source_type == "cloudwatch":
                        region = getattr(source, "region", "—")
                        groups = getattr(source, "log_group_names", [])
                        has_session = bool(getattr(source, "aws_session_token", None))
                        
                        st.caption(f"Region: `{region}`")
                        st.caption(f"Log Groups: `{', '.join(groups)}`" if groups else "No log groups")
                        
                        # ✅ Show if using temporary credentials
                        if has_session:
                            st.caption("🔑 Using temporary credentials (session token)")

                with col_btn:
                    st.write("")   # vertical align
                    if st.button("🗑️ Remove", key=f"remove_{name}"):
                        registry.remove_source(name)
                        st.success(f"Removed '{name}'")
                        st.rerun()

        st.divider()
    else:
        st.info("No log sources configured yet — add one below.")

    # ── Add new source ─────────────────────────────────────────────────
    st.subheader("Add New Log Source")

    source_type = st.selectbox(
        "Source Type",
        options=["AWS CloudWatch", "Datadog (Coming Soon)", "New Relic (Coming Soon)"],
        help="Select the cloud logging provider",
    )

    if source_type == "AWS CloudWatch":
        _render_cloudwatch_form(registry)
    else:
        st.info("🚧 This integration is coming soon.")


# ══════════════════════════════════════════════════════════════════════
#  CloudWatch form
# ══════════════════════════════════════════════════════════════════════

def _render_cloudwatch_form(registry) -> None:
    st.markdown("### AWS CloudWatch Configuration")
    
    # ✅ Info box explaining authentication
    st.info("""
    **Authentication Methods:**
    
    1. **Long-term credentials**: Use IAM user access keys
       - AWS_ACCESS_KEY_ID
       - AWS_SECRET_ACCESS_KEY
    
    2. **Temporary credentials**: Use STS session tokens (for assumed roles)
       - AWS_ACCESS_KEY_ID
       - AWS_SECRET_ACCESS_KEY
       - AWS_SESSION_TOKEN (expires after configured duration)
    
    **Required IAM Permissions:**
    - `logs:DescribeLogGroups`
    - `logs:StartQuery`
    - `logs:GetQueryResults`
    """)

    with st.form("cloudwatch_form", clear_on_submit=False):
        source_name = st.text_input(
            "Source Name",
            value="my-cloudwatch",
            help="Friendly label for this source",
        )

        st.markdown("**AWS Credentials** (Standard AWS Environment Variable Names)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # ✅ AWS_ACCESS_KEY_ID
            access_key = st.text_input(
                "AWS_ACCESS_KEY_ID",
                type="password",
                help="IAM user access key or temporary access key from STS",
            )
        
        with col2:
            # ✅ AWS_SECRET_ACCESS_KEY
            secret_key = st.text_input(
                "AWS_SECRET_ACCESS_KEY",
                type="password",
                help="Secret key corresponding to the access key",
            )
        
        # ✅ AWS_SESSION_TOKEN (optional)
        session_token = st.text_input(
            "AWS_SESSION_TOKEN (Optional)",
            type="password",
            help="Required only for temporary credentials from AWS STS (leave empty for long-term credentials)",
        )

        st.markdown("**CloudWatch Settings**")
        
        col3, col4 = st.columns(2)
        
        with col3:
            region = st.selectbox(
                "AWS Region",
                options=[
                    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
                    "eu-west-1", "eu-west-2", "eu-central-1",
                    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
                    "ap-south-1", "ca-central-1", "sa-east-1",
                ],
            )
        
        with col4:
            st.write("")   # spacer

        log_groups_raw = st.text_area(
            "Log Group Name(s)",
            placeholder="/aws/lambda/my-function\n/aws/ecs/my-service",
            help=(
                "One log group per line. "
                "Example: /aws/lambda/my-function"
            ),
            height=100,
        )

        submitted = st.form_submit_button(
            "🔌 Test & Add Source", use_container_width=True, type="primary"
        )

    if not submitted:
        return

    # ── Validate inputs ──────────────────────────────────────────────

    errors = []
    if not source_name.strip():
        errors.append("Source Name is required")
    if not access_key.strip():
        errors.append("AWS_ACCESS_KEY_ID is required")
    if not secret_key.strip():
        errors.append("AWS_SECRET_ACCESS_KEY is required")

    log_groups = [
        g.strip() for g in log_groups_raw.strip().splitlines() if g.strip()
    ]
    if not log_groups:
        errors.append("At least one Log Group Name is required")

    if errors:
        for err in errors:
            st.error(f"❌ {err}")
        return

    if source_name in registry.list_sources():
        st.error(f"❌ A source named '{source_name}' already exists")
        return

    # ── Test connection ──────────────────────────────────────────────

    # ✅ Create source with standard AWS credential names
    source = CloudWatchSource(
        aws_access_key_id=access_key.strip(),
        aws_secret_access_key=secret_key.strip(),
        region=region,
        log_group_names=log_groups,
        aws_session_token=session_token.strip() if session_token.strip() else None,  # ✅ Optional
    )

    with st.spinner("Testing connection to CloudWatch…"):
        try:
            success, message = asyncio.run(source.test_connection())
        except Exception as exc:
            success, message = False, str(exc)

    if not success:
        st.error(f"❌ Connection failed: {message}")
        st.caption("Check your credentials and log group names, then try again.")
        return

    # ── Register & persist ───────────────────────────────────────────

    registry.add_source(source_name, source)
    # Registry auto-saves to data/log_sources.json on add_source()

    st.success(f"✅ {message}")
    st.success(f"✅ Source **'{source_name}'** added and saved.")
    
    if session_token:
        st.warning(
            "⚠️ **Temporary Credentials**: Your session token will expire. "
            "Update credentials when you see authentication errors."
        )
    
    st.info(
        "💡 Go to **Monitor** tab and click **Start Monitor** to begin "
        "collecting logs from this source."
    )
    st.rerun()