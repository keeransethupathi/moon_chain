import threading
import time
from datetime import datetime
import pandas as pd
import streamlit as st
from fyers_service import FyersService, INDEX_SYMBOLS, DEFAULT_APP_ID, DEFAULT_SECRET_ID, DEFAULT_CUSTOMER_ID, DEFAULT_REDIRECT_URI
from candle_service import CandleManager


class GlobalMarketDataHub:
    """Thread-safe centralized market data hub shared across all connected users (Universal Mode).
    
    Ensures that only ONE Fyers API request is made per refresh interval, preventing rate limits
    and ensuring all concurrent visitors see synchronized live data.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self.fyers_service = FyersService()
        self.candle_manager = CandleManager(max_candles=350)
        
        # Cache format: cache_key -> {"df": DataFrame, "spot": float, "atm": int, "raw": dict, "time": float, "error": str}
        self._data_cache = {}
        self.cache_ttl = 4.0  # seconds: max 1 Fyers API call per 4 seconds per index
        self.last_fetch_time = 0.0
        self.total_requests_served = 0
        self.total_fyers_calls = 0
        self._last_spot = {}
        self.last_api_error = ""

        # Attempt to load token from st.secrets if running on Streamlit Cloud
        self._try_load_secrets_token()

    def _try_load_secrets_token(self):
        """Check Streamlit Cloud secrets for FYERS_ACCESS_TOKEN"""
        try:
            if hasattr(st, "secrets") and "FYERS_ACCESS_TOKEN" in st.secrets:
                token = str(st.secrets["FYERS_ACCESS_TOKEN"]).strip()
                if token and not self.fyers_service.access_token:
                    self.fyers_service.save_token(token)
        except Exception:
            pass

    def is_connected(self):
        """Check if master Fyers access token is configured and NOT expired"""
        if not self.fyers_service.access_token:
            return False
        return not self.fyers_service.is_token_expired()

    def get_connection_status(self):
        """Return clear connection status: LIVE, EXPIRED, or NO_TOKEN"""
        if not self.fyers_service.access_token:
            return "NO_TOKEN"
        if self.fyers_service.is_token_expired():
            return "EXPIRED"
        if self.last_api_error and any(k in self.last_api_error.lower() for k in ["token", "auth", "-15", "invalid"]):
            return "EXPIRED"
        return "LIVE"

    def get_last_spot(self, symbol_key):
        """Return the last known valid spot price for this symbol"""
        return self._last_spot.get(symbol_key, 0.0)

    def get_token(self):
        return self.fyers_service.access_token

    def set_master_token(self, token):
        """Update master access token across all sessions"""
        with self._lock:
            self.fyers_service.save_token(token)
            self.last_api_error = ""
            # Clear cached errors
            self._data_cache.clear()

    def exchange_master_auth_code(self, auth_code, redirect_uri=None):
        """Generate and store master access token from OAuth code"""
        with self._lock:
            success, token, msg = self.fyers_service.exchange_auth_code(auth_code, redirect_uri)
            if success:
                self.last_api_error = ""
                self._data_cache.clear()
            return success, token, msg

    def clear_cache(self):
        """Clear cached option chain data"""
        with self._lock:
            self._data_cache.clear()

    def fetch_shared_option_chain(self, symbol_key, strike_count=20, expiry_timestamp=""):
        """Fetch option chain with centralized caching.
        
        If multiple users request data within the cache TTL, the cached snapshot is returned,
        eliminating duplicate API calls to Fyers.
        """
        cache_key = f"{symbol_key}_{strike_count}_{expiry_timestamp}"
        now = time.time()
        self.total_requests_served += 1

        # Check in-memory cache first
        if cache_key in self._data_cache:
            try:
                entry = self._data_cache[cache_key]
                cache_time = entry.get("time", 0.0)
                if (now - cache_time) < self.cache_ttl and entry.get("df") is not None:
                    return (
                        entry.get("df"),
                        entry.get("spot", 0.0),
                        entry.get("atm", 0),
                        entry.get("raw"),
                        entry.get("error", "")
                    )
            except Exception:
                pass

        # Cache miss or expired - acquire lock to make at most 1 Fyers call
        with self._lock:
            try:
                # Double-check if another thread updated cache while waiting for lock
                if cache_key in self._data_cache:
                    entry = self._data_cache[cache_key]
                    cache_time = entry.get("time", 0.0)
                    if (time.time() - cache_time) < self.cache_ttl and entry.get("df") is not None:
                        return (
                            entry.get("df"),
                            entry.get("spot", 0.0),
                            entry.get("atm", 0),
                            entry.get("raw"),
                            entry.get("error", "")
                        )

                self.total_fyers_calls += 1
                self.last_fetch_time = time.time()

                result, error_msg = self.fyers_service.fetch_live_option_chain(
                    symbol_key, 
                    strike_count=strike_count, 
                    expiry_timestamp=expiry_timestamp
                )

                if result is not None and not error_msg and isinstance(result, dict):
                    df = result.get("df", pd.DataFrame())
                    spot = float(result.get("spot", 0.0) or 0.0)
                    if spot > 0:
                        self._last_spot[symbol_key] = spot
                    elif symbol_key in self._last_spot:
                        spot = self._last_spot[symbol_key]
                    self.last_api_error = ""
                    
                    # Safe extraction of atm strike
                    atm_val = result.get("atm") if result.get("atm") is not None else result.get("atm_strike")
                    if atm_val is not None:
                        try:
                            atm = int(float(atm_val))
                        except Exception:
                            atm = 0
                    elif df is not None and not df.empty and "strike" in df:
                        atm = int(df["strike"].iloc[len(df)//2])
                    else:
                        atm = 0

                    # Ingest live ticks for all valid strikes in the chain into global candle manager
                    if df is not None and not df.empty:
                        for _, row in df.iterrows():
                            try:
                                strike = int(row.get("strike", 0))
                                ce_ltp = float(row.get("ce_ltp", 0.0))
                                pe_ltp = float(row.get("pe_ltp", 0.0))
                                ce_vol = int(row.get("ce_vol", 0))
                                pe_vol = int(row.get("pe_vol", 0))
                                if strike > 0:
                                    if ce_ltp > 0:
                                        self.candle_manager.add_tick(symbol_key, strike, "CE", ce_ltp, volume_delta=ce_vol)
                                    if pe_ltp > 0:
                                        self.candle_manager.add_tick(symbol_key, strike, "PE", pe_ltp, volume_delta=pe_vol)
                            except Exception:
                                pass

                    self._data_cache[cache_key] = {
                        "df": df,
                        "spot": spot,
                        "atm": atm,
                        "raw": result,
                        "time": time.time(),
                        "error": ""
                    }
                    return df, spot, atm, result, ""
                else:
                    self.last_api_error = error_msg or "Failed to fetch option chain"
                    fallback_spot = self._last_spot.get(symbol_key, 0.0)
                    if cache_key in self._data_cache:
                        entry = self._data_cache[cache_key]
                        if entry.get("df") is not None and not entry.get("df").empty:
                            return (
                                entry.get("df"),
                                entry.get("spot", fallback_spot) or fallback_spot,
                                entry.get("atm", 0),
                                entry.get("raw"),
                                f"⚠️ Using cached data ({error_msg})"
                            )
                    
                    return None, fallback_spot, 0, None, error_msg or "Failed to fetch option chain"
            except Exception as ex:
                self.last_api_error = str(ex)
                fallback_spot = self._last_spot.get(symbol_key, 0.0)
                if cache_key in self._data_cache:
                    entry = self._data_cache[cache_key]
                    if entry.get("df") is not None and not entry.get("df").empty:
                        return (
                            entry.get("df"),
                            entry.get("spot", fallback_spot) or fallback_spot,
                            entry.get("atm", 0),
                            entry.get("raw"),
                            f"⚠️ Using cached data ({str(ex)})"
                        )
                return None, fallback_spot, 0, None, f"Processing Error: {str(ex)}"




def ensure_instance_compatibility(hub):
    """Ensure cached instances on Streamlit Cloud from previous runs have all new methods."""
    if not hasattr(hub, "_last_spot"):
        hub._last_spot = {}
    if not hasattr(hub, "last_api_error"):
        hub.last_api_error = ""
    if not hasattr(hub, "get_connection_status"):
        hub.get_connection_status = lambda: (
            "NO_TOKEN" if not getattr(hub.fyers_service, "access_token", None)
            else "EXPIRED" if getattr(hub.fyers_service, "is_token_expired", lambda: False)()
            else "LIVE"
        )
    if not hasattr(hub, "get_last_spot"):
        hub.get_last_spot = lambda sym: hub._last_spot.get(sym, 0.0)
    return hub


@st.cache_resource(show_spinner=False)
def get_data_hub(_version="v2.3"):
    """Streamlit singleton instance shared across all users and browser sessions."""
    instance = GlobalMarketDataHub()
    return ensure_instance_compatibility(instance)
