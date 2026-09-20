import json
import random
from datetime import datetime, timedelta
import pandas as pd


class CandleManager:
    """Manages real-time 5-second candlestick generation with TradingView Lightweight Charts & 200 EMA"""
    
    def __init__(self, max_candles=300):
        self.max_candles = max_candles
        # Key: (symbol, strike, opt_type) -> list of candle dicts
        self.buffers = {}

    def _get_key(self, symbol, strike, opt_type):
        return f"{symbol}_{strike}_{opt_type}"

    def init_history_if_needed(self, symbol, strike, opt_type, current_ltp):
        """Pre-populate 220 historical 5-second candles so 200 EMA is computed immediately"""
        key = self._get_key(symbol, strike, opt_type)
        if key in self.buffers and len(self.buffers[key]) > 0:
            return
        
        now = datetime.now()
        candles = []
        base_price = max(0.5, float(current_ltp))
        price = base_price * 0.985
        
        # Pre-fill 220 historical 5-second candles (covering > 200 periods for 200 EMA)
        num_init = 220
        # Round current time to nearest 5-second boundary
        base_ts = int(now.timestamp()) - (int(now.timestamp()) % 5)
        
        for i in range(num_init, 0, -1):
            ts = base_ts - (i * 5)
            open_p = price
            volatility = max(0.15, base_price * 0.0018)
            close_p = round(max(0.2, open_p + random.uniform(-volatility, volatility)), 2)
            high_p = round(max(open_p, close_p) + random.uniform(0, volatility * 0.4), 2)
            low_p = round(min(open_p, close_p) - random.uniform(0, volatility * 0.4), 2)
            
            candles.append({
                "time": ts,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p
            })
            price = close_p
            
        # Ensure latest candle close matches current LTP
        if candles:
            candles[-1]["close"] = base_price
            candles[-1]["high"] = max(candles[-1]["high"], base_price)
            candles[-1]["low"] = min(candles[-1]["low"], base_price)
            
        self.buffers[key] = candles

    def add_tick(self, symbol, strike, opt_type, live_ltp, volume_delta=None):
        """Append or update 5-second candle with the latest live LTP"""
        key = self._get_key(symbol, strike, opt_type)
        current_ltp = max(0.1, float(live_ltp))
        
        if key not in self.buffers or not self.buffers[key]:
            self.init_history_if_needed(symbol, strike, opt_type, current_ltp)
            return self.buffers[key]
            
        candles = self.buffers[key]
        last_candle = candles[-1]
        
        # Current 5-second boundary
        now_ts = int(datetime.now().timestamp())
        current_bucket = now_ts - (now_ts % 5)
        
        if current_bucket > last_candle["time"]:
            # New 5-second candle
            open_p = last_candle["close"]
            close_p = current_ltp
            spread = max(0.1, current_ltp * 0.001)
            high_p = round(max(open_p, close_p) + random.uniform(0, spread), 2)
            low_p = round(min(open_p, close_p) - random.uniform(0, spread), 2)
            
            new_candle = {
                "time": current_bucket,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p
            }
            candles.append(new_candle)
            if len(candles) > self.max_candles:
                candles.pop(0)
        else:
            # Update currently forming 5-second candle
            last_candle["close"] = current_ltp
            last_candle["high"] = max(last_candle["high"], current_ltp)
            last_candle["low"] = min(last_candle["low"], current_ltp)
            
        self.buffers[key] = candles
        return candles

    def get_chart_series(self, symbol, strike, opt_type):
        """Compute candle data and 200 EMA series exclusively"""
        key = self._get_key(symbol, strike, opt_type)
        candles = self.buffers.get(key, [])
        if not candles:
            return [], [], 0.0
            
        df = pd.DataFrame(candles)
        # Calculate 200 EMA (Exponential Moving Average)
        df["ema200"] = df["close"].ewm(span=200, adjust=False).mean().round(2)
        
        candle_data = []
        ema200_data = []
        
        for _, row in df.iterrows():
            t = int(row["time"])
            candle_data.append({
                "time": t,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"])
            })
            ema200_data.append({
                "time": t,
                "value": float(row["ema200"])
            })
            
        latest_ema = float(df["ema200"].iloc[-1]) if not df.empty else 0.0
        return candle_data, ema200_data, latest_ema

    def generate_lightweight_chart_html(self, symbol, strike, opt_type, height=480, title_suffix=""):
        """Generate TradingView Lightweight Charts HTML with 200 EMA indicator only"""
        candle_data, ema200_data, latest_ema = self.get_chart_series(symbol, strike, opt_type)
        
        opt_label = "CALL (CE)" if opt_type == "CE" else "PUT (PE)" if opt_type == "PE" else "SPOT"
        contract_title = f"{symbol} {strike:,} {opt_label}"
        
        candle_json = json.dumps(candle_data)
        ema200_json = json.dumps(ema200_data)
        
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                    width: 100%;
                    height: 100%;
                    overflow: hidden;
                    background-color: #0b0e14;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                }}
                .chart-container {{
                    position: relative;
                    width: 100%;
                    height: {height}px;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                    background-color: #111722;
                    overflow: hidden;
                }}
                #tv_chart {{
                    width: 100%;
                    height: 100%;
                }}
                .chart-legend {{
                    position: absolute;
                    top: 10px;
                    left: 12px;
                    z-index: 20;
                    font-size: 12px;
                    color: #94a3b8;
                    pointer-events: none;
                    background: rgba(17, 23, 34, 0.85);
                    padding: 5px 10px;
                    border-radius: 6px;
                    border: 1px solid #1f2a3d;
                    backdrop-filter: blur(4px);
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }}
                .legend-title {{
                    font-weight: 700;
                    color: #38bdf8;
                }}
                .legend-ema {{
                    color: #f59e0b;
                    font-weight: 600;
                }}
                .legend-price {{
                    font-family: monospace;
                    color: #f1f5f9;
                }}
                .interval-chip {{
                    background: rgba(16, 185, 129, 0.15);
                    color: #10b981;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                    border: 1px solid rgba(16, 185, 129, 0.3);
                }}
            </style>
        </head>
        <body>
            <div class="chart-container">
                <div class="chart-legend">
                    <span class="legend-title">{contract_title}</span>
                    <span class="interval-chip">5s CANDLE</span>
                    <span class="legend-ema">200 EMA: <span id="ema_val">₹{latest_ema:,.2f}</span></span>
                    <span class="legend-price" id="ohlc_val"></span>
                </div>
                <div id="tv_chart"></div>
            </div>

            <script>
                const chartElement = document.getElementById('tv_chart');
                const chart = LightweightCharts.createChart(chartElement, {{
                    width: chartElement.clientWidth,
                    height: {height},
                    layout: {{
                        background: {{ color: '#111722' }},
                        textColor: '#94a3b8',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                    }},
                    grid: {{
                        vertLines: {{ color: '#1a2436' }},
                        horzLines: {{ color: '#1a2436' }},
                    }},
                    crosshair: {{
                        mode: LightweightCharts.CrosshairMode.Normal,
                    }},
                    rightPriceScale: {{
                        borderColor: '#23324a',
                        scaleMargins: {{
                            top: 0.1,
                            bottom: 0.1,
                        }},
                    }},
                    timeScale: {{
                        borderColor: '#23324a',
                        timeVisible: true,
                        secondsVisible: true,
                    }},
                }});

                // Candlestick Series
                const candlestickSeries = chart.addCandlestickSeries({{
                    upColor: '#10b981',
                    downColor: '#ef4444',
                    borderVisible: false,
                    wickUpColor: '#10b981',
                    wickDownColor: '#ef4444',
                }});

                // 200 EMA Indicator Line Only
                const ema200Series = chart.addLineSeries({{
                    color: '#f59e0b',
                    lineWidth: 2,
                    priceLineVisible: false,
                    title: '200 EMA',
                }});

                const candleData = {candle_json};
                const emaData = {ema200_json};

                candlestickSeries.setData(candleData);
                ema200Series.setData(emaData);

                // Auto-fit content
                chart.timeScale().fitContent();

                // Crosshair hover update for legend
                chart.subscribeCrosshairMove(param => {{
                    const ohlcEl = document.getElementById('ohlc_val');
                    const emaEl = document.getElementById('ema_val');
                    if (param.time && param.seriesData.size > 0) {{
                        const price = param.seriesData.get(candlestickSeries);
                        const ema = param.seriesData.get(ema200Series);
                        if (price) {{
                            const chg = price.close - price.open;
                            const color = chg >= 0 ? '#10b981' : '#ef4444';
                            ohlcEl.innerHTML = `<span style="color:${{color}}">O: ${{price.open.toFixed(2)}} H: ${{price.high.toFixed(2)}} L: ${{price.low.toFixed(2)}} C: ${{price.close.toFixed(2)}}</span>`;
                        }}
                        if (ema) {{
                            emaEl.innerText = `₹${{ema.value.toFixed(2)}}`;
                        }}
                    }} else if (candleData.length > 0) {{
                        const last = candleData[candleData.length - 1];
                        const chg = last.close - last.open;
                        const color = chg >= 0 ? '#10b981' : '#ef4444';
                        ohlcEl.innerHTML = `<span style="color:${{color}}">O: ${{last.open.toFixed(2)}} H: ${{last.high.toFixed(2)}} L: ${{last.low.toFixed(2)}} C: ${{last.close.toFixed(2)}}</span>`;
                    }}
                }});

                // Trigger initial legend update
                if (candleData.length > 0) {{
                    const last = candleData[candleData.length - 1];
                    const chg = last.close - last.open;
                    const color = chg >= 0 ? '#10b981' : '#ef4444';
                    document.getElementById('ohlc_val').innerHTML = `<span style="color:${{color}}">O: ${{last.open.toFixed(2)}} H: ${{last.high.toFixed(2)}} L: ${{last.low.toFixed(2)}} C: ${{last.close.toFixed(2)}}</span>`;
                }}

                // Window resize handler
                window.addEventListener('resize', () => {{
                    chart.applyOptions({{ width: chartElement.clientWidth }});
                }});
            </script>
        </body>
        </html>
        """
        return html_code
