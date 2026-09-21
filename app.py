import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
from fyers_service import INDEX_SYMBOLS, DEFAULT_APP_ID, DEFAULT_SECRET_ID, DEFAULT_CUSTOMER_ID, DEFAULT_REDIRECT_URI
from data_hub import get_data_hub

# Page configuration
st.set_page_config(
    page_title="Moon Chain - Universal Fyers Terminal",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper to render clean HTML without Markdown indentation bug
def render_html(html_str):
    clean = "".join(line.strip() for line in html_str.splitlines())
    st.markdown(clean, unsafe_allow_html=True)

# Custom Styling for Financial Trading Desk
render_html("""
<style>
    .block-container {
        padding-top: 1.0rem;
        padding-bottom: 0.5rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
        max-width: 100%;
    }
    
    [data-testid="stAppViewContainer"] {
        background-color: #0b0e14;
        color: #d1d5db;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    /* Clean Trading Desk: Hide default Streamlit header toolbar/deploy and remove overlay */
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0px !important;
        min-height: 0px !important;
        pointer-events: none !important;
    }
    
    header[data-testid="stHeader"] > div {
        background: transparent !important;
    }

    [data-testid="stToolbar"], 
    [data-testid="stDecoration"],
    .stAppDeployButton {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
        width: 0px !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    [data-testid="stSidebarCollapsedControl"] {
        pointer-events: auto !important;
        z-index: 999999 !important;
    }
    
    [data-testid="stSidebar"] {
        background-color: #111622;
        border-right: 1px solid #1e2638;
    }

    .terminal-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 16px;
        background: linear-gradient(90deg, #131b2a 0%, #162235 100%);
        border: 1px solid #23324a;
        border-radius: 8px;
        margin-bottom: 10px;
    }

    .brand-title {
        display: flex;
        align-items: center;
        gap: 10px;
        font-weight: 700;
        font-size: 1.15rem;
        color: #38bdf8;
        letter-spacing: 0.5px;
    }

    .metric-container {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-bottom: 12px;
    }

    .metric-card {
        background: #111722;
        border: 1px solid #1f2a3d;
        border-radius: 8px;
        padding: 8px 12px;
        text-align: center;
    }

    .metric-label {
        font-size: 0.72rem;
        color: #8899ac;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        margin-bottom: 2px;
    }

    .metric-value {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f3f4f6;
    }

    .stream-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.75rem;
        color: #10b981;
        background: rgba(16, 185, 129, 0.12);
        padding: 3px 10px;
        border-radius: 12px;
        font-weight: 600;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .pulse-dot {
        width: 7px;
        height: 7px;
        background-color: #10b981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10b981;
        animation: pulse 1.6s infinite;
    }

    @keyframes pulse {
        0% { opacity: 0.4; }
        50% { opacity: 1; }
        100% { opacity: 0.4; }
    }

    .auth-card {
        background: #131b2a;
        border: 1px solid #20314a;
        border-radius: 10px;
        padding: 20px;
        margin-top: 10px;
    }
</style>
""")

# Initialize Singleton Global Market Data Hub (Shared across all users)
hub = get_data_hub("v2.3")

# Auto-heal legacy cached instances on Streamlit Cloud
if not hasattr(hub, "get_connection_status") or not hasattr(hub, "get_last_spot"):
    try:
        st.cache_resource.clear()
        hub = get_data_hub("v2.3")
    except Exception:
        pass

def safe_conn_status(hub_inst):
    if hasattr(hub_inst, "get_connection_status"):
        try:
            return hub_inst.get_connection_status()
        except Exception:
            pass
    if hasattr(hub_inst, "is_connected"):
        try:
            return "LIVE" if hub_inst.is_connected() else "NO_TOKEN"
        except Exception:
            pass
    return "NO_TOKEN"

def safe_token_details(hub_inst):
    if hasattr(hub_inst, "fyers_service") and hasattr(hub_inst.fyers_service, "get_token_details"):
        try:
            return hub_inst.fyers_service.get_token_details()
        except Exception:
            pass
    return {"status": "UNKNOWN", "expired": False, "exp_time": None}

def safe_last_spot(hub_inst, sym):
    if hasattr(hub_inst, "get_last_spot"):
        try:
            return hub_inst.get_last_spot(sym)
        except Exception:
            pass
    return 0.0

# Sidebar Configuration
with st.sidebar:
    st.markdown("### ⚡ Live Option Chain Settings")
    
    selected_index = st.selectbox(
        "Select Underlying",
        options=list(INDEX_SYMBOLS.keys()),
        index=0,
        help="Select index for live Fyers API option chain"
    )
    
    strike_count = st.slider(
        "Number of Strikes",
        min_value=10,
        max_value=50,
        value=20,
        step=2,
        help="Number of strikes around ATM (max 50 strikes per Fyers API limits)"
    )
    
    refresh_enabled = st.checkbox("Enable Auto-Refresh (5s)", value=True)
    refresh_interval = st.select_slider(
        "Interval (seconds)",
        options=[3, 5, 10, 15, 30],
        value=5,
        disabled=not refresh_enabled
    )

    st.markdown("---")
    st.markdown("### 🌐 Universal Multi-User Status")
    
    conn_status = safe_conn_status(hub)
    is_live = (conn_status == "LIVE")
    token_details = safe_token_details(hub)
    
    status_color = "#10b981" if conn_status == "LIVE" else ("#f59e0b" if conn_status == "EXPIRED" else "#ef4444")
    if conn_status == "LIVE":
        status_text = "🟢 LIVE • MULTI-USER SYNCHRONIZED"
    elif conn_status == "EXPIRED":
        status_text = "🟡 EXPIRED • TOKEN RENEWAL REQUIRED"
    else:
        status_text = "🔴 OFFLINE • MASTER TOKEN NEEDED"

    exp_note = ""
    if conn_status == "EXPIRED" and token_details.get("exp_time"):
        exp_note = f'<div style="font-size: 0.68rem; color: #f59e0b; margin-top: 3px;">Expired: {token_details["exp_time"]}</div>'

    render_html(f"""
    <div style="background: #151d2c; border: 1px solid #23324a; border-radius: 8px; padding: 10px;">
        <div style="font-size: 0.72rem; color: #8899ac; text-transform: uppercase;">Central Data Feed</div>
        <div style="font-size: 0.82rem; font-weight: 700; color: {status_color}; margin-top: 3px;">
            {status_text}
        </div>
        {exp_note}
        <div style="font-size: 0.7rem; color: #64748b; margin-top: 5px;">
            1 Fyers API call / 5s • Zero rate limit bans
        </div>
        <div style="font-size: 0.7rem; color: #64748b; margin-top: 2px;">
            Requests Served: <b style="color: #94a3b8;">{hub.total_requests_served}</b>
        </div>
    </div>
    """)
    
    with st.expander("⚙️ Admin & Master Token Settings", expanded=not is_live):
        st.caption("Manage centralized Fyers connection for all users:")
        tab1, tab2 = st.tabs(["Direct Token", "OAuth Login"])
        
        with tab1:
            token_input = st.text_input("Master Access Token", value=hub.get_token(), type="password")
            if st.button("Save Master Token", use_container_width=True):
                if token_input.strip():
                    hub.set_master_token(token_input.strip())
                    st.success("Master token updated for all users!")
                    st.rerun()
                else:
                    st.warning("Please enter a valid token.")
                    
        with tab2:
            st.caption("Registered Redirect URL:")
            redirect_val = st.text_input("Redirect URL", value=hub.fyers_service.redirect_uri, key="sb_redirect")
            if redirect_val != hub.fyers_service.redirect_uri:
                hub.fyers_service.save_redirect_uri(redirect_val)
                st.rerun()
                
            sb_login_url = hub.fyers_service.get_login_url()
            render_html(f"""
            <a href="{sb_login_url}" target="_blank" style="
                display: block;
                text-align: center;
                background: #0284c7;
                color: #ffffff;
                text-decoration: none;
                padding: 7px 10px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 0.8rem;
                margin-top: 6px;
                margin-bottom: 8px;
            ">1. Login to Fyers ↗</a>
            """)
            
            auth_code = st.text_input("2. Auth Code from URL", placeholder="auth_code parameter", key="sb_auth_code")
            if st.button("Generate Master Token", use_container_width=True, key="sb_gen_btn"):
                if auth_code.strip():
                    success, token, msg = hub.exchange_master_auth_code(auth_code)
                    if success:
                        st.success("Master token generated! All users connected.")
                        st.rerun()
                    else:
                        st.error(f"Error: {msg}")
                        
        if is_live:
            if st.button("Disconnect Master Token", use_container_width=True):
                hub.set_master_token("")
                st.rerun()

    st.markdown("---")
    st.caption("Moon Chain Universal • Fyers API v3")


# Fragment that auto-refreshes every 5 seconds without full page reload
@st.fragment(run_every=f"{refresh_interval}s" if refresh_enabled else None)
def render_live_option_chain(symbol_name, num_strikes):
    conn_status = safe_conn_status(hub)
    is_live = (conn_status == "LIVE")
    curr_time_str = datetime.now().strftime("%H:%M:%S")
    
    # Try fetching shared option chain if connected
    df, spot, atm, raw_result, err_msg = None, 0.0, 0, None, ""
    if is_live:
        try:
            df, spot, atm, raw_result, err_msg = hub.fetch_shared_option_chain(symbol_name, num_strikes)
        except Exception as exc:
            df, spot, atm, raw_result, err_msg = None, 0.0, 0, None, f"Data stream notice: {str(exc)}"

    # Determine display spot and atm values
    last_spot = safe_last_spot(hub, symbol_name)
    display_spot = spot if spot > 0 else last_spot
    strike_gap = INDEX_SYMBOLS.get(symbol_name, {}).get("strike_gap", 50)
    if atm > 0:
        display_atm = atm
    elif display_spot > 0:
        display_atm = int(round(display_spot / strike_gap) * strike_gap)
    else:
        display_atm = 0

    # Top Navbar Header with Universal Live Stream Badge (ALWAYS RENDERED)
    if is_live and df is not None:
        badge_bg = "rgba(16, 185, 129, 0.12)"
        badge_color = "#10b981"
        badge_border = "rgba(16, 185, 129, 0.3)"
        badge_text = "UNIVERSAL LIVE STREAM (ONE DATA FEED)"
        time_label = f"Shared Feed • {curr_time_str}"
    elif conn_status == "EXPIRED":
        badge_bg = "rgba(245, 158, 11, 0.15)"
        badge_color = "#f59e0b"
        badge_border = "rgba(245, 158, 11, 0.3)"
        badge_text = "TOKEN EXPIRED (RENEWAL REQUIRED)"
        time_label = "Standby • Token Renewal Required"
    else:
        badge_bg = "rgba(239, 68, 68, 0.15)"
        badge_color = "#ef4444"
        badge_border = "rgba(239, 68, 68, 0.3)"
        badge_text = "FEED OFFLINE (SETUP NEEDED)"
        time_label = "Standby • Waiting for token"

    render_html(f"""
    <div class="terminal-header" id="moon-terminal-header">
        <div class="brand-title">
            <span>⚡ MOON CHAIN TERMINAL</span>
            <span style="color: #64748b; font-weight: normal; font-size: 0.9rem;">|</span>
            <span style="color: #f8fafc; font-size: 1.05rem;">{symbol_name}</span>
            <span class="stream-badge" style="background: {badge_bg}; color: {badge_color}; border: 1px solid {badge_border};">
                <span class="pulse-dot" style="background-color: {badge_color}; box-shadow: 0 0 8px {badge_color};"></span>
                {badge_text}
            </span>
        </div>
        <div style="font-size: 0.78rem; color: #8899ac;">
            {time_label}
        </div>
    </div>
    """)

    # Key Analytics Metrics Cards (Spot Price & ATM Strike only) - ALWAYS RENDERED
    spot_text = f"₹{display_spot:,.2f}" if display_spot > 0 else "Waiting for Feed..."
    atm_text = f"{display_atm:,}" if display_atm > 0 else "--"
    render_html(f"""
    <div class="metric-container" id="moon-spot-container">
        <div class="metric-card" id="moon-spot-card">
            <div class="metric-label">Spot Price</div>
            <div class="metric-value" id="nifty-spot-price" style="color: #38bdf8;">{spot_text}</div>
        </div>
        <div class="metric-card" id="moon-atm-card">
            <div class="metric-label">ATM Strike</div>
            <div class="metric-value" id="nifty-atm-strike" style="color: #fbbf24;">{atm_text}</div>
        </div>
    </div>
    """)

    # If master token is not active or expired, render Setup & Renewal Card
    if not is_live:
        token_details = safe_token_details(hub)
        expired_msg = f"Your session token expired at <b>{token_details.get('exp_time')}</b>. Please renew it below to resume live streaming." if conn_status == "EXPIRED" else "Provide today's Fyers access token once. The server will stream live synchronized market data to <b>all connected visitors</b>."

        render_html(f"""
        <div class="auth-card">
            <h3 style="color: #38bdf8; margin-top: 0; margin-bottom: 6px;">🔑 Universal Data Feed Setup & Token Renewal</h3>
            <p style="color: #94a3b8; font-size: 0.88rem; margin-top: 0;">
                {expired_msg}
            </p>
        </div>
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Option 1: Paste Master Token")
            st.caption("Paste today's active Fyers access token:")
            direct_token = st.text_area("Fyers Access Token", placeholder="Paste access_token here...", height=120)
            if st.button("Connect Stream for All Users", type="primary", use_container_width=True):
                if direct_token.strip():
                    hub.set_master_token(direct_token.strip())
                    st.success("Master Token connected! All users can now view live data.")
                    st.rerun()
                else:
                    st.error("Please enter a non-empty access token.")
                    
        with col2:
            st.subheader("Option 2: Generate via OAuth")
            st.write(f"App ID: `{DEFAULT_APP_ID}` | Customer ID: `{DEFAULT_CUSTOMER_ID}`")
            
            redirect_input = st.text_input(
                "Registered Redirect URL in Fyers Dashboard",
                value=hub.fyers_service.redirect_uri,
                help="Matches your registered redirect URL in https://myapi.fyers.in/dashboard/"
            )
            if redirect_input != hub.fyers_service.redirect_uri:
                hub.fyers_service.save_redirect_uri(redirect_input)
                st.rerun()
            
            login_url = hub.fyers_service.get_login_url(redirect_uri=redirect_input)
            
            render_html(f"""
            <a href="{login_url}" target="_blank" style="
                display: block;
                text-align: center;
                background: #0284c7;
                color: #ffffff;
                text-decoration: none;
                padding: 10px 14px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 0.9rem;
                margin-top: 10px;
                margin-bottom: 10px;
            ">1. Open Fyers Login Page ↗</a>
            """)
            
            st.caption("ℹ️ Copy the authorization code from the redirected page and paste below:")
            auth_code_input = st.text_input("2. Paste auth_code or Full Redirected URL", placeholder="Paste authorization code or full URL")
            if st.button("Generate Master Token & Connect", type="primary", use_container_width=True):
                if auth_code_input.strip():
                    success, token, msg = hub.exchange_master_auth_code(auth_code_input.strip(), redirect_uri=redirect_input)
                    if success:
                        st.success("Connected successfully! All users will receive the live feed.")
                        st.rerun()
                    else:
                        st.error(f"Failed: {msg}")
                else:
                    st.warning("Please paste the auth_code or redirect URL.")
        return

    # If is_live but df is None (API notice / outside market hours without cache)
    if df is None:
        st.error(f"Fyers API Notice: {err_msg}")
        st.info("If the master session token expired, update it in the Admin sidebar.")
        return

    # Interactive Strike Selector for Candlestick Chart (Individual for this user session)
    available_strikes = [int(s) for s in df["strike"].tolist()] if not df.empty else [25000]
    default_strike = atm if atm in available_strikes else available_strikes[len(available_strikes)//2]

    col_s1, col_s2, col_s3 = st.columns([3, 2, 2])
    with col_s1:
        selected_strike = st.selectbox(
            "🎯 Select Strike Price to Load Candlestick Chart:",
            options=available_strikes,
            index=available_strikes.index(default_strike) if default_strike in available_strikes else 0,
            key=f"chart_strike_{symbol_name}"
        )
    with col_s2:
        selected_opt_type = st.radio(
            "Contract Type:",
            options=["CE", "PE"],
            horizontal=True,
            format_func=lambda x: "🔵 Call (CE)" if x == "CE" else "🔴 Put (PE)",
            key=f"chart_opt_type_{symbol_name}"
        )
    with col_s3:
        contract_row = df[df["strike"] == selected_strike]
        if not contract_row.empty:
            c_ltp = float(contract_row["ce_ltp"].values[0] if selected_opt_type == "CE" else contract_row["pe_ltp"].values[0])
            c_chg = float(contract_row["ce_chg"].values[0] if selected_opt_type == "CE" else contract_row["pe_chg"].values[0])
            c_vol = int(contract_row["ce_vol"].values[0] if selected_opt_type == "CE" else contract_row["pe_vol"].values[0])
            st.metric(
                label=f"{symbol_name} {selected_strike} {selected_opt_type}",
                value=f"₹{c_ltp:,.2f}",
                delta=f"{c_chg:+.2f}%"
            )
        else:
            c_ltp = 100.0
            c_vol = 0

    # Tabs: Option Chain Matrix | 5s Candlestick Chart
    tab_table, tab_candlestick = st.tabs([
        "📋 Option Chain Matrix",
        f"🕯️ 5s Candlestick Chart ({selected_strike} {selected_opt_type})"
    ])

    with tab_table:
        if df.empty:
            st.info("No option chain contracts returned for this strike range.")
        else:
            html_rows = []
            for _, row in df.iterrows():
                strike = int(row["strike"])
                is_atm = row["is_atm"]
                ce_itm = row["ce_itm"]
                pe_itm = row["pe_itm"]
                is_selected = strike == selected_strike
                
                row_class = "atm-row" if is_atm else ""
                ce_cell_class = "itm-call" if ce_itm else ""
                pe_cell_class = "itm-put" if pe_itm else ""
                strike_class = "selected-strike-cell" if is_selected else ("atm-strike-cell" if is_atm else "")

                ce_chg_cls = "pos-chg" if row["ce_chg"] >= 0 else "neg-chg"
                pe_chg_cls = "pos-chg" if row["pe_chg"] >= 0 else "neg-chg"

                ce_oichg_cls = "pos-chg" if row["ce_oichg"] >= 0 else "neg-chg"
                pe_oichg_cls = "pos-chg" if row["pe_oichg"] >= 0 else "neg-chg"

                ce_oichg_prefix = "+" if row["ce_oichg"] > 0 else ""
                pe_oichg_prefix = "+" if row["pe_oichg"] > 0 else ""

                strike_badge = " ⚡" if is_atm else (" 🎯" if is_selected else "")

                html_rows.append(f"""
                <tr class="{row_class}">
                    <!-- CALLS -->
                    <td class="{ce_cell_class}" style="font-weight: 600;">{int(row['ce_oi']):,}</td>
                    <td class="{ce_cell_class} {ce_oichg_cls}">{ce_oichg_prefix}{int(row['ce_oichg']):,}</td>
                    <td class="{ce_cell_class}">{int(row['ce_vol']):,}</td>
                    <td class="{ce_cell_class}">{row['ce_iv']:.1f}%</td>
                    <td class="{ce_cell_class}" style="font-weight: bold; color: #38bdf8;">₹{row['ce_ltp']:,.2f}</td>
                    <td class="{ce_cell_class} {ce_chg_cls}">{row['ce_chg']:+.2f}%</td>
                    
                    <!-- STRIKE -->
                    <td class="{strike_class}">
                        <b>{strike:,}</b>{strike_badge}
                    </td>
                    
                    <!-- PUTS -->
                    <td class="{pe_cell_class} {pe_chg_cls}">{row['pe_chg']:+.2f}%</td>
                    <td class="{pe_cell_class}" style="font-weight: bold; color: #f472b6;">₹{row['pe_ltp']:,.2f}</td>
                    <td class="{pe_cell_class}">{row['pe_iv']:.1f}%</td>
                    <td class="{pe_cell_class}">{int(row['pe_vol']):,}</td>
                    <td class="{pe_cell_class} {pe_oichg_cls}">{pe_oichg_prefix}{int(row['pe_oichg']):,}</td>
                    <td class="{pe_cell_class}" style="font-weight: 600;">{int(row['pe_oi']):,}</td>
                </tr>
                """)

            complete_table_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{
                        margin: 0;
                        padding: 0;
                        background-color: #0b0e14;
                        color: #d1d5db;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    }}
                    .table-wrapper {{
                        width: 100%;
                        overflow-x: auto;
                        border-radius: 8px;
                        border: 1px solid #1f2a3d;
                        background-color: #111722;
                    }}
                    .oc-table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-size: 0.82rem;
                        text-align: center;
                    }}
                    .oc-table thead {{
                        position: sticky;
                        top: 0;
                        z-index: 10;
                    }}
                    .oc-table th {{
                        padding: 8px 6px;
                        font-weight: 600;
                        letter-spacing: 0.4px;
                        border-bottom: 2px solid #23324a;
                    }}
                    .calls-hdr {{
                        background-color: #132438;
                        color: #38bdf8;
                        border-right: 2px solid #23324a;
                    }}
                    .puts-hdr {{
                        background-color: #281c2d;
                        color: #f472b6;
                        border-left: 2px solid #23324a;
                    }}
                    .strike-hdr {{
                        background-color: #1e2638;
                        color: #fbbf24;
                    }}
                    .sub-hdr {{
                        background-color: #162030;
                        color: #94a3b8;
                        font-size: 0.72rem;
                    }}
                    .oc-table td {{
                        padding: 6px 4px;
                        border-bottom: 1px solid #1a2333;
                        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                    }}
                    .itm-call {{
                        background-color: rgba(234, 179, 8, 0.09);
                    }}
                    .itm-put {{
                        background-color: rgba(234, 179, 8, 0.09);
                    }}
                    .atm-row {{
                        background-color: rgba(56, 189, 248, 0.14);
                        font-weight: bold;
                    }}
                    .atm-strike-cell {{
                        background-color: #2a374d;
                        color: #fbbf24;
                        font-weight: 800;
                        border-left: 2px solid #fbbf24;
                        border-right: 2px solid #fbbf24;
                    }}
                    .selected-strike-cell {{
                        background-color: #0369a1 !important;
                        color: #ffffff !important;
                        font-weight: 800;
                        border-left: 2px solid #38bdf8;
                        border-right: 2px solid #38bdf8;
                    }}
                    .pos-chg {{ color: #10b981; }}
                    .neg-chg {{ color: #ef4444; }}
                    tr:hover {{
                        background-color: #1a2436;
                    }}
                </style>
            </head>
            <body>
                <div class="table-wrapper">
                    <table class="oc-table">
                        <thead>
                            <tr>
                                <th colspan="6" class="calls-hdr">CALLS (CE)</th>
                                <th class="strike-hdr">STRIKE</th>
                                <th colspan="6" class="puts-hdr">PUTS (PE)</th>
                            </tr>
                            <tr class="sub-hdr">
                                <th style="color: #38bdf8;">OI</th>
                                <th>CHG IN OI</th>
                                <th>VOLUME</th>
                                <th>IV</th>
                                <th style="color: #38bdf8;">LTP</th>
                                <th>CHG%</th>
                                <th style="color: #fbbf24;">STRIKE</th>
                                <th>CHG%</th>
                                <th style="color: #f472b6;">LTP</th>
                                <th>IV</th>
                                <th>VOLUME</th>
                                <th>CHG IN OI</th>
                                <th style="color: #f472b6;">OI</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(html_rows)}
                        </tbody>
                    </table>
                </div>
            </body>
            </html>
            """
            components.html(complete_table_html, height=540, scrolling=True)
            st.caption("🟡 ITM highlighted with amber tint • ⚡ ATM highlighted in gold • 🎯 Selected strike highlighted in blue")

            # Inline TradingView Lightweight Chart below table
            st.markdown(f"#### 📈 TradingView 5s Candlestick Chart (200 EMA) • {symbol_name} {selected_strike} {selected_opt_type}")
            inline_tv_html = hub.candle_manager.generate_lightweight_chart_html(symbol_name, selected_strike, selected_opt_type, height=440)
            components.html(inline_tv_html, height=460, scrolling=False)

    with tab_candlestick:
        # Fullscreen dedicated TradingView Lightweight Chart tab with 200 EMA
        col_c1, col_c2 = st.columns([4, 1])
        with col_c1:
            full_tv_html = hub.candle_manager.generate_lightweight_chart_html(
                symbol_name, selected_strike, selected_opt_type, height=520,
                title_suffix=f"• Spot: ₹{spot:,.2f}"
            )
            components.html(full_tv_html, height=540, scrolling=False)
        with col_c2:
            st.markdown("#### ⚡ Contract Specs")
            contract_row = df[df["strike"] == selected_strike]
            if not contract_row.empty:
                c_ltp = float(contract_row["ce_ltp"].values[0] if selected_opt_type == "CE" else contract_row["pe_ltp"].values[0])
                c_chg = float(contract_row["ce_chg"].values[0] if selected_opt_type == "CE" else contract_row["pe_chg"].values[0])
                c_oi = int(contract_row["ce_oi"].values[0] if selected_opt_type == "CE" else contract_row["pe_oi"].values[0])
                c_oichg = int(contract_row["ce_oichg"].values[0] if selected_opt_type == "CE" else contract_row["pe_oichg"].values[0])
                c_vol = int(contract_row["ce_vol"].values[0] if selected_opt_type == "CE" else contract_row["pe_vol"].values[0])
                c_iv = float(contract_row["ce_iv"].values[0] if selected_opt_type == "CE" else contract_row["pe_iv"].values[0])
                _, _, latest_ema = hub.candle_manager.get_chart_series(symbol_name, selected_strike, selected_opt_type)
                
                render_html(f"""
                <div style="background: #151d2c; border: 1px solid #23324a; border-radius: 8px; padding: 12px; font-size: 0.85rem;">
                    <div style="color: #94a3b8; font-size: 0.75rem;">CONTRACT</div>
                    <div style="font-weight: bold; color: #38bdf8; font-size: 1.05rem; margin-bottom: 8px;">{symbol_name} {selected_strike} {selected_opt_type}</div>
                    <div style="margin-bottom: 4px;"><b>LTP:</b> ₹{c_ltp:,.2f}</div>
                    <div style="margin-bottom: 4px; color: #f59e0b;"><b>200 EMA:</b> ₹{latest_ema:,.2f}</div>
                    <div style="margin-bottom: 4px;"><b>Day Chg:</b> {c_chg:+.2f}%</div>
                    <div style="margin-bottom: 4px;"><b>IV:</b> {c_iv:.1f}%</div>
                    <div style="margin-bottom: 4px;"><b>Open Interest:</b> {c_oi:,}</div>
                    <div style="margin-bottom: 4px;"><b>OI Change:</b> {c_oichg:+,}</div>
                    <div><b>Volume:</b> {c_vol:,}</div>
                </div>
                """)


# Run the live fragment
render_live_option_chain(selected_index, strike_count)
