import os
import telebot

def _get_env(key):
    v = os.getenv(key)
    return v.strip() if v else None

BOT_TOKEN = _get_env("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в переменных окружения BotHost! Добавь BOT_TOKEN в Settings → Environment Variables")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
