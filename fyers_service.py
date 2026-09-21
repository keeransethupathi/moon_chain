import os
import time
import math
import json
import base64
from datetime import datetime
import urllib.parse
import pandas as pd

# Updated Fyers credentials provided by user
DEFAULT_APP_ID = "1FRBS8GNGM-100"
DEFAULT_SECRET_ID = "QK260NFE05"
DEFAULT_CUSTOMER_ID = "YK14522"
DEFAULT_REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"
TOKEN_FILE = "fyers_token.txt"
CONFIG_FILE = "fyers_config.json"

# Index symbols map
INDEX_SYMBOLS = {
    "NIFTY 50": {"symbol": "NSE:NIFTY50-INDEX", "strike_gap": 50},
    "BANK NIFTY": {"symbol": "NSE:NIFTYBANK-INDEX", "strike_gap": 100},
    "FIN NIFTY": {"symbol": "NSE:FINNIFTY-INDEX", "strike_gap": 50},
    "MIDCP NIFTY": {"symbol": "NSE:MIDCPNIFTY-INDEX", "strike_gap": 25},
    "SENSEX": {"symbol": "BSE:SENSEX-INDEX", "strike_gap": 100}
}


class FyersService:
    def __init__(self, app_id=DEFAULT_APP_ID, secret_id=DEFAULT_SECRET_ID, customer_id=DEFAULT_CUSTOMER_ID):
        self.app_id = app_id
        self.secret_id = secret_id
        self.customer_id = customer_id
        self.redirect_uri = self.load_saved_redirect_uri()
        self.access_token = self.load_saved_token()
        self.fyers_client = None

    def load_saved_redirect_uri(self):
        """Load configured redirect URI from config file"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    cfg = json.load(f)
                    return cfg.get("redirect_uri", DEFAULT_REDIRECT_URI)
            except Exception:
                pass
        return DEFAULT_REDIRECT_URI

    def save_redirect_uri(self, uri):
        """Save redirect URI to config file"""
        self.redirect_uri = uri.strip()
        try:
            cfg = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    cfg = json.load(f)
            cfg["redirect_uri"] = self.redirect_uri
            with open(CONFIG_FILE, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def load_saved_token(self):
        """Load stored access token from disk, env, or st.secrets"""
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "FYERS_ACCESS_TOKEN" in st.secrets:
                token = str(st.secrets["FYERS_ACCESS_TOKEN"]).strip()
                if token:
                    return token
        except Exception:
            pass

        env_token = os.environ.get("FYERS_ACCESS_TOKEN", "").strip()
        if env_token:
            return env_token

        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r") as f:
                    token = f.read().strip()
                    if token:
                        return token
            except Exception:
                pass
        return ""

    def save_token(self, token):
        """Save access token to disk"""
        self.access_token = token.strip()
        try:
            with open(TOKEN_FILE, "w") as f:
                f.write(self.access_token)
        except Exception:
            pass

    def is_token_expired(self):
        """Check whether the stored access token has expired based on its JWT payload"""
        if not self.access_token:
            return True
        try:
            parts = self.access_token.split(".")
            if len(parts) >= 2:
                # Add base64 padding if needed
                payload_b64 = parts[1]
                rem = len(payload_b64) % 4
                if rem > 0:
                    payload_b64 += "=" * (4 - rem)
                payload_json = base64.b64decode(payload_b64.encode("utf-8")).decode("utf-8")
                payload = json.loads(payload_json)
                exp = payload.get("exp", 0)
                if exp > 0 and time.time() >= exp:
                    return True
                return False
        except Exception:
            pass
        return False

    def get_token_details(self):
        """Get expiration timestamp and status of the current token"""
        if not self.access_token:
            return {"status": "NO_TOKEN", "expired": True, "exp_time": None}
        try:
            parts = self.access_token.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                rem = len(payload_b64) % 4
                if rem > 0:
                    payload_b64 += "=" * (4 - rem)
                payload_json = base64.b64decode(payload_b64.encode("utf-8")).decode("utf-8")
                payload = json.loads(payload_json)
                exp = payload.get("exp", 0)
                exp_dt = datetime.fromtimestamp(exp) if exp > 0 else None
                is_expired = time.time() >= exp if exp > 0 else False
                return {
                    "status": "EXPIRED" if is_expired else "VALID",
                    "expired": is_expired,
                    "exp_time": exp_dt.strftime("%Y-%m-%d %H:%M:%S") if exp_dt else "Unknown",
                    "remaining_sec": max(0, int(exp - time.time())) if exp > 0 else 0
                }
        except Exception:
            pass
        return {"status": "UNKNOWN", "expired": False, "exp_time": None}

    def get_spot_quote(self, symbol_key):
        """Fetch live real-time spot quote directly via Fyers Quotes API"""
        symbol_info = INDEX_SYMBOLS.get(symbol_key, INDEX_SYMBOLS["NIFTY 50"])
        fyers_symbol = symbol_info["symbol"]
        client = self.init_fyers_client()
        if not client:
            return 0.0
        try:
            res = client.quotes(data={"symbols": fyers_symbol})
            if res.get("s") == "ok" and "d" in res and len(res["d"]) > 0:
                quote_data = res["d"][0].get("v", {})
                lp = quote_data.get("lp")
                if lp is not None and float(lp) > 0:
                    return float(lp)
        except Exception:
            pass
        return 0.0

    def get_login_url(self, redirect_uri=None):
        """Generate Fyers OAuth login URL for obtaining auth code"""
        uri = (redirect_uri or self.redirect_uri).strip()
        try:
            from fyers_apiv3 import fyersModel
            session = fyersModel.SessionModel(
                client_id=self.app_id,
                secret_key=self.secret_id,
                redirect_uri=uri,
                response_type="code",
                grant_type="authorization_code"
            )
            return session.generate_authcode()
        except Exception as e:
            return f"https://api-t1.fyers.in/api/v3/generate-authcode?client_id={self.app_id}&redirect_uri={uri}&response_type=code&state=sample_state"

    def extract_auth_code(self, input_text):
        """Extract auth_code whether user enters raw code or full redirected URL"""
        text = input_text.strip()
        if "?" in text or "&" in text or "http" in text:
            try:
                parsed = urllib.parse.urlparse(text)
                params = urllib.parse.parse_qs(parsed.query)
                if "auth_code" in params:
                    return params["auth_code"][0]
            except Exception:
                pass
        if "auth_code=" in text:
            return text.split("auth_code=")[1].split("&")[0]
        return text

    def exchange_auth_code(self, auth_code, redirect_uri=None):
        """Exchange auth code from login redirect for a 24h access token"""
        clean_code = self.extract_auth_code(auth_code)
        uri = (redirect_uri or self.redirect_uri).strip()
        try:
            from fyers_apiv3 import fyersModel
            session = fyersModel.SessionModel(
                client_id=self.app_id,
                secret_key=self.secret_id,
                redirect_uri=uri,
                response_type="code",
                grant_type="authorization_code"
            )
            session.set_token(clean_code)
            response = session.generate_token()
            if response.get("s") == "ok" and "access_token" in response:
                token = response["access_token"]
                self.save_token(token)
                return True, token, "Access Token generated successfully!"
            else:
                msg = response.get("message", "Failed to generate token")
                code = response.get("code", "")
                return False, "", f"Fyers Token Error [{code}]: {msg}"
        except Exception as e:
            return False, "", str(e)

    def init_fyers_client(self):
        """Initialize the FyersModel client if token is present"""
        if not self.access_token:
            return None
        try:
            from fyers_apiv3 import fyersModel
            self.fyers_client = fyersModel.FyersModel(
                client_id=self.app_id,
                token=self.access_token,
                log_path=""
            )
            return self.fyers_client
        except Exception:
            return None

    def fetch_live_option_chain(self, symbol_key, strike_count=20, expiry_timestamp=""):
        """Fetch live option chain exclusively from Fyers API v3"""
        symbol_info = INDEX_SYMBOLS.get(symbol_key, INDEX_SYMBOLS["NIFTY 50"])
        fyers_symbol = symbol_info["symbol"]
        
        if not self.access_token:
            return None, "No Fyers access token configured. Please enter or generate your token."
        
        client = self.init_fyers_client()
        if not client:
            return None, "Failed to initialize Fyers API client. Check token validity."
        
        try:
            data = {
                "symbol": fyers_symbol,
                "strikecount": min(int(strike_count), 50),
                "timestamp": str(expiry_timestamp) if expiry_timestamp else ""
            }
            response = client.optionchain(data=data)
            
            if response.get("s") == "ok" and "data" in response:
                return self._parse_fyers_response(response["data"], symbol_key), ""
            else:
                msg = response.get("message", "Error fetching data from Fyers API")
                code = response.get("code", "")
                return None, f"Fyers API Error [{code}]: {msg}"
        except Exception as e:
            return None, f"Fyers API Exception: {str(e)}"

    def _parse_fyers_response(self, data, symbol_key):
        """Parse raw Fyers option chain response into tabular structured format"""
        symbol_info = INDEX_SYMBOLS.get(symbol_key, INDEX_SYMBOLS["NIFTY 50"])
        fyers_symbol = symbol_info["symbol"]
        
        raw_chain = data.get("optionsChain", [])
        vix = data.get("indiavixData", {}).get("ltp", 0.0)
        expiries = data.get("expiryData", [])
        
        # 1. Look for spot price in root-level fields
        spot_price = float(
            data.get("underlyingValue") or 
            data.get("spot_price") or 
            data.get("underlying_price") or 
            data.get("netLtp") or 
            0.0
        )
        
        rows = {}
        for item in raw_chain:
            strike = item.get("strike_price")
            opt_type = item.get("option_type")
            item_sym = item.get("symbol", "")
            item_ltp = float(item.get("ltp", 0.0))

            # Detect if this item is the underlying index itself (Fyers returns 1 INDEX record)
            is_index_item = (
                item_sym == fyers_symbol or
                opt_type not in ("CE", "PE") or
                strike is None or
                strike in (-1, 0)
            )

            if is_index_item:
                if spot_price <= 0.0 and item_ltp > 0:
                    spot_price = item_ltp
                # Do not insert index entry as a strike row in option chain
                continue
            
            strike = int(strike)
            if strike not in rows:
                rows[strike] = {"strike": strike}
            
            prefix = "ce_" if opt_type == "CE" else "pe_"
            rows[strike][prefix + "ltp"] = item_ltp
            rows[strike][prefix + "chg"] = float(item.get("pchange", item.get("change", 0.0)))
            rows[strike][prefix + "oi"] = int(item.get("oi", 0))
            rows[strike][prefix + "oichg"] = int(item.get("oichange", 0))
            rows[strike][prefix + "vol"] = int(item.get("volume", 0))
            rows[strike][prefix + "iv"] = float(item.get("iv", 0.0))
            rows[strike][prefix + "symbol"] = item_sym

        df_list = list(rows.values())
        df = pd.DataFrame(df_list).sort_values("strike").reset_index(drop=True) if df_list else pd.DataFrame()
        
        # 2. If spot_price is still 0, fetch live quote directly from Fyers Quotes API
        if spot_price <= 0.0:
            spot_price = self.get_spot_quote(symbol_key)

        # 3. Fallback to median strike only if spot_price is still unavailable
        if spot_price <= 0.0 and not df.empty and "strike" in df:
            spot_price = float(df["strike"].median())
            
        return self._enrich_option_data(df, spot_price, vix, expiries)

    def _enrich_option_data(self, df, spot_price, vix, expiries):
        """Calculate PCR, Max Pain, ATM Strike, and ITM/OTM status"""
        if df.empty:
            return {
                "df": df,
                "spot": spot_price or 0.0,
                "atm": 0,
                "atm_strike": 0,
                "pcr": 1.0,
                "max_pain": 0,
                "total_ce_oi": 0,
                "total_pe_oi": 0,
                "vix": vix,
                "expiries": expiries,
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        
        for col in ["ce_oi", "ce_oichg", "ce_vol", "ce_iv", "ce_ltp", "ce_chg", 
                    "pe_chg", "pe_ltp", "pe_iv", "pe_vol", "pe_oichg", "pe_oi"]:
            if col not in df.columns:
                df[col] = 0.0
                
        df = df.fillna(0)
        
        strikes = df["strike"].values
        atm_strike = min(strikes, key=lambda x: abs(x - spot_price))
        
        total_ce_oi = int(df["ce_oi"].sum())
        total_pe_oi = int(df["pe_oi"].sum())
        pcr = round(total_pe_oi / max(1, total_ce_oi), 2)
        
        min_loss = float("inf")
        max_pain_strike = atm_strike
        for exp_strike in strikes:
            ce_loss = (df["ce_oi"] * df["strike"].apply(lambda s: max(0.0, exp_strike - s))).sum()
            pe_loss = (df["pe_oi"] * df["strike"].apply(lambda s: max(0.0, s - exp_strike))).sum()
            total_loss = ce_loss + pe_loss
            if total_loss < min_loss:
                min_loss = total_loss
                max_pain_strike = exp_strike
                
        df["ce_itm"] = df["strike"] < spot_price
        df["pe_itm"] = df["strike"] > spot_price
        df["is_atm"] = df["strike"] == atm_strike
        
        return {
            "df": df,
            "spot": spot_price,
            "atm": atm_strike,
            "atm_strike": atm_strike,
            "pcr": pcr,
            "max_pain": max_pain_strike,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
            "vix": vix,
            "expiries": expiries,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
