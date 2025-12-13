import os
import telebot
from dotenv import load_dotenv


load_dotenv()


TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
raise RuntimeError("❌ BOT_TOKEN не задан в окружении")


bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")
