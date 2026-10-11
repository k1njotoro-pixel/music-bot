import json
import os
import random
import telebot
from telebot import types

TOKEN = "8623102402:AAHDwi8CbD1jZaK1qkWUiWzT81sVfMahQTA"
ADMIN_ID = 8859654422

DB_FILE = "bot_data.json"

bot = telebot.TeleBot(TOKEN)

# Хранилище временных состояний пользователей
user_states = {}


# --- Работа с базой данных ---
def load_data():
    default_data = {
        "users": [],
        "tracks": {
            "all": [],
            "грустное": [],
            "веселое": [],
            "ностальгия": [],
            "подушам": [],
            "тт2026": [],
        },
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in default_data["tracks"]:
                    if key not in data.get("tracks", {}):
                        data.setdefault("tracks", {})[key] = []
                data.setdefault("users", [])
                return data
        except Exception:
            return default_data
    return default_data


def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- Клавиатуры ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🎲 Любой трек"),
        types.KeyboardButton("📂 Выбрать жанр"),
        types.KeyboardButton("🎧 Предложить трек"),
    )
    return markup


def get_genres_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🌧 Грустное"),
        types.KeyboardButton("⚡ Веселое"),
        types.KeyboardButton("📼 Ностальгия"),
        types.KeyboardButton("☕ По душам"),
        types.KeyboardButton("🔥 ТТ 2026"),
        types.KeyboardButton("🔙 Назад"),
    )
    return markup


def get_admin_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
    )
    return markup


# --- Старт ---
@bot.message_handler(commands=["start"])
def start(message):
    data = load_data()
    if message.chat.id not in data["users"]:
        data["users"].append(message.chat.id)
        save_data(data)

    user_states.pop(message.chat.id, None)
    text = (
        "Салам! Выбирай категорию или жми «Любой трек», чтобы заценить музыку 🎧"
    )
    bot.send_message(
        message.chat.id, text, reply_markup=get_main_keyboard()
    )


# --- Админ панель ---
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(
        message.chat.id, "Панель администратора:", reply_markup=get_admin_keyboard()
    )


# --- Обработка перехвата музыки из канала ---
@bot.channel_post_handler(content_types=["audio"])
def handle_channel_audio(message):
    file_id = message.audio.file_id
    caption = (message.caption or "").lower()

    data = load_data()

    if file_id not in data["tracks"]["all"]:
        data["tracks"]["all"].append(file_id)

    genre_tags = {
        "#грустное": "грустное",
        "#веселое": "веселое",
        "#ностальгия": "ностальгия",
        "#подушам": "подушам",
        "#тт2026": "тт2026",
    }

    found_genre = False
    for tag, cat in genre_tags.items():
        if tag in caption:
            if file_id not in data["tracks"][cat]:
                data["tracks"][cat].append(file_id)
            found_genre = True

    save_data(data)
    print(
        f"Новый трек: {message.audio.title or 'Без названия'} (Теги найдены: {found_genre})"
    )


# --- Навигация по кнопкам ---
@bot.message_handler(
    func=lambda msg: msg.text in ["🔙 Назад", "🎲 Любой трек", "📂 Выбрать жанр"]
)
def handle_navigation(message):
    user_states.pop(message.chat.id, None)

    if message.text == "🔙 Назад":
        bot.send_message(
            message.chat.id, "Главное меню:", reply_markup=get_main_keyboard()
        )
    elif message.text == "📂 Выбрать жанр":
        bot.send_message(
            message.chat.id,
            "Выбери нужный жанр:",
            reply_markup=get_genres_keyboard(),
        )
    elif message.text == "🎲 Любой трек":
        data = load_data()
        all_tracks = data["tracks"]["all"]
        if not all_tracks:
            bot.send_message(message.chat.id, "Треков пока нет!")
            return
        bot.send_audio(message.chat.id, random.choice(all_tracks))


# --- Выдача по конкретным жанрам ---
GENRE_MAP = {
    "🌧 Грустное": "грустное",
    "⚡ Веселое": "веселое",
    "📼 Ностальгия": "ностальгия",
    "☕ По душам": "подушам",
    "🔥 ТТ 2026": "тт2026",
}


@bot.message_handler(func=lambda msg: msg.text in GENRE_MAP)
def handle_genre_pick(message):
    cat = GENRE_MAP[message.text]
    data = load_data()
    tracks = data["tracks"].get(cat, [])

    if not tracks:
        bot.send_message(
            message.chat.id,
            f"В категории «{message.text}» пока нет треков. Закинь их в канал с тегом #{cat}!",
        )
        return

    bot.send_audio(message.chat.id, random.choice(tracks))


# --- Предложить трек ---
@bot.message_handler(func=lambda msg: msg.text == "🎧 Предложить трек")
def propose_track_start(message):
    user_states[message.chat.id] = "waiting_track"
    bot.send_message(
        message.chat.id,
        "Отправь мне аудиофайл трека (или напиши название и автора), и админ рассмотрит его!",
    )


# --- Прием трека / рассылка ---
@bot.message_handler(
    content_types=[
        "text",
        "audio",
        "voice",
        "video",
        "photo",
        "document",
    ]
)
def handle_incoming(message):
    state = user_states.get(message.chat.id)

    # Режим рассылки от админа
    if state == "waiting_broadcast" and message.chat.id == ADMIN_ID:
        user_states.pop(message.chat.id, None)
        data = load_data()
        users = data.get("users", [])
        sent = 0

        bot.send_message(ADMIN_ID, f"Начинаю рассылку для {len(users)} пользователей...")
        for uid in users:
            try:
                bot.copy_message(chat_id=uid, from_chat_id=ADMIN_ID, message_id=message.message_id)
                sent += 1
            except Exception:
                pass

        bot.send_message(ADMIN_ID, f"Рассылка завершена! Доставлено: {sent}/{len(users)}")
        return

    # Пользователь прислал трек в предложку
    if state == "waiting_track":
        user_states.pop(message.chat.id, None)

        bot.send_message(
            message.chat.id,
            "Спасибо! Трек отправлен на проверку админу.",
            reply_markup=get_main_keyboard(),
        )

        admin_inline = types.InlineKeyboardMarkup()
        admin_inline.add(
            types.InlineKeyboardButton(
                "❌ Отклонить", callback_data=f"reject_{message.chat.id}"
            )
        )

        bot.send_message(
            ADMIN_ID,
            f"📥 <b>Новая предложка!</b>\nОт: @{message.from_user.username or 'без_юзернейма'} (ID: {message.chat.id})",
            parse_mode="HTML",
        )
        bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=admin_inline,
        )
        return


# --- Коллбэки админки (статистика, рассылка, отклонение) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "admin_stats" and call.message.chat.id == ADMIN_ID:
        data = load_data()
        users_count = len(data.get("users", []))
        tracks = data.get("tracks", {})
        all_t = len(tracks.get("all", []))

        text = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👤 Пользователей: <code>{users_count}</code>\n"
            f"🎵 Всего треков: <code>{all_t}</code>\n\n"
            f"• 🌧 Грустное: {len(tracks.get('грустное', []))}\n"
            f"• ⚡ Веселое: {len(tracks.get('веселое', []))}\n"
            f"• 📼 Ностальгия: {len(tracks.get('ностальгия', []))}\n"
            f"• ☕ По душам: {len(tracks.get('подушам', []))}\n"
            f"• 🔥 ТТ 2026: {len(tracks.get('тт2026', []))}"
        )
        bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    elif call.data == "admin_broadcast" and call.message.chat.id == ADMIN_ID:
        user_states[ADMIN_ID] = "waiting_broadcast"
        bot.send_message(
            ADMIN_ID,
            "Пришли сообщение (текст, фото с описанием или аудио), которое нужно разослать всем пользователям:",
        )
        bot.answer_callback_query(call.id)

    elif call.data.startswith("reject_"):
        user_id = int(call.data.split("_")[1])
        try:
            bot.send_message(
                user_id,
                "К сожалению, твой предложенный трек не подошел по формату. Но ты можешь предложить другой!",
            )
        except Exception:
            pass
        bot.edit_message_caption(
            caption=(call.message.caption or "") + "\n\n❌ <i>Отклонено</i>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id, text="Трек отклонен")


bot.infinity_polling()
