import json
import os
import random
import telebot
from telebot import types

TOKEN = "8623102402:AAHDwi8CbD1jZaK1qkWUiWzT81sVfMahQTA"
ADMIN_ID = 8859654422
CHANNEL_ID = -1003918122345

DB_FILE = "bot_data.json"

bot = telebot.TeleBot(TOKEN)

user_states = {}
pending_tracks = {}


# --- База данных ---
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
        "lyrics": {},
        "ratings": {},   # file_id: {"likes": [], "dislikes": []}
        "favorites": {}, # user_id: [file_id, ...]
        "track_of_day": None,
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("users", [])
                data.setdefault("lyrics", {})
                data.setdefault("ratings", {})
                data.setdefault("favorites", {})
                data.setdefault("track_of_day", None)
                tracks = data.setdefault("tracks", {})
                for k in ["all", "грустное", "веселое", "ностальгия", "подушам", "тт2026"]:
                    tracks.setdefault(k, [])
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
        types.KeyboardButton("🔥 Трек дня"),
        types.KeyboardButton("📂 Выбрать жанр"),
        types.KeyboardButton("⭐ Моё избранное"),
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


def get_track_inline_kb(file_id, data):
    ratings = data.get("ratings", {}).get(file_id, {"likes": [], "dislikes": []})
    likes_count = len(ratings.get("likes", []))
    dislikes_count = len(ratings.get("dislikes", []))

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_like = types.InlineKeyboardButton(f"👍 {likes_count}", callback_data=f"like_{file_id}")
    btn_dislike = types.InlineKeyboardButton(f"👎 {dislikes_count}", callback_data=f"dislike_{file_id}")
    btn_fav = types.InlineKeyboardButton("⭐ В избранное", callback_data=f"fav_{file_id}")
    btn_lyrics = types.InlineKeyboardButton("📜 Текст песни", callback_data=f"lyrics_{file_id}")

    markup.add(btn_like, btn_dislike)
    markup.add(btn_fav, btn_lyrics)
    return markup


def get_admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🌟 Задать трек дня", callback_data="admin_set_tod"),
    )
    return markup


# --- Команда /start ---
@bot.message_handler(commands=["start"])
def cmd_start(message):
    data = load_data()
    if message.chat.id not in data["users"]:
        data["users"].append(message.chat.id)
        save_data(data)

    user_states.pop(message.chat.id, None)
    bot.send_message(
        message.chat.id,
        "Салам! Врубай треки, ставь лайки и сохраняй в избранное 🎧",
        reply_markup=get_main_keyboard(),
    )


# --- Команда /admin ---
@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(
        message.chat.id,
        "🛠 <b>Панель администратора</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard(),
    )


# --- Автоматический перехват постов из канала ---
@bot.channel_post_handler(content_types=["audio"])
def handle_channel_audio(message):
    file_id = message.audio.file_id
    raw_caption = message.caption or ""
    caption = raw_caption.lower()

    data = load_data()
    if file_id not in data["tracks"]["all"]:
        data["tracks"]["all"].append(file_id)

    # Парсинг текста песни из описания поста
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


# --- Главное меню и выбор треков ---
@bot.message_handler(
    func=lambda msg: msg.text in [
        "🔙 Назад",
        "🎲 Любой трек",
        "📂 Выбрать жанр",
        "🔥 Трек дня",
        "⭐ Моё избранное",
        "🎧 Предложить трек",
    ]
)
def handle_main_menu(message):
    user_states.pop(message.chat.id, None)
    data = load_data()

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
        all_tracks = data["tracks"]["all"]
        if not all_tracks:
            bot.send_message(
                message.chat.id,
                "В базе пока нет треков. Закинь аудиозаписи в канал!",
            )
            return
        chosen = random.choice(all_tracks)
        bot.send_audio(
            message.chat.id,
            chosen,
            reply_markup=get_track_inline_kb(chosen, data),
        )

    elif message.text == "🔥 Трек дня":
        tod = data.get("track_of_day")
        if not tod:
            bot.send_message(
                message.chat.id,
                "Трек дня ещё не назначен админом через /admin!",
            )
            return
        bot.send_audio(
            message.chat.id,
            tod,
            caption="🌟 <b>Главный трек дня!</b>",
            parse_mode="HTML",
            reply_markup=get_track_inline_kb(tod, data),
        )

    elif message.text == "⭐ Моё избранное":
        favs = data.get("favorites", {}).get(str(message.chat.id), [])
        if not favs:
            bot.send_message(
                message.chat.id,
                "Твой список избранного пуст! Жми кнопку «⭐ В избранное» под любым треком.",
            )
            return

        bot.send_message(
            message.chat.id, f"У тебя {len(favs)} сохраненных треков. Кидаю случайный из них:"
        )
        fav_track = random.choice(favs)
        bot.send_audio(
            message.chat.id,
            fav_track,
            reply_markup=get_track_inline_kb(fav_track, data),
        )

    elif message.text == "🎧 Предложить трек":
        user_states[message.chat.id] = "waiting_track"
        bot.send_message(
            message.chat.id,
            "Отправь аудиофайл (mp3), который хочешь предложить в канал:",
        )


# --- Жанры ---
GENRE_MAP = {
    "🌧 Грустное": "грустное",
    "⚡ Веселое": "веселое",
    "📼 Ностальгия": "ностальгия",
    "☕ По душам": "подушам",
    "🔥 ТТ 2026": "тт2026",
}


@bot.message_handler(func=lambda msg: msg.text in GENRE_MAP)
def handle_genres(message):
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
    bot.send_audio(
        message.chat.id, chosen, reply_markup=get_track_inline_kb(chosen, data)
    )


# --- Обработка ввода админа и предложки пользователей ---
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
def handle_inputs(message):
    state = user_states.get(message.chat.id)

    # Установка трека дня
    if state == "waiting_tod" and message.chat.id == ADMIN_ID:
        user_states.pop(message.chat.id, None)
        if message.content_type != "audio":
            bot.send_message(ADMIN_ID, "Нужно было скинуть именно аудиозапись!")
            return

        data = load_data()
        data["track_of_day"] = message.audio.file_id
        if message.audio.file_id not in data["tracks"]["all"]:
            data["tracks"]["all"].append(message.audio.file_id)
        save_data(data)

        bot.send_message(ADMIN_ID, "✅ Новый трек дня успешно сохранен!")
        return

    # Рассылка админа
    if state == "waiting_broadcast" and message.chat.id == ADMIN_ID:
        user_states.pop(message.chat.id, None)
        data = load_data()
        users = data.get("users", [])
        sent = 0

        bot.send_message(ADMIN_ID, f"Начинаю рассылку для {len(users)} пользователей...")
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

        bot.send_message(
            ADMIN_ID, f"Рассылка завершена! Успешно: {sent}/{len(users)}"
        )
        return

    # Предложка от пользователя
    if state == "waiting_track":
        if message.content_type != "audio":
            bot.send_message(message.chat.id, "Пришли, пожалуйста, аудиофайл песней.")
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
            "Спасибо! Трек улетел на рассмотрение админу 🎵",
            reply_markup=get_main_keyboard(),
        )

        admin_kb = types.InlineKeyboardMarkup(row_width=2)
        admin_kb.add(
            types.InlineKeyboardButton(
                "✅ Одобрить и в тгк", callback_data=f"approve_{req_id}"
            ),
            types.InlineKeyboardButton(
                "❌ Отклонить", callback_data=f"reject_{req_id}"
            ),
        )

        user_mention = (
            f"@{message.from_user.username}"
            if message.from_user.username
            else message.from_user.first_name
        )
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


# --- Обработка инлайн-кнопок (Лайки, Избранное, Текст, Админка) ---
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    data = load_data()
    uid = call.from_user.id
    str_uid = str(uid)

    # Лайк
    if call.data.startswith("like_"):
        file_id = call.data.split("like_")[1]
        track_rating = data.setdefault("ratings", {}).setdefault(
            file_id, {"likes": [], "dislikes": []}
        )

        if uid in track_rating["likes"]:
            track_rating["likes"].remove(uid)
        else:
            track_rating["likes"].append(uid)
            if uid in track_rating["dislikes"]:
                track_rating["dislikes"].remove(uid)

        save_data(data)
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_track_inline_kb(file_id, data),
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id)
        return

    # Дизлайк
    elif call.data.startswith("dislike_"):
        file_id = call.data.split("dislike_")[1]
        track_rating = data.setdefault("ratings", {}).setdefault(
            file_id, {"likes": [], "dislikes": []}
        )

        if uid in track_rating["dislikes"]:
            track_rating["dislikes"].remove(uid)
        else:
            track_rating["dislikes"].append(uid)
            if uid in track_rating["likes"]:
                track_rating["likes"].remove(uid)

        save_data(data)
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=get_track_inline_kb(file_id, data),
            )
        except Exception:
            pass
        bot.answer_callback_query(call.id)
        return

    # Добавить / убрать из избранного
    elif call.data.startswith("fav_"):
        file_id = call.data.split("fav_")[1]
        user_favs = data.setdefault("favorites", {}).setdefault(str_uid, [])

        if file_id in user_favs:
            user_favs.remove(file_id)
            bot.answer_callback_query(call.id, "Удалено из избранного ❌")
        else:
            user_favs.append(file_id)
            bot.answer_callback_query(call.id, "Добавлено в избранное! ⭐")

        save_data(data)
        return

    # Показ текста песни
    elif call.data.startswith("lyrics_"):
        file_id = call.data.split("lyrics_")[1]
        lyrics = data.get("lyrics", {}).get(file_id)

        if lyrics:
            bot.send_message(
                call.message.chat.id,
                f"📜 <b>Текст песни:</b>\n\n{lyrics}",
                parse_mode="HTML",
            )
        else:
            bot.send_message(
                call.message.chat.id,
                "К этой песне пока нет текста. Добавь строку «Текст: ...» в описание трека в канале!",
            )
        bot.answer_callback_query(call.id)
        return

    # Админка: Статистика
    elif call.data == "admin_stats" and call.message.chat.id == ADMIN_ID:
        users_count = len(data.get("users", []))
        tracks = data.get("tracks", {})
        all_t = len(tracks.get("all", []))

        text = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👤 Слушателей: <code>{users_count}</code>\n"
            f"🎵 Всего треков: <code>{all_t}</code>\n\n"
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

    # Админка: Задать трек дня
    elif call.data == "admin_set_tod" and call.message.chat.id == ADMIN_ID:
        user_states[ADMIN_ID] = "waiting_tod"
        bot.send_message(ADMIN_ID, "Пришли аудиофайл трека дня:")
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
            f"🔥 Слушай и делись с друзьями!"
        )

        try:
            bot.send_audio(
                CHANNEL_ID,
                track_info["file_id"],
                caption=post_caption,
                parse_mode="HTML",
            )

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
                bot.send_message(
                    track_info["user_id"],
                    "К сожалению, трек не подошел. Попробуй предложить что-то другое!",
                )
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
