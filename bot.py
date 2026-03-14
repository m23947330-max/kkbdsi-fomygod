import os
import asyncio
import tempfile
import aiohttp
from telethon import TelegramClient, events
from telethon.tl.types import DocumentAttributeVideo
import logging

# ------------------- KONFIGURATSIYA -------------------
API_ID = int(os.environ.get("API_ID"))          # my.telegram.org dan olingan
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")          # Bot token (ixtiyoriy, userbot ham bo‘lishi mumkin)

# Agar bot token bilan ishlasangiz, session fayl nomi boshqacha bo‘ladi
SESSION_NAME = "video_bot"  # Telethon session fayli (userbot uchun)
BOT_SESSION = "bot_session" # Bot token bilan ishlaganda

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- MTProto KLIENTI -------------------
# Agar bot token bilan ishlamoqchi bo‘lsangiz:
# client = TelegramClient(BOT_SESSION, API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Agar userbot (shaxsiy hisob) bilan ishlamoqchi bo‘lsangiz (tavsiya etiladi):
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# ------------------- YUKLAB OLISH FUNKSIYASI -------------------
async def download_file(url):
    """URL dan faylni vaqtinchalik nom bilan yuklab oladi, to‘liq yo‘lni qaytaradi."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as resp:
                if resp.status != 200:
                    return None, f"HTTP xatosi: {resp.status}"

                # Fayl nomini URL dan olish yoki random yaratish
                content_disposition = resp.headers.get('content-disposition')
                if content_disposition and 'filename=' in content_disposition:
                    filename = content_disposition.split('filename=')[-1].strip('"')
                else:
                    filename = url.split('/')[-1].split('?')[0] or "video.mp4"

                # Vaqtinchalik fayl yaratish
                fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(filename)[1])
                with os.fdopen(fd, 'wb') as tmp_file:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):  # 1 MB chunk
                        tmp_file.write(chunk)
                return temp_path, None
    except Exception as e:
        return None, str(e)

# ------------------- TELEGRAM YUBORISH -------------------
async def send_video(chat_id, file_path, caption=""):
    """Videonu Telegram'ga yuboradi (MTProto orqali)."""
    try:
        # Faylni yuborish (avtomatik ravishda bo‘laklab yuboradi)
        await client.send_file(
            chat_id,
            file_path,
            caption=caption,
            attributes=[
                DocumentAttributeVideo(
                    duration=0,  # aniqlanmagan bo‘lsa, fayldan o‘qiydi
                    w=0,
                    h=0,
                    supports_streaming=True
                )
            ],
            force_document=False  # videoni video sifatida yuborish
        )
        logger.info(f"Video yuborildi: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Yuborishda xato: {e}")
        return False

# ------------------- BOT XABARLARINI QAYTA ISHLASH -------------------
@client.on(events.NewMessage(pattern=r'^/start$'))
async def start_handler(event):
    await event.reply("Assalomu alaykum! Menga to‘g‘ridan-to‘g‘ri video fayl yoki video URL yuboring, men uni qayta yuboraman.")

@client.on(events.NewMessage)
async def message_handler(event):
    # Agar foydalanuvchi fayl yuborsa
    if event.message.file:
        # Faylni qabul qilish
        file_path = await event.message.download_media(file=tempfile.gettempdir())
        await event.reply("📥 Fayl qabul qilindi, qayta yuborilmoqda...")
        success = await send_video(event.chat_id, file_path)
        os.unlink(file_path)  # O‘chirish
        if success:
            await event.reply("✅ Video yuborildi.")
        else:
            await event.reply("❌ Yuborishda xatolik.")
        return

    # Agar foydalanuvchi matn yuborsa (URL deb qaraymiz)
    url = event.message.text.strip()
    if url.startswith(('http://', 'https://')):
        await event.reply(f"⏳ Yuklab olinmoqda: {url}")
        file_path, error = await download_file(url)
        if error:
            await event.reply(f"❌ Yuklab bo‘lmadi: {error}")
            return
        await event.reply("📤 Yuklandi, Telegram'ga yuborilmoqda...")
        success = await send_video(event.chat_id, file_path, caption=f"🎬 {url}")
        os.unlink(file_path)  # O‘chirish
        if success:
            await event.reply("✅ Video yuborildi.")
        else:
            await event.reply("❌ Yuborishda xatolik.")
    else:
        await event.reply("Iltimos, to‘g‘ri URL yoki video fayl yuboring.")

# ------------------- ASOSIY -------------------
async def main():
    await client.start()
    logger.info("Bot ishga tushdi. @username yoki bot token bilan ishlayapti.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
