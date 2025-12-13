import requests
"interval": interval,
"limit": limit,
}
r = requests.get(url, params=params, timeout=10)
r.raise_for_status()
data = r.json()
return data["result"]["list"]




def _get_orderbook(symbol: str, limit=50):
url = f"{BASE_URL}/v5/market/orderbook"
params = {
"category": "spot",
"symbol": symbol,
"limit": limit,
}
r = requests.get(url, params=params, timeout=10)
r.raise_for_status()
return r.json()["result"]




def analyze_symbol(symbol: str) -> dict:
# ---- свечи ----
klines = _get_klines(symbol)
volumes = [float(k[5]) for k in klines]
closes = [float(k[4]) for k in klines]


last_vol = volumes[-1]
avg_vol = np.mean(volumes[:-1])
vol_ratio = last_vol / avg_vol if avg_vol > 0 else 0


price_change = (closes[-1] - closes[0]) / closes[0]


# ---- стакан ----
ob = _get_orderbook(symbol)
bids = np.array([[float(p), float(q)] for p, q in ob["b"]])
asks = np.array([[float(p), float(q)] for p, q in ob["a"]])


bid_liq = bids[:10, 1].sum()
ask_liq = asks[:10, 1].sum()
imbalance = (bid_liq - ask_liq) / (bid_liq + ask_liq)


# ---- pump score ----
score = 0
explanations = []


if vol_ratio > 2:
score += 0.4
explanations.append(f"Объём вырос в x{vol_ratio:.2f} раза")


if price_change > 0.01:
score += 0.3
explanations.append(f"Цена растёт (+{price_change*100:.2f}%)")


if imbalance > 0.2:
score += 0.3
explanations.append("В стакане доминируют bid-заявки")


score = min(score, 1.0)


return {
"pump_score": score,
"explanations": explanations,
"debug": {
"volume_ratio": vol_ratio,
"price_change": price_change,
"orderbook_imbalance": imbalance,
}
}
```python
import random


def analyze_symbol(symbol: str) -> dict:
return {
"pump_score": random.uniform(0.2, 0.9),
"explanations": [
"Резкий рост объёма",
"Увеличение количества сделок",
"Снижение ликвидности в стакане"
]
}
