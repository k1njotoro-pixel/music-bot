import os
import json
import random
import logging
from datetime import date
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.INFO)

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "8623102402:AAHDwi8CbD1jZaK1qkWUiWzT81sVfMahQTA"
CHANNEL_ID = -1003918122345
ADMIN_ID = 1944824871
DATA_FILE = "music_bot_data.json"
# =============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)


def load_data():
    default_data = {
        "tracks": list(range(2, 71)),  # Посты с треками вплоть до 70
        "favorites": {},               # {user_id: [msg_id, ...]}
        "likes": {},                   # {msg_id: [user_id, ...]}
        "dislikes": {},                # {msg_id: [user_id, ...]}
        "track_of_the_day": {"date": "", "msg_id": None}
    }
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_data.items():
                    data.setdefault(k, v)
                return data
        except Exception:
            return default_data
    return default_data


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


db = load_data()


def get_main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🎲 Любой трек"))
    kb.row(KeyboardButton("🔥 Трек дня"), KeyboardButton("⭐ Моё избранное"))
    return kb


def get_track_inline_keyboard(msg_id: int):
    msg_id_str = str(msg_id)
    likes_count = len(db["likes"].get(msg_id_str, []))
    dislikes_count = len(db["dislikes"].get(msg_id_str, []))

    ikb = InlineKeyboardMarkup(row_width=2)
    ikb.row(
        InlineKeyboardButton(f"👍 {likes_count}", callback_data=f"like_{msg_id}"),
        InlineKeyboardButton(f"👎 {dislikes_count}", callback_data=f"dislike_{msg_id}")
    )
    ikb.row(
        InlineKeyboardButton("⭐ В избранное", callback_data=f"fav_{msg_id}"),
        InlineKeyboardButton("📜 Текст", callback_data=f"lyrics_{msg_id}")
    )
    return ikb


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer(
        f"ID админа: {ADMIN_ID}\n"
        f"Треков в базе: {len(db['tracks'])} шт.\n\n"
        "Выбирай пункт в меню ниже 👇",
        reply_markup=get_main_keyboard()
    )


@dp.message_handler(lambda msg: "Любой трек" in msg.text)
async def send_random_track(message: types.Message):
    if not db["tracks"]:
        await message.answer("В базе пока нет треков!")
        return

    # До 5 попыток отправить трек из канала
    for _ in range(5):
        rand_id = random.choice(db["tracks"])
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=CHANNEL_ID,
                message_id=rand_id,
                reply_markup=get_track_inline_keyboard(rand_id)
            )
            return
        except Exception:
            continue

    await message.answer("Не удалось быстро загрузить трек, нажми еще раз!")


@dp.message_handler(lambda msg: "Трек дня" in msg.text)
async def send_track_of_the_day(message: types.Message):
    if not db["tracks"]:
        await message.answer("В базе пока нет треков!")
        return

    today_str = str(date.today())
    totd = db.get("track_of_the_day", {})

    if totd.get("date") != today_str or not totd.get("msg_id"):
        totd["date"] = today_str
        totd["msg_id"] = random.choice(db["tracks"])
        db["track_of_the_day"] = totd
        save_data()

    track_id = totd["msg_id"]
    try:
        await message.answer("🔥 <b>Трек дня сегодня:</b>", parse_mode="HTML")
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=track_id,
            reply_markup=get_track_inline_keyboard(track_id)
        )
    except Exception:
        totd["msg_id"] = random.choice(db["tracks"])
        save_data()
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=totd["msg_id"],
            reply_markup=get_track_inline_keyboard(totd["msg_id"])
        )


@dp.message_handler(lambda msg: "Моё избранное" in msg.text)
async def send_favorites(message: types.Message):
    user_id_str = str(message.from_user.id)
    fav_tracks = db["favorites"].get(user_id_str, [])

    if not fav_tracks:
        await message.answer("У тебя пока нет сохраненных треков. Нажимай «⭐ В избранное» под треками!")
        return

    await message.answer(f"⭐ Твои сохраненные треки ({len(fav_tracks)} шт.):")
    for track_id in fav_tracks[-5:]:
        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=CHANNEL_ID,
                message_id=track_id,
                reply_markup=get_track_inline_keyboard(track_id)
            )
        except Exception:
            continue


@dp.message_handler(content_types=[types.ContentType.AUDIO, types.ContentType.DOCUMENT])
async def handle_track_upload(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    audio_file_id = message.audio.file_id if message.audio else message.document.file_id

    try:
        sent_msg = await bot.send_audio(
            chat_id=CHANNEL_ID,
            audio=audio_file_id,
            caption=message.caption or ""
        )
        if sent_msg.message_id not in db["tracks"]:
            db["tracks"].append(sent_msg.message_id)
            save_data()

        await message.answer(f"✅ Трек добавлен в канал и базу! Всего треков: {len(db['tracks'])}")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки в канал: {e}")


@dp.callback_query_handler(lambda c: c.data)
async def process_track_actions(call: types.CallbackQuery):
    try:
        action, msg_id = call.data.split("_")
        track_id = int(msg_id)
    except Exception:
        await call.answer()
        return

    user_id = call.from_user.id
    user_id_str = str(user_id)
    track_id_str = str(track_id)

    db["likes"].setdefault(track_id_str, [])
    db["dislikes"].setdefault(track_id_str, [])
    db["favorites"].setdefault(user_id_str, [])

    if action == "like":
        if user_id in db["likes"][track_id_str]:
            db["likes"][track_id_str].remove(user_id)
            await call.answer("Лайк убран")
        else:
            db["likes"][track_id_str].append(user_id)
            if user_id in db["dislikes"][track_id_str]:
                db["dislikes"][track_id_str].remove(user_id)
            await call.answer("Тебе понравился трек! 👍")
        save_data()
        await call.message.edit_reply_markup(reply_markup=get_track_inline_keyboard(track_id))

    elif action == "dislike":
        if user_id in db["dislikes"][track_id_str]:
            db["dislikes"][track_id_str].remove(user_id)
            await call.answer("Дизлайк убран")
        else:
            db["dislikes"][track_id_str].append(user_id)
            if user_id in db["likes"][track_id_str]:
                db["likes"][track_id_str].remove(user_id)
            await call.answer("Не понравилось 👎")
        save_data()
        await call.message.edit_reply_markup(reply_markup=get_track_inline_keyboard(track_id))

    elif action == "fav":
        if track_id in db["favorites"][user_id_str]:
            db["favorites"][user_id_str].remove(track_id)
            await call.answer("Удалено из избранного ❌")
        else:
            db["favorites"][user_id_str].append(track_id)
            await call.answer("Добавлено в избранное! ⭐")
        save_data()

    elif action == "lyrics":
        await call.answer("Текст песни пока не добавлен для этого трека 📜", show_alert=True)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)+ "\n\n✅ Опубликовано", chat_id=call.message.chat.id, message_id=call.message.message_id)
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
