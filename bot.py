from loader import bot
from pump_analyzer import analyze_symbol


WAITING_FOR_TICKER = set()


WELCOME = (
"Привет! Я монитор пампов (Bybit). 👋\n\n"
"Отправь тикер токена, например: ZKLUSDT или ZKL (ТОЛЬКО ЗАГЛАВНЫМИ).\n"
"После этого я пришлю отчёт о возможной подготовке пампа."
)


@bot.message_handler(commands=['start'])
def start_handler(message):
chat_id = message.chat.id
bot.send_message(chat_id, WELCOME)
bot.send_message(chat_id, "Введи тикер:")
WAITING_FOR_TICKER.add(chat_id)


@bot.message_handler(func=lambda m: m.chat.id in WAITING_FOR_TICKER)
def ticker_handler(message):
chat_id = message.chat.id
text = message.text.strip()


if not text:
bot.send_message(chat_id, "Пусто. Введи тикер, например ZKLUSDT")
return


if text != text.upper():
bot.send_message(chat_id, "Используй ТОЛЬКО заглавные буквы")
return


symbol = text if text.endswith("USDT") else text + "USDT"
WAITING_FOR_TICKER.discard(chat_id)


bot.send_message(chat_id, f"🔍 Анализирую `{symbol}`... Подожди 5–10 секунд")


try:
report = analyze_symbol(symbol)
except Exception as e:
bot.send_message(chat_id, f"❌ Ошибка анализа: {e}")
return


if "pump_score" not in report:
bot.send_message(chat_id, "❌ Нет данных по тикеру")
return


score = int(report['pump_score'] * 100)
lines = [
f"📊 *Отчёт по* `{symbol}`",
f"🔥 PumpScore: *{score}%*",
""
]


for text in report.get("explanations", []):
lines.append(f"• {text}")


bot.send_message(chat_id, "\n".join(lines))


@bot.message_handler(func=lambda m: True)
def fallback(message):
bot.send_message(message.chat.id, "Введи /start для начала анализа")


if __name__ == '__main__':
bot.infinity_polling()
