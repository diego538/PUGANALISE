🐉, [07.12.2025 23:46]
import telebot
import time
from loader import bot
from pump_analyzer import analyze_symbol

# simple in-memory state for users waiting to input ticker
WAITING_FOR_TICKER = set()

WELCOME = (
    "Привет! Я монитор пампов (Bybit). 👋\n\n"
    "Отправь тикер токена в формате, например: ZKLUSDT или ZKL (без кавычек). "
    "Только ЗАГЛАВНЫЕ буквы — если ты ввёл строчные, я попрошу повторить.\n\n"
    "После ввода я проанализирую указанный тикер и пришлю подробный отчёт о признаках подготовки пампа."
)

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, WELCOME)
    bot.send_message(chat_id, "Введи тикер (uppercase):")
    WAITING_FOR_TICKER.add(chat_id)

@bot.message_handler(func=lambda m: m.chat.id in WAITING_FOR_TICKER)
def handle_ticker_input(message):
    chat_id = message.chat.id
    text = message.text.strip()
    # basic normalization: if user typed lowercase, prompt to use uppercase
    if not text:
        bot.send_message(chat_id, "Пустая строка — введи тикер, например: `ZKLUSDT`")
        return

    # accept either ZKL or ZKLUSDT
    t = text.strip()
    # enforce uppercase letters & digits and optionally ending with USDT
    if t != t.upper():
        bot.send_message(chat_id, "Пожалуйста, введи тикер ЗАГЛАВНЫМИ буквами, например ZKLUSDT.")
        return

    # if user provided 'ZKL' -> append USDT
    if t.endswith("USDT"):
        symbol = t
    else:
        symbol = t + "USDT"

    bot.send_message(chat_id, f"Принят тикер: {symbol}. Запускаю анализ — это займёт ~5–12 секунд...", parse_mode="Markdown")
    WAITING_FOR_TICKER.discard(chat_id)

    try:
        report = analyze_symbol(symbol)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при анализе: {e}")
        return

    # format result
    if "pump_score" not in report:
        bot.send_message(chat_id, "Не удалось получить отчёт по тикеру — возможно неверный символ или проблемы с API Bybit.")
        return

    score_pct = int(report["pump_score"] * 100)
    lines = []
    lines.append(f"📊 Отчёт по `{symbol}`")
    lines.append(f"PumpScore: *{score_pct}%*")
    lines.append("")
    # add raw indicators
    ind = report.get("indicators", {})
    vs = ind.get("volume_spike")
    if vs:
        lines.append(f"• Объём: текущая свеча = {vs['last_vol']:.6f}, средняя предыдущих = {vs['avg_prev']:.6f}, отношение = x{vs['ratio']:.2f}")

    ts = ind.get("trade_spike")
    if ts:
        lines.append(f"• Сделки: за 60s ≈ {ts['recent_60s']}, ожидаемо ≈ {ts['est_avg']:.1f}, отношение = x{ts['ratio']:.2f}")

    pp = ind.get("price_pct")
    if pp:
        lines.append(f"• Цена: последняя = {pp['last']:.8f}, изменение = {pp['pct_change']*100:.3f}% (по последним свечам)")

    liq = ind.get("liquidity_top10")
    if liq:
        lines.append(f"• Ликвидность top10 (asks/bids) = {liq['liq_asks']:.6f} / {liq['liq_bids']:.6f}, spread = {liq['spread']}")

    imb = ind.get("orderbook_imbalance")
    if imb:
        lines.append(f"• Imbalance (bid-ask) = {imb['imbalance']:.3f} (положительное → больше bid)")

    wall = ind.get("possible_large_wall")
    if wall:
        if wall["found"]:
            info = wall["info"]
            lines.append(f"• Крупная стенка обнаружена: сторона {info['side']}, qty={info['qty']:.6f} @ {info['price']}")
        else:
            lines.append("• Крупных стен в топ-3 не обнаружено")

    lines.append("")
    lines.append("*Объяснение по пунктам:*")
    for ex in report.get("explanations", []):
        lines.append(f"• {ex}")

    # send as Markdown (escape backticks already in symbol)
    final_text = "\n".join(lines)
    try:
        bot.send_message(chat_id, final_text, parse_mode="Markdown")
    except Exception as e:
        # fallback to plain text
        bot.send_message(chat_id, "Ошибка отправки в Markdown, отправляю в plain text.")
        bot.send_message(chat_id, final_text.replace("*", ""))

# help fallback
@bot.message_handler(func=lambda m: True)
def fallback(m):
    bot.send_message(m.chat.

🐉, [07.12.2025 23:46]
id, "Чтобы запустить анализ — введи /start и следуй инструкциям.")
