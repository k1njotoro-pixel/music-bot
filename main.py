import json
import os
import random
import telebot
from telebot import types

TOKEN = "8623102402:AAHDwi8CbD1jZaK1qkWUiWzT81sVfMahQTA"
ADMIN_ID = 8859654422

DB_FILE = "bot_data.json"

bot = telebot.TeleBot(TOKEN)

# Состояния для ожидания ввода
USER_STATES = {}  # {user_id: "state"}

# Доступные жанры и их хэштеги
GENRES = {
    "🌧 Грустное": "грустное",
    "🎉 Весёлое": "веселое",
    "📼 Ностальгия": "ностальгия",
    "☕ Душевное": "душевное",
    "🔥 ТТ 2026": "тт2026",
}


# --- Работа с базой данных (JSON) ---
def load_data():
    default_data = {
        "users": [],
        "tracks": {
            "all": [],
            "грустное": [],
            "веселое": [],
            "ностальгия": [],
            "душевное": [],
            "тт2026": [],
        },
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_data
    return default_data


def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- Клавиатуры ---
def get_main_keyboard(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(types.KeyboardButton("🎲 Любая песня"))
    kb.add(
        types.KeyboardButton("🌧 Грустное"), types.KeyboardButton("🎉 Весёлое")
    )
    kb.add(
        types.KeyboardButton("📼 Ностальгия"),
        types.KeyboardButton("☕ Душевное"),
    )
    kb.add(
        types.KeyboardButton("🔥 ТТ 2026"),
        types.KeyboardButton("✍️ Предложить трек"),
    )
    if user_id == ADMIN_ID:
        kb.add(types.KeyboardButton("⚙️ Админ-панель"))
    return kb


def get_admin_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(
            "📊 Статистика", callback_data="admin_stats"
        ),
        types.InlineKeyboardButton(
            "📢 Сделать рассылку", callback_data="admin_broadcast"
        ),
    )
    return kb


# --- Команда /start ---
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    data = load_data()

    if user_id not in data["users"]:
        data["users"].append(user_id)
        save_data(data)

    USER_STATES[user_id] = None
    bot.send_message(
        message.chat.id,
        "Салам! Выбирай категорию или жми «Любая песня» 🎧",
        reply_markup=get_main_keyboard(user_id),
    )


# --- Админ-панель: команда и кнопка ---
@bot.message_handler(
    func=lambda msg: msg.text == "⚙️ Админ-панель"
    and msg.from_user.id == ADMIN_ID
)
@bot.message_handler(
    commands=["admin"], func=lambda msg: msg.from_user.id == ADMIN_ID
)
def admin_panel(message):
    bot.send_message(
        message.chat.id,
        "Панель администратора:",
        reply_markup=get_admin_keyboard(),
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call):
    if call.from_user.id != ADMIN_ID:
        return

    data = load_data()

    if call.data == "admin_stats":
        total_users = len(data["users"])
        total_tracks = len(data["tracks"]["all"])
        stats_text = (
            f"📊 **Статистика бота:**\n\n"
            f"👥 Пользователей: `{total_users}`\n"
            f"🎵 Всего треков: `{total_tracks}`\n\n"
            f"• Грустное: `{len(data['tracks'].get('грустное', []))}`\n"
            f"• Весёлое: `{len(data['tracks'].get('веселое', []))}`\n"
            f"• Ностальгия: `{len(data['tracks'].get('ностальгия', []))}`\n"
            f"• Душевное: `{len(data['tracks'].get('душевное', []))}`\n"
            f"• ТТ 2026: `{len(data['tracks'].get('тт2026', []))}`"
        )
        bot.send_message(call.message.chat.id, stats_text, parse_mode="Markdown")

    elif call.data == "admin_broadcast":
        USER_STATES[ADMIN_ID] = "waiting_broadcast"
        bot.send_message(
            call.message.chat.id,
            "Отправь сообщение (текст, фото или кружок), которое нужно разослать всем пользователям. Для отмены напи
