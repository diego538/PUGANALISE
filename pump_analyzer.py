import requests
import time
import numpy as np

KLINE_URL = "https://api.bybit.com/v5/market/kline?category=spot&symbol={}&interval={}&limit={}"
TRADES_URL = "https://api.bybit.com/v5/market/recent-trade?category=spot&symbol={}&limit={}"
ORDERBOOK_URL = "https://api.bybit.com/v5/market/orderbook?category=spot&symbol={}&limit={}"
TICKER_URL = "https://api.bybit.com/v5/market/tickers?category=spot&symbol={}"

# Timeout for HTTP requests
REQ_TIMEOUT = 8.0

def _safe_get(url):
    try:
        r = requests.get(url, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def fetch_kline(symbol, interval="1", limit=10):
    j = _safe_get(KLINE_URL.format(symbol, interval, limit))
    if not j:
        return None
    # Bybit returns result.list usually
    res = j.get("result", {})
    data = res.get("list") or res.get("list", [])
    if not data:
        return None
    # data is list of lists: [t, open, high, low, close, volume, turnover]
    try:
        arr = []
        for row in data:
            # ensure numeric close & volume
            close = float(row[4])
            vol = float(row[5])
            arr.append({"t": row[0], "close": close, "volume": vol})
        return arr
    except Exception:
        return None

def fetch_trades(symbol, limit=200):
    j = _safe_get(TRADES_URL.format(symbol, limit))
    if not j:
        return []
    res = j.get("result", []) or []
    # result for bybit v5 recent-trade may be list of dicts with keys p (price), v (qty)
    return res

def fetch_orderbook(symbol, limit=50):
    j = _safe_get(ORDERBOOK_URL.format(symbol, limit))
    if not j:
        return {"asks": [], "bids": []}
    ob = j.get("result", {}) or {}
    asks = ob.get("asks", []) or []
    bids = ob.get("bids", []) or []
    # convert to float tuples
    try:
        asks = [(float(x[0]), float(x[1])) for x in asks]
        bids = [(float(x[0]), float(x[1])) for x in bids]
    except Exception:
        asks = []
        bids = []
    return {"asks": asks, "bids": bids}

def fetch_ticker(symbol):
    j = _safe_get(TICKER_URL.format(symbol))
    if not j:
        return None
    res = j.get("result", [])
    if isinstance(res, list) and res:
        return res[0]
    if isinstance(res, dict):
        return res
    return None

def analyze_symbol(symbol):
    """
    Analyze single symbol and return a report:
    {
      "symbol": symbol,
      "time": <unix>,
      "pump_score": 0.0..1.0,
      "indicators": { ... },
      "explanations": [ ... ],
      "raw": { ... }
    }
    """
    now = int(time.time())
    report = {"symbol": symbol, "time": now, "pump_score": 0.0, "indicators": {}, "explanations": [], "raw": {}}

    # 1) fetch data
    klines = fetch_kline(symbol, interval="1", limit=12)  # last 12 1-min candles
    trades = fetch_trades(symbol, limit=200)
    ob = fetch_orderbook(symbol, limit=50)
    ticker = fetch_ticker(symbol)

    report["raw"]["klines_len"] = len(klines) if klines else 0
    report["raw"]["trades_len"] = len(trades)
    report["raw"]["orderbook_top"] = {
        "top_ask": ob["asks"][0] if ob["asks"] else None,
        "top_bid": ob["bids"][0] if ob["bids"] else None
    }
    if ticker:
        # attempt to extract turnover24h if present
        report["raw"]["turnover24h"] = ticker.get("turnover24h") or ticker.get("quoteVolume24h") or ticker.get("volume24h")

    # If we couldn't fetch main data — report error
    if not klines:
        report["explanations"].append("Не удалось получить истории свечей (kline) с Bybit — проверь корректность тикера.")
        return report

    # Metric A: volume spike on last candle vs avg prev N
    volumes = [c["volume"] for c in klines]
    last_vol = volumes[-1]
    prev_avg = np.mean(volumes[:-1]) if len(volumes) > 1 else last_vol
    vol_spike = float(last_vol / (prev_avg + 1e-9)) if prev_avg > 0 else 0.0
    report["indicators"]["volume_spike"] = {"last_vol": float(last_vol), "avg_prev": float(prev_avg), "ratio": float(vol_spike)}
        # Metric B: trade frequency spike (recent trades count vs expected per minute)
    # approximate trades per last 1 minute via trades entries that are recent (Bybit returns trade_time_ms)
    now_ms = int(time.time() * 1000)
    recent_60s = 0
    for tr in trades:
        # try multiple possible fields
        ts = tr.get("trade_time_ms") or tr.get("t") or tr.get("ts")
        if ts:
            try:
                ts = int(ts)
                if now_ms - ts <= 60_000:
                    recent_60s += 1
            except Exception:
                continue
    # expected trades per minute from kline (estimate): assume each candle contains many trades but we use avg trades ~ len(trades)/ (recent window)
    avg_trades = max(1.0, len(trades) / 3.0)  # rough fallback
    trade_spike = float(recent_60s / (avg_trades + 1e-9))
    report["indicators"]["trade_spike"] = {"recent_60s": recent_60s, "est_avg": float(avg_trades), "ratio": float(trade_spike)}

    # Metric C: price acceleration — percent change last candle vs previous
    try:
        last_price = klines[-1]["close"]
        prev_price = klines[-2]["close"]
        older_price = klines[-3]["close"] if len(klines) > 2 else prev_price
        pct_last = (last_price - prev_price) / (prev_price + 1e-9)
        slope = (prev_price - older_price) / (older_price + 1e-9) if older_price != 0 else 0.0
    except Exception:
        pct_last = 0.0
        slope = 0.0
    report["indicators"]["price_pct"] = {"last": float(last_price), "prev": float(prev_price), "pct_change": float(pct_last), "slope": float(slope)}

    # Metric D: liquidity top_n (sum of top asks and bids)
    liq_asks = sum(q for p, q in ob["asks"][:10]) if ob["asks"] else 0.0
    liq_bids = sum(q for p, q in ob["bids"][:10]) if ob["bids"] else 0.0
    spread = None
    if ob["asks"] and ob["bids"]:
        spread = ob["asks"][0][0] - ob["bids"][0][0]
    report["indicators"]["liquidity_top10"] = {"liq_asks": float(liq_asks), "liq_bids": float(liq_bids), "spread": float(spread) if spread is not None else None}

    # Metric E: orderbook imbalance (ask vs bid)
    imbalance = 0.0
    if (liq_asks + liq_bids) > 0:
        imbalance = (liq_bids - liq_asks) / (liq_asks + liq_bids)
    report["indicators"]["orderbook_imbalance"] = {"imbalance": float(imbalance)}

    # Heuristic spoofing (single-run: look for abnormally large single top orders)
    # If top order > 25% of top10 liquidity -> possible wall (could be spoof)
    top_large = False
    large_info = None
    prev_top10 = liq_asks + liq_bids
    if prev_top10 > 0:
        # find any top 3 orders > 25% of prev_top10
        for side, arr in (("asks", ob["asks"][:3]), ("bids", ob["bids"][:3])):
            for p, q in arr:
                if q / (prev_top10 + 1e-9) > 0.25:
                    top_large = True
                    large_info = {"side": side, "price": float(p), "qty": float(q)}
                    break
            if top_large:
                break
    report["indicators"]["possible_large_wall"] = {"found": bool(top_large), "info": large_info}

    # Compose weighted PumpScore: weights chosen to favor volume and trade spikes + price action + low liquidity + large wall removal
    score = 0.0
    # volume spike weight
    score += 0.45 * min(vol_spike / 5.0, 1.0)   # vol_spike of ~5 gives max contribution
    # trade freq
    score += 0.25 * min(trade_spike / 5.0, 1.0)
    # price pct: 1% in 1min is meaningful
    score += 0.15 * min(abs(pct_last) / 0.01, 1.0)
    # low liquidity => easier to pump
    top_liq_avg = (liq_asks + liq_bids) / 2.0
    if top_liq_avg < 50:
        score += 0.15
    elif top_liq_avg < 200:
        score += 0.06
    # large single wall increases suspicion
    if top_large:
        score += 0.12

    # clamp 0..1
    score = max(0.0, min(1.0, score))
    report["pump_score"] = float(score)

    # Explanations: produce human-readable bullets
    expl = []
    # volume
    if vol_spike > 2.0:
        expl.append(f"Всплеск объёма: текущая свеча x{vol_spike:.2f} от средней — сильный индикатор накопления.")
            elif vol_spike > 1.2:
        expl.append(f"Умеренный рост объёма: текущая свеча x{vol_spike:.2f} от средней.")
    else:
        expl.append("Объём в текущей свече не выдающийся.")

    # trades
    if trade_spike > 2.0:
        expl.append(f"Рост частоты сделок за 60с: {recent_60s} сделок (≈ x{trade_spike:.2f}). Это часто сопровождает wash-trading/накопление.")
    elif recent_60s > 0:
        expl.append(f"Небольшая активность сделок: {recent_60s} за последнюю минуту.")
    else:
        expl.append("Сделок за последнюю минуту мало или данные не полные.")

    # price
    if abs(pct_last) > 0.01:
        expl.append(f"Быстрый прирост цены: {pct_last*100:.2f}% за последнюю минуту.")
    elif abs(pct_last) > 0.002:
        expl.append(f"Небольшая ценовая волатильность: {pct_last*100:.2f}% за последнюю минуту.")
    else:
        expl.append("Цена держится стабильно, резкого движения нет.")

    # liquidity
    expl.append(f"Доступная ликвидность (top10): asks={liq_asks:.4f}, bids={liq_bids:.4f}, spread={spread}")

    # large wall
    if top_large and large_info:
        expl.append(f"Обнаружено крупное лимитное размещение на стороне {large_info['side']} — qty={large_info['qty']:.4f} @ {large_info['price']}. Может быть стеной или подготовкой к spoofing.")
    else:
        expl.append("Крупных одиночных стен в топ-3 не обнаружено.")

    # add summary verdict
    if score >= 0.7:
        expl.append("Вердикт: Высокая вероятность подготовки пампа (реакция — мониторить в реальном времени / рассмотреть вход с осторожностью).")
    elif score >= 0.4:
        expl.append("Вердикт: Средняя вероятность пампа (следить за динамикой 1–3 минут).")
    elif score > 0.01:
        expl.append("Вердикт: Низкая вероятность, есть некоторые признаки — наблюдать.")
    else:
        expl.append("Вердикт: Признаков подготовки пампа не обнаружено.")

    report["explanations"] = expl
    return report
            
        
