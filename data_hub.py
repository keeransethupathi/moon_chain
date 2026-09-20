import threading
import time
from datetime import datetime
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
        """Check if master Fyers access token is configured"""
        return bool(self.fyers_service.access_token)

    def get_token(self):
        return self.fyers_service.access_token

    def set_master_token(self, token):
        """Update master access token across all sessions"""
        with self._lock:
            self.fyers_service.save_token(token)
            # Clear cached errors
            self._data_cache.clear()

    def exchange_master_auth_code(self, auth_code, redirect_uri=None):
        """Generate and store master access token from OAuth code"""
        with self._lock:
            success, token, msg = self.fyers_service.exchange_auth_code(auth_code, redirect_uri)
            if success:
                self._data_cache.clear()
            return success, token, msg

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
            entry = self._data_cache[cache_key]
            if (now - entry["time"]) < self.cache_ttl:
                return entry["df"], entry["spot"], entry["atm"], entry["raw"], entry["error"]

        # Cache miss or expired - acquire lock to make at most 1 Fyers call
        with self._lock:
            # Double-check if another thread updated cache while waiting for lock
            if cache_key in self._data_cache:
                entry = self._data_cache[cache_key]
                if (time.time() - entry["time"]) < self.cache_ttl:
                    return entry["df"], entry["spot"], entry["atm"], entry["raw"], entry["error"]

            self.total_fyers_calls += 1
            self.last_fetch_time = time.time()

            result, error_msg = self.fyers_service.fetch_live_option_chain(
                symbol_key, 
                strike_count=strike_count, 
                expiry_timestamp=expiry_timestamp
            )

            if result is not None and not error_msg:
                df = result.get("df")
                spot = float(result.get("spot", 0.0))
                atm = int(result.get("atm_strike", result.get("atm", 0)))

                # Ingest live ticks for all strikes in the chain into global candle manager
                if not df.empty:
                    for _, row in df.iterrows():
                        strike = int(row["strike"])
                        if row["ce_ltp"] > 0:
                            self.candle_manager.add_tick(
                                symbol_key, strike, "CE", row["ce_ltp"], volume_delta=int(row["ce_vol"])
                            )
                        if row["pe_ltp"] > 0:
                            self.candle_manager.add_tick(
                                symbol_key, strike, "PE", row["pe_ltp"], volume_delta=int(row["pe_vol"])
                            )

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
                # If fetch failed but we have a previous cache entry, return it with error note
                if cache_key in self._data_cache and not self._data_cache[cache_key]["df"].empty:
                    entry = self._data_cache[cache_key]
                    return entry["df"], entry["spot"], entry["atm"], entry["raw"], f"⚠️ Using cached data ({error_msg})"
                
                return None, 0.0, 0, None, error_msg


@st.cache_resource
def get_data_hub():
    """Streamlit singleton instance shared across all users and browser sessions."""
    return GlobalMarketDataHub()
