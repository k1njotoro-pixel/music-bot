import json
import os
import random
import time
import telebot
from telebot import types

TOKEN = "8623102402:AAHDwi8CbD1jZaK1qkWUiWzT81sVfMahQTA"
ADMIN_ID = 8859654422
CHANNEL_ID = -1003918122345

DB_FILE = "bot_data.json"
COOLDOWN_SECONDS = 3

bot = telebot.TeleBot(TOKEN)

user_states = {}
pending_tracks = {}
last_action_time = {}


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
        "lyrics": {},  # file_id: текст
        "track_of_day": None,  # file_id трека дня
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key in default_data["tracks"]:
                    if key not in data.get("tracks", {}):
                        data.setdefault("tracks", {})[key] = []
                data.setdefault("users", [])
                data.setdefault("lyrics", {})
                data.setdefault("track_of_day", None)
                return data
        except Exception:
            return default_data
    return default_data


def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# --- Проверка антиспама ---
def check_cooldown(user_id):
    if user_id == ADMIN_ID:
        return True
    now = time.time()
    last_time = last_action_time.get(user_id, 0)
    if now - last_time < COOLDOWN_SECONDS:
        return False
    last_action_time[user_id] = now
    return True


# --- Клавиатуры ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🎲 Любой трек"),
        types.KeyboardButton("🔥 Трек дня"),
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
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🌟 Задать трек дня", callback_data="admin_set_tod"),
    )
    return markup


def get_track_inline_kb(file_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📜 Текст песни", callback_data=f"lyrics_{file_id}"))
    return markup


# --- Старт ---
@bot.message_handler(commands=["start"])
def start(message):
    data = load_data()
    if message.chat.id not in data["users"]:
        data["users"].append(message.chat.id)
        save_data(data)

    user_states.pop(message.chat.id, None)
    bot.send_message(
        message.chat.id,
        "Салам! Выбирай категорию или жми «Любой трек», чтобы послушать музыку 🎧",
        reply_markup=get_main_keyboard(),
    )


# --- Админ панель ---
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(message.chat.id, "Панель администратора:", reply_markup=get_admin_keyboard())


# --- Перехват постов из канала ---
@bot.channel_post_handler(content_types=["audio"])
def handle_channel_audio(message):
    file_id = message.audio.file_id
    raw_caption = message.caption or ""
    caption = raw_caption.lower()

    data = load_data()
    if file_id not in data["tracks"]["all"]:
        data["tracks"]["all"].append(file_id)

    # Если в подписи был текст с пометкой текста песни (например: Текст: ...)
    if "текст:" in caption:
        lyrics_text = raw_caption.split("текст:", 1)[1].strip()
        data["lyrics"][file_id] = lyrics_text

    genre_tags = {
        "#грустное": "грустное",
        "#веселое": "веселое",
        "#ностальгия": "ностальгия",
        "#подушам": "подушам",
        "#тт2026": "тт2026",
    }

    for tag, cat in genre_tags.items():
        if tag in caption and file_id not in data["tracks"][cat]:
            data["tracks"][cat].append(file_id)

    save_data(data)


# --- Навигация и получение треков ---
@bot.message_handler(
    func=lambda msg: msg.text in ["🔙 Назад", "🎲 Любой трек", "📂 Выбрать жанр", "🔥 Трек дня"]
)
def handle_navigation(message):
    if not check_cooldown(message.chat.id):
        bot.send_message(message.chat.id, "⏳ Подожди пару секунд перед следующим выбором!")
        return

    user_states.pop(message.chat.id, None)

    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=get_main_keyboard())

    elif message.text == "📂 Выбрать жанр":
        bot.send_message(message.chat.id, "Выбери нужный жанр:", reply_markup=get_genres_keyboard())

    elif message.text == "🔥 Трек дня":
        data = load_data()
        tod = data.get("track_of_day")
        if not tod:
            bot.send_message(message.chat.id, "Трек дня ещё не выбран админом! Попробуй «Любой трек».")
            return
        bot.send_audio(
            message.chat.id,
            tod,
            caption="🌟 <b>Главный трек сегодняшнего дня!</b>",
            parse_mode="HTML",
            reply_markup=get_track_inline_kb(tod),
        )

    elif message.text == "🎲 Любой трек":
        data = load_data()
        all_tracks = data["tracks"]["all"]
        if not all_tracks:
            bot.send_message(message.chat.id, "Треков пока нет!")
            return
        chosen = random.choice(all_tracks)
        bot.send_audio(message.chat.id, chosen, reply_markup=get_track_inline_kb(chosen))


# --- Жанры ---
GENRE_MAP = {
    "🌧 Грустное": "грустное",
    "⚡ Веселое": "веселое",
    "📼 Ностальгия": "ностальгия",
    "☕ По душам": "подушам",
    "🔥 ТТ 2026": "тт2026",
}


@bot.message_handler(func=lambda msg: msg.text in GENRE_MAP)
def handle_genre_pick(message):
    if not check_cooldown(message.chat.id):
        bot.send_message(message.chat.id, "⏳ Подожди пару секунд!")
        return

    cat = GENRE_MAP[message.text]
    data = load_data()
    tracks = data["tracks"].get(cat, [])

    if not tracks:
        bot.send_message(
            message.chat.id,
            f"В категории «{message.text}» пока нет треков. Закинь их в канал с тегом #{cat}!",
        )
        return

    chosen = random.choice(tracks)
    bot.send_audio(message.chat.id, chosen, reply_markup=get_track_inline_kb(chosen))


# --- Предложить трек ---
@bot.message_handler(func=lambda msg: msg.text == "🎧 Предложить трек")
def propose_track_start(message):
    user_states[message.chat.id] = "waiting_track"
    bot.send_message(
        message.chat.id,
        "Отправь аудиофайл (mp3), который хочешь предложить в канал:",
    )


# --- Обработка ввода (рассылка, установка трека дня, предложка) ---
@bot.message_handler(
    content_types=["text", "audio", "voice", "video", "photo", "document"]
)
def handle_incoming(message):
    state = user_states.get(message.chat.id)

    # Админ ставит трек дня
    if state == "waiting_tod" and message.chat.id == ADMIN_ID:
        user_states.pop(message.chat.id, None)
        if message.content_type != "audio":
            bot.send_message(ADMIN_ID, "Нужно было прислать аудиофайл! Отменено.")
            return

        data = load_data()
        data["track_of_day"] = message.audio.file_id
        if message.audio.file_id not in data["tracks"]["all"]:
            data["tracks"]["all"].append(message.audio.file_id)
        save_data(data)

        bot.send_message(ADMIN_ID, "✅ Трек дня успешно обновлен!")
        return

    # Админ делает рассылку
    if state == "waiting_broadcast" and message.chat.id == ADMIN_ID:
        user_states.pop(message.chat.id, None)
        data = load_data()
        users = data.get("users", [])
        sent = 0

        bot.send_message(ADMIN_ID, f"Рассылаю для {len(users)} пользователей...")
        for uid in users:
            try:
                bot.copy_message(
                    chat_id=uid,
                    from_chat_id=ADMIN_ID,
                    message_id=message.message_id,
                )
                sent += 1
            except Exception:
                pass

        bot.send_message(ADMIN_ID, f"Рассылка завершена! Доставлено: {sent}/{len(users)}")
        return

    # Предложка от пользователя
    if state == "waiting_track":
        if message.content_type != "audio":
            bot.send_message(message.chat.id, "Пожалуйста, пришли именно аудиофайл (музыку).")
            return

        user_states.pop(message.chat.id, None)
        req_id = str(message.message_id)

        pending_tracks[req_id] = {
            "user_id": message.chat.id,
            "file_id": message.audio.file_id,
            "title": message.audio.title or "Без названия",
            "performer": message.audio.performer or "Неизвестен",
            "username": message.from_user.username or message.from_user.first_name,
        }

        bot.send_message(
            message.chat.id,
            "Спасибо! Трек отправлен админу на оценку 🎵",
            reply_markup=get_main_keyboard(),
        )

        admin_kb = types.InlineKeyboardMarkup(row_width=2)
        admin_kb.add(
            types.InlineKeyboardButton("✅ Одобрить и в тгк", callback_data=f"approve_{req_id}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{req_id}"),
        )

        user_mention = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        caption = (
            f"📥 <b>Новая предложка</b> от {user_mention}\n"
            f"Трек: <i>{pending_tracks[req_id]['performer']} — {pending_tracks[req_id]['title']}</i>"
        )

        bot.send_audio(
            ADMIN_ID,
            message.audio.file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=admin_kb,
        )
        return


# --- Коллбэки инлайн-кнопок ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    # Показ текста песни
    if call.data.startswith("lyrics_"):
        file_id = call.data.split("_", 1)[1]
        data = load_data()
        lyrics = data.get("lyrics", {}).get(file_id)

        if lyrics:
            bot.send_message(call.message.chat.id, f"📜 <b>Текст песни:</b>\n\n{lyrics}", parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id, "К этому треку пока не добавлен текст песни.")
        bot.answer_callback_query(call.id)
        return

    # Админка: Статистика
    if call.data == "admin_stats" and call.message.chat.id == ADMIN_ID:
        data = load_data()
        users_count = len(data.get("users", []))
        tracks = data.get("tracks", {})

        text = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👤 Пользователей: <code>{users_count}</code>\n"
            f"🎵 Всего треков: <code>{len(tracks.get('all', []))}</code>\n\n"
            f"• 🌧 Грустное: {len(tracks.get('грустное', []))}\n"
            f"• ⚡ Веселое: {len(tracks.get('веселое', []))}\n"
            f"• 📼 Ностальгия: {len(tracks.get('ностальгия', []))}\n"
            f"• ☕ По душам: {len(tracks.get('подушам', []))}\n"
            f"• 🔥 ТТ 2026: {len(tracks.get('тт2026', []))}"
        )
        bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        bot.answer_callback_query(call.id)

    # Админка: Рассылка
    elif call.data == "admin_broadcast" and call.message.chat.id == ADMIN_ID:
        user_states[ADMIN_ID] = "waiting_broadcast"
        bot.send_message(ADMIN_ID, "Пришли сообщение для рассылки:")
        bot.answer_callback_query(call.id)

    # Админка: Назначить трек дня
    elif call.data == "admin_set_tod" and call.message.chat.id == ADMIN_ID:
        user_states[ADMIN_ID] = "waiting_tod"
        bot.send_message(ADMIN_ID, "Пришли аудиофайл, который станет новым «Треком дня»:")
        bot.answer_callback_query(call.id)

    # Одобрение предложки
    elif call.data.startswith("approve_"):
        req_id = call.data.split("_")[1]
        track_info = pending_tracks.get(req_id)

        if not track_info:
            bot.answer_callback_query(call.id, "Данные устарели")
            return

        post_caption = (
            f"🎧 <b>Новый трек из предложки!</b>\n\n"
            f"👤 Предложил: {track_info['username']}\n"
            f"🔥 Приятного прослушивания!"
        )

        try:
            bot.send_audio(
                CHANNEL_ID,
                track_info["file_id"],
                caption=post_caption,
                parse_mode="HTML",
            )

            data = load_data()
            if track_info["file_id"] not in data["tracks"]["all"]:
                data["tracks"]["all"].append(track_info["file_id"])
                save_data(data)

            bot.send_message(
                track_info["user_id"],
                "🔥 Твой трек одобрен и выложен в канал! Спасибо.",
            )

            bot.edit_message_caption(
                caption=call.message.caption + "\n\n✅ <b>Опубликовано в канал</b>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
            )
            bot.answer_callback_query(call.id, "Опубликовано!")
            pending_tracks.pop(req_id, None)
        except Exception as e:
            bot.send_message(ADMIN_ID, f"Ошибка публикации в канал: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    # Отклонение предложки
    elif call.data.startswith("reject_"):
        req_id = call.data.split("_")[1]
        track_info = pending_tracks.get(req_id)

        if track_info:
            try:
                bot.send_message(track_info["user_id"], "К сожалению, трек не подошел.")
            except Exception:
                pass
            pending_tracks.pop(req_id, None)

        bot.edit_message_caption(
            caption=(call.message.caption or "") + "\n\n❌ <b>Отклонено</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML",
        )
        bot.answer_callback_query(call.id, "Отклонено")


print("Бот успешно запущен!")
bot.infinity_polling()
