import json
import os
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
from telebot import types

TOKEN = "8623102402:AAHDwi8CbD1jZaK1qkWUiWzT81sVfMahQTA"
ADMIN_ID = 1944824871
CHANNEL_ID = -1003918122345

DB_FILE = "bot_data.json"

bot = telebot.TeleBot(TOKEN)

user_states = {}
pending_tracks = {}


# --- Поддержка активности Render ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is online")

def run_web():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()


# --- База данных ---
def load_data():
    default_data = {
        "users": [ADMIN_ID],
        "tracks": {
            "all": [],
            "грустное": [],
            "веселое": [],
            "ностальгия": [],
            "подушам": [],
            "тт2026": [],
        },
        "lyrics": {},
        "ratings": {},
        "favorites": {},
        "track_names": {},  # file_id: "Исполнитель — Название"
        "track_of_day": None,
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("users", [ADMIN_ID])
                data.setdefault("lyrics", {})
                data.setdefault("ratings", {})
                data.setdefault("favorites", {})
                data.setdefault("track_names", {})
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


def get_track_index(file_id, data):
    if file_id not in data["tracks"]["all"]:
        data["tracks"]["all"].append(file_id)
        save_data(data)
    return data["tracks"]["all"].index(file_id)


# --- Клавиатуры ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("🎲 Любой трек"),
        types.KeyboardButton("🔥 Трек дня"),
        types.KeyboardButton("🏆 Топ-5 треков"),
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


def get_track_inline_kb(idx, data):
    file_id = data["tracks"]["all"][idx]
    ratings = data.get("ratings", {}).get(file_id, {"likes": [], "dislikes": []})
    likes_count = len(ratings.get("likes", []))
    dislikes_count = len(ratings.get("dislikes", []))

    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_like = types.InlineKeyboardButton(f"👍 {likes_count}", callback_data=f"lk_{idx}")
    btn_dislike = types.InlineKeyboardButton(f"👎 {dislikes_count}", callback_data=f"dl_{idx}")
    btn_fav = types.InlineKeyboardButton("⭐ В избранное", callback_data=f"fv_{idx}")
    btn_lyrics = types.InlineKeyboardButton("📜 Текст", callback_data=f"ly_{idx}")

    markup.add(btn_like, btn_dislike)
    markup.add(btn_fav, btn_lyrics)
    return markup


def get_admin_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("🌟 Задать трек дня", callback_data="admin_set_tod"),
        types.InlineKeyboardButton("➕ Закинуть треки", callback_data="admin_add_track"),
    )
    return markup


# --- Команды ---
@bot.message_handler(commands=["start"])
def cmd_start(message):
    data = load_data()
    if message.chat.id not in data["users"]:
        data["users"].append(message.chat.id)
        save_data(data)

    user_states.pop(message.chat.id, None)
    bot.send_message(
        message.chat.id,
        "Салам! Врубай треки, чекай чарт Топ-5 и сохраняй любимое в избранное 🎧",
        reply_markup=get_main_keyboard(),
    )


@bot.message_handler(commands=["admin"])
def cmd_admin(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещен.")
        return

    data = load_data()
    tracks_count = len(data["tracks"]["all"])
    text = (
        f"👑 <b>Панель администратора</b>\n\n"
        f"ID админа: <code>{ADMIN_ID}</code>\n"
        f"Треков в базе: <b>{tracks_count}</b> шт."
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=get_admin_keyboard())


# Перехват аудио из канала
@bot.channel_post_handler(content_types=["audio"])
def handle_channel_audio(message):
    file_id = message.audio.file_id
    raw_caption = message.caption or ""
    caption = raw_caption.lower()

    data = load_data()
    if file_id not in data["tracks"]["all"]:
        data["tracks"]["all"].append(file_id)

    title = message.audio.title or "Без названия"
    perf = message.audio.performer or "Неизвестен"
    data["track_names"][file_id] = f"{perf} — {title}"

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


# Главное меню
@bot.message_handler(
    func=lambda msg: msg.text in [
        "🔙 Назад",
        "🎲 Любой трек",
        "📂 Выбрать жанр",
        "🔥 Трек дня",
        "🏆 Топ-5 треков",
        "⭐ Моё избранное",
        "🎧 Предложить трек",
    ]
)
def handle_main_menu(message):
    user_states.pop(message.chat.id, None)
    data = load_data()

    if message.text == "🔙 Назад":
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=get_main_keyboard())

    elif message.text == "📂 Выбрать жанр":
        bot.send_message(message.chat.id, "Выбери жанр:", reply_markup=get_genres_keyboard())

    elif message.text == "🎲 Любой трек":
        all_tracks = data["tracks"]["all"]
        if not all_tracks:
            bot.send_message(message.chat.id, "В базе пока нет музыки! Закинь аудио через /admin или канал.")
            return
        chosen = random.choice(all_tracks)
        idx = get_track_index(chosen, data)
        bot.send_audio(message.chat.id, chosen, reply_markup=get_track_inline_kb(idx, data))

    elif message.text == "🔥 Трек дня":
        tod = data.get("track_of_day")
        if not tod:
            bot.send_message(message.chat.id, "Трек дня ещё не назначен админом через /admin!")
            return
        idx = get_track_index(tod, data)
        bot.send_audio(
            message.chat.id,
            tod,
            caption="🌟 <b>Главный трек дня!</b>",
            parse_mode="HTML",
            reply_markup=get_track_inline_kb(idx, data),
        )

    elif message.text == "🏆 Топ-5 треков":
        all_tracks = data["tracks"]["all"]
        if not all_tracks:
            bot.send_message(message.chat.id, "В базе пока нет треков для рейтинга.")
            return

        def score(fid):
            r = data.get("ratings", {}).get(fid, {"likes": [], "dislikes": []})
            return len(r.get("likes", [])) - len(r.get("dislikes", []))

        sorted_tracks = sorted(all_tracks, key=score, reverse=True)[:5]
        
        text = "🏆 <b>Топ-5 треков по версии слушателей:</b>\n\n"
        kb = types.InlineKeyboardMarkup()
        for i, fid in enumerate(sorted_tracks, 1):
            r = data.get("ratings", {}).get(fid, {"likes": [], "dislikes": []})
            likes = len(r.get("likes", []))
            name = data.get("track_names", {}).get(fid, f"Трек #{i}")
            text += f"{i}. <b>{name}</b> — 👍 {likes}\n"
            t_idx = get_track_index(fid, data)
            kb.add(types.InlineKeyboardButton(f"Слушать #{i}", callback_data=f"play_{t_idx}"))

        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=kb)

    elif message.text == "⭐ Моё избранное":
        favs = data.get("favorites", {}).get(str(message.chat.id), [])
        if not favs:
            bot.send_message(message.chat.id, "Список избранного пуст! Жми «⭐ В избранное» под треком.")
            return
        bot.send_message(message.chat.id, f"У тебя {len(favs)} треков в избранном. Лови случайный:")
        fav_track = random.choice(favs)
        idx = get_track_index(fav_track, data)
        bot.send_audio(message.chat.id, fav_track, reply_markup=get_track_inline_kb(idx, data))

    elif message.text == "🎧 Предложить трек":
        user_states[message.chat.id] = "waiting_track"
        bot.send_message(message.chat.id, "Отправь аудиофайл (mp3), который хочешь предложить в канал:")


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
        bot.send_message(message.chat.id, f"В категории «{message.text}» пока нет треков. Добавь их с тегом #{cat}!")
        return

    chosen = random.choice(tracks)
    idx = get_track_index(chosen, data)
    bot.send_audio(message.chat.id, chosen, reply_markup=get_track_inline_kb(idx, data))


@bot.message_handler(content_types=["text", "audio", "voice", "video", "photo", "document"])
def handle_inputs(message):
    state = user_states.get(message.chat.id)

    if state == "waiting_admin_track" and message.chat.id == ADMIN_ID:
        if message.content_type != "audio":
            bot.send_message(ADMIN_ID, "Отправь аудиофайл mp3.")
            return

        file_id = message.audio.file_id
        raw_caption = message.caption or ""
        caption = raw_caption.lower()

        data = load_data()
        if file_id not in data["tracks"]["all"]:
            data["tracks"]["all"].append(file_id)

        title = message.audio.title or "Без названия"
        perf = message.audio.performer or "Неизвестен"
        data["track_names"][file_id] = f"{perf} — {title}"

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

        if "текст:" in caption:
            data["lyrics"][file_id] = raw_caption.split("текст:", 1)[1].strip()

        save_data(data)
        bot.send_message(
            ADMIN_ID,
            f"✅ Добавлен: {data['track_names'][file_id]}\nКидай ещё или напиши /admin для завершения."
        )
        return

    if state == "waiting_tod" and message.chat.id == ADMIN_ID:
        user_states.pop(message.chat.id, None)
        if message.content_type != "audio":
            bot.send_message(ADMIN_ID, "Нужно было скинуть аудиофайл!")
            return

        data = load_data()
        file_id = message.audio.file_id
        data["track_of_day"] = file_id
        if file_id not in data["tracks"]["all"]:
            data["tracks"]["all"].append(file_id)
        title = message.audio.title or "Без названия"
        perf = message.audio.performer or "Неизвестен"
        data["track_names"][file_id] = f"{perf} — {title}"
        save_data(data)
        bot.send_message(ADMIN_ID, "✅ Новый трек дня сохранен!")
        return

    if state == "waiting_broadcast" and message.chat.id == ADMIN_ID:
        user_states.pop(message.chat.id, None)
        data = load_data()
        users = data.get("users", [])
        sent = 0

        bot.send_message(ADMIN_ID, f"Рассылаю для {len(users)} пользователей...")
        for uid in users:
            try:
                bot.copy_message(chat_id=uid, from_chat_id=ADMIN_ID, message_id=message.message_id)
                sent += 1
            except Exception:
                pass
        bot.send_message(ADMIN_ID, f"Рассылка завершена! Доставлено: {sent}/{len(users)}")
        return

    if state == "waiting_track":
        if message.content_type != "audio":
            bot.send_message(message.chat.id, "Пришли аудиофайл трека.")
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

        bot.send_message(message.chat.id, "Спасибо! Трек отправлен админу 🎵", reply_markup=get_main_keyboard())

        admin_kb = types.InlineKeyboardMarkup(row_width=2)
        admin_kb.add(
            types.InlineKeyboardButton("✅ Одобрить и в тгк", callback_data=f"ap_{req_id}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"rj_{req_id}"),
        )

        user_mention = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        caption = f"📥 Предложка от {user_mention}\n{pending_tracks[req_id]['performer']} — {pending_tracks[req_id]['title']}"

        bot.send_audio(ADMIN_ID, message.audio.file_id, caption=caption, reply_markup=admin_kb)
        return


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    data = load_data()
    uid = call.from_user.id
    str_uid = str(uid)

    if call.data.startswith("play_"):
        idx = int(call.data.split("_")[1])
        fid = data["tracks"]["all"][idx]
        bot.send_audio(call.message.chat.id, fid, reply_markup=get_track_inline_kb(idx, data))
        bot.answer_callback_query(call.id)
        return

    elif call.data.startswith("lk_"):
        idx = int(call.data.split("_")[1])
        file_id = data["tracks"]["all"][idx]
        track_rating = data.setdefault("ratings", {}).setdefault(file_id, {"likes": [], "dislikes": []})

        if uid in track_rating["likes"]:
            track_rating["likes"].remove(uid)
        else:
            track_rating["likes"].append(uid)
            if uid in track_rating["dislikes"]:
                track_rating["dislikes"].remove(uid)

        save_data(data)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_track_inline_kb(idx, data))
        except Exception:
            pass
        bot.answer_callback_query(call.id)
        return

    elif call.data.startswith("dl_"):
        idx = int(call.data.split("_")[1])
        file_id = data["tracks"]["all"][idx]
        track_rating = data.setdefault("ratings", {}).setdefault(file_id, {"likes": [], "dislikes": []})

        if uid in track_rating["dislikes"]:
            track_rating["dislikes"].remove(uid)
        else:
            track_rating["dislikes"].append(uid)
            if uid in track_rating["likes"]:
                track_rating["likes"].remove(uid)

        save_data(data)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_track_inline_kb(idx, data))
        except Exception:
            pass
        bot.answer_callback_query(call.id)
        return

    elif call.data.startswith("fv_"):
        idx = int(call.data.split("_")[1])
        file_id = data["tracks"]["all"][idx]
        user_favs = data.setdefault("favorites", {}).setdefault(str_uid, [])

        if file_id in user_favs:
            user_favs.remove(file_id)
            bot.answer_callback_query(call.id, "Удалено из избранного ❌")
        else:
            user_favs.append(file_id)
            bot.answer_callback_query(call.id, "Добавлено в избранное! ⭐")

        save_data(data)
        return

    elif call.data.startswith("ly_"):
        idx = int(call.data.split("_")[1])
        file_id = data["tracks"]["all"][idx]
        lyrics = data.get("lyrics", {}).get(file_id)

        if lyrics:
            bot.send_message(call.message.chat.id, f"📜 <b>Текст песни:</b>\n\n{lyrics}", parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id, "К этой песне нет текста!")
        bot.answer_callback_query(call.id)
        return

    elif call.data == "admin_stats" and call.message.chat.id == ADMIN_ID:
        users_count = len(data.get("users", []))
        tracks = data.get("tracks", {})
        text = (
            f"📊 <b>Статистика</b>\n\n"
            f"👤 Слушателей: <code>{users_count}</code>\n"
            f"🎵 Всего треков: <code>{len(tracks.get('all', []))}</code>\n\n"
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
        bot.send_message(ADMIN_ID, "Пришли сообщение для рассылки:")
        bot.answer_callback_query(call.id)

    elif call.data == "admin_set_tod" and call.message.chat.id == ADMIN_ID:
        user_states[ADMIN_ID] = "waiting_tod"
        bot.send_message(ADMIN_ID, "Пришли аудиофайл трека дня:")
        bot.answer_callback_query(call.id)

    elif call.data == "admin_add_track" and call.message.chat.id == ADMIN_ID:
        user_states[ADMIN_ID] = "waiting_admin_track"
        bot.send_message(
            ADMIN_ID,
            "Кидай сюда любые треки mp3 (можно с хэштегами, например <code>#веселое</code>). Они сохранятся навсегда!",
            parse_mode="HTML"
        )
        bot.answer_callback_query(call.id)

    elif call.data.startswith("ap_"):
        req_id = call.data.split("_")[1]
        track_info = pending_tracks.get(req_id)
        if not track_info:
            bot.answer_callback_query(call.id, "Устарело")
            return

        post_caption = f"🎧 Новый трек из предложки!\n👤 Предложил: {track_info['username']}"
        try:
            bot.send_audio(CHANNEL_ID, track_info["file_id"], caption=post_caption)
            if track_info["file_id"] not in data["tracks"]["all"]:
                data["tracks"]["all"].append(track_info["file_id"])
                data["track_names"][track_info["file_id"]] = f"{track_info['performer']} — {track_info['title']}"
                save_data(data)
            bot.send_message(track_info["user_id"], "🔥 Твой трек выложен в канал!")
            bot.edit_message_caption(caption=call.message.caption + "\n\n✅ Опубликовано", chat_id=call.message.chat.id, message_id=call.message.message_id)
            bot.answer_callback_query(call.id, "Опубликовано!")
            pending_tracks.pop(req_id, None)
        except Exception as e:
            bot.send_message(ADMIN_ID, f"Ошибка отправки: {e}")
            bot.answer_callback_query(call.id, "Ошибка")

    elif call.data.startswith("rj_"):
        req_id = call.data.split("_")[1]
        track_info = pending_tracks.get(req_id)
        if track_info:
            try:
                bot.send_message(track_info["user_id"], "К сожалению, трек не подошел.")
            except Exception:
                pass
            pending_tracks.pop(req_id, None)
        bot.edit_message_caption(caption=(call.message.caption or "") + "\n\n❌ Отклонено", chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.answer_callback_query(call.id, "Отклонено")


print("Бот успешно запущен!")
bot.infinity_polling()
