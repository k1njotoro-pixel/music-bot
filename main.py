import json
import os
import random
import telebot
from telebot import types

TOKEN = "8623102402:AAHDwi8CbD1jZaK1qkWUiWzT81sVfMahQTA"
CHANNEL_ID = None

DB_FILE = "songs.json"

bot = telebot.TeleBot(TOKEN)


def load_tracks():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_tracks(tracks):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)


markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
markup.add(types.KeyboardButton("🎲 Рандомная песня"))


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "Салам! Жми кнопку ниже, чтобы получить трек 🎧",
        reply_markup=markup,
    )


@bot.channel_post_handler(content_types=["audio"])
def handle_channel_audio(message):
    print(f"Пост из канала! ID канала: {message.chat.id}")
    if CHANNEL_ID and message.chat.id != CHANNEL_ID:
        return

    file_id = message.audio.file_id
    tracks = load_tracks()

    if file_id not in tracks:
        tracks.append(file_id)
        save_tracks(tracks)
        print(f"Сохранен трек: {message.audio.title or 'Без названия'}")


@bot.message_handler(func=lambda msg: msg.text == "🎲 Рандомная песня")
def send_song(message):
    tracks = load_tracks()
    if not tracks:
        bot.send_message(
            message.chat.id, "В базе пока пусто! Закинь аудио в канал."
        )
        return

    random_id = random.choice(tracks)
    bot.send_audio(message.chat.id, random_id)


print("Бот успешно запущен на сервере!")
bot.infinity_polling()
