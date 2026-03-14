import os
import asyncio
import tempfile
import aiohttp
from telethon import TelegramClient, events
import logging

# ------------------- KONFIGURATSIYA -------------------
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- MTProto KLIENTI (BOT TOKEN BILAN) -------------------
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ------------------- YUKLAB OLISH FUNKSIYASI -------------------
async def download_file(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=60) as resp:
                if resp.status != 200:
                    return None, f"HTTP xatosi: {resp.status}"

                # Fayl nomini aniqlash
                content_disp = resp.headers.get('content-disposition')
                if content_disp and 'filename=' in content_disp:
                    filename = content_disp.split('filename=')[-1].strip('"')
                else:
                    filename = url.split('/')[-1].split('?')[0] or "file.bin"

                fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(filename)[1])
                with os.fdopen(fd, 'wb') as tmp:
                    async for chunk in resp.content.iter_chunked(1024 * 1024):
                        tmp.write(chunk)
                return temp_path, None
    except Exception as e:
        return None, str(e)

# ------------------- BOT XABARLARI -------------------
@client.on(events.NewMessage(pattern=r'^/start$'))
async def start(event):
    await event.reply("Assalomu alaykum! Video URL yoki fayl yuboring, men uni Telegram’ga yuklab beraman.")

@client.on(events.NewMessage)
async def handler(event):
    # Agar foydalanuvchi fayl yuborsa
    if event.message.file:
        file_path = await event.message.download_media(file=tempfile.gettempdir())
        await event.reply("📥 Qabul qilindi, qayta yuborilmoqda...")
        await client.send_file(event.chat_id, file_path)
        os.unlink(file_path)
        await event.reply("✅ Yuklandi.")
        return

    # Agar foydalanuvchi URL yuborsa
    url = event.message.text.strip()
    if url.startswith(('http://', 'https://')):
        await event.reply("⏳ Yuklab olinmoqda...")
        file_path, err = await download_file(url)
        if err:
            await event.reply(f"❌ Xato: {err}")
            return
        await event.reply("📤 Telegram’ga yuborilmoqda...")
        await client.send_file(event.chat_id, file_path, caption=f"🎬 {url}")
        os.unlink(file_path)
        await event.reply("✅ Tayyor!")
    else:
        await event.reply("Iltimos, video URL yoki fayl yuboring.")

# ------------------- ASOSIY -------------------
async def main():
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
