import os
import asyncio
import tempfile
import logging
import aiohttp
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonCallback
from googlesearch import search
from aiohttp import web

# ------------------- KONFIGURATSIYA -------------------
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))  # Render beradigan port

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- BOT KLIENTI (Telethon) -------------------
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Foydalanuvchilarning qidiruv natijalarini vaqtinchalik saqlash
user_search_results = {}

# ------------------- YUKLAB OLISH FUNKSIYASI -------------------
async def download_file(url):
    """URL dan faylni yuklab oladi, vaqtinchalik fayl yo‘lini qaytaradi."""
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

# ------------------- QIDIRUV FUNKSIYASI -------------------
def google_search(query, num_results=5):
    """Google’da qidirib, URL ro‘yxatini qaytaradi."""
    try:
        results = list(search(query, num_results=num_results))
        # Faqat URL lar ro‘yxati, sarlavhasiz. Tugmada URL ko‘rinadi.
        return [{"title": url, "link": url} for url in results[:num_results]]
    except Exception as e:
        logger.error(f"Qidiruv xatosi: {e}")
        return []

# ------------------- BOT XABARLARI -------------------
@client.on(events.NewMessage(pattern=r'^/start$'))
async def start(event):
    await event.reply(
        "Assalomu alaykum! Menga qidiruv so‘rovingizni yuboring.\n"
        "Masalan: 'python darslari'\n"
        "Men Google’dan topib, faylni yuklab beraman."
    )

@client.on(events.NewMessage)
async def search_handler(event):
    if event.message.text.startswith('/') or event.message.file:
        return

    query = event.message.text.strip()
    if not query:
        return

    await event.reply(f"🔍 Qidirilmoqda: {query}")

    results = google_search(query)
    if not results:
        await event.reply("Hech narsa topilmadi.")
        return

    user_id = event.sender_id
    user_search_results[user_id] = results

    buttons = []
    for i, res in enumerate(results):
        btn_text = f"{i+1}. {res['title'][:40]}"
        buttons.append([KeyboardButtonCallback(btn_text, data=f"select_{i}")])

    await event.reply("📋 Natijalar (birini tanlang):", buttons=buttons)

@client.on(events.CallbackQuery)
async def callback_handler(event):
    user_id = event.sender_id
    data = event.data.decode()

    if data.startswith("select_"):
        index = int(data.split("_")[1])
        results = user_search_results.get(user_id)
        if not results or index >= len(results):
            await event.answer("❌ Natija topilmadi. Qaytadan qidirib ko‘ring.")
            return

        selected = results[index]
        url = selected['link']

        await event.edit(f"⏳ Yuklanmoqda: {url}")

        file_path, error = await download_file(url)
        if error:
            await event.respond(f"❌ Yuklab bo‘lmadi: {error}")
            return

        await event.respond("📤 Telegram’ga yuborilmoqda...")
        try:
            await client.send_file(event.chat_id, file_path, caption=url)
        except Exception as e:
            await event.respond(f"❌ Yuborishda xato: {e}")
        finally:
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)

        await event.respond("✅ Tayyor!")

        if user_id in user_search_results:
            del user_search_results[user_id]

# ------------------- HEALTH CHECK SERVER (Render uchun) -------------------
async def health_check(request):
    return web.Response(text="Bot ishlayapti", status=200)

async def start_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Health check server running on port {PORT}")

# ------------------- ASOSIY -------------------
async def main():
    # Health check serverni parallel ishga tushirish
    await start_server()

    # Botni ishga tushirish va to‘xtaguncha kutish
    async with client:
        await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to‘xtatildi.")
