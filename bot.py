import os
import asyncio
import tempfile
import logging
import aiohttp
from telethon import TelegramClient, events
from telethon.tl.types import KeyboardButtonCallback
from googlesearch import search

# ------------------- KONFIGURATSIYA -------------------
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- BOT KLIENTI -------------------
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Foydalanuvchilarning qidiruv natijalarini vaqtinchalik saqlash
# Kalit: user_id, qiymat: natijalar ro‘yxati (har biri dict: title, link)
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
                    async for chunk in resp.content.iter_chunked(1024 * 1024):  # 1 MB chunk
                        tmp.write(chunk)
                return temp_path, None
    except Exception as e:
        return None, str(e)

# ------------------- QIDIRUV FUNKSIYASI -------------------
def google_search(query, num_results=5):
    """Google’da qidirib, natijalarni ro‘yxat qilib qaytaradi."""
    try:
        # Generator, listga aylantiramiz
        results = list(search(query, num_results=num_results))
        # search() qaytargan natijalar URL lar ro‘yxati, sarlavhasiz.
        # Sarlavha olish uchun qo‘shimcha so‘rov kerak, lekin bu murakkab.
        # Shu sababli URL larni ishlatamiz, foydalanuvchiga URL ko‘rsatamiz.
        # Agar sarlavha kerak bo‘lsa, aiohttp bilan har bir URL dan sarlavha olish mumkin, lekin bu sekin.
        # Alternativ: Google Custom Search API ishlatish (tavsiya).
        # Hozircha faqat URL lar bilan cheklanamiz.
        return [{"title": url, "link": url} for url in results[:num_results]]
    except Exception as e:
        logger.error(f"Qidiruv xatosi: {e}")
        return []

# ------------------- BOT XABARLARI -------------------
@client.on(events.NewMessage(pattern=r'^/start$'))
async def start(event):
    await event.reply("Assalomu alaykum! Menga qidiruv so‘rovingizni yuboring (masalan: 'python darslari'). Men Google’dan topib, faylni yuklab beraman.")

@client.on(events.NewMessage)
async def search_handler(event):
    # Agar buyruq bo‘lsa yoki fayl bo‘lsa, qidirmaymiz
    if event.message.text.startswith('/') or event.message.file:
        return

    query = event.message.text.strip()
    if not query:
        return

    await event.reply(f"🔍 Qidirilmoqda: {query}")

    # Qidiruv
    results = google_search(query)
    if not results:
        await event.reply("Hech narsa topilmadi.")
        return

    # Natijalarni foydalanuvchi ID si bo‘yicha saqlaymiz
    user_id = event.sender_id
    user_search_results[user_id] = results

    # Tugmalar yaratish (har bir natija uchun)
    buttons = []
    for i, res in enumerate(results):
        # Tugma matni – URL ning birinchi 30 ta belgisi
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

        # Faylni yuklab olish
        file_path, error = await download_file(url)
        if error:
            await event.respond(f"❌ Yuklab bo‘lmadi: {error}")
            return

        # Telegram’ga yuborish
        await event.respond("📤 Telegram’ga yuborilmoqda...")
        try:
            await client.send_file(event.chat_id, file_path, caption=url)
        except Exception as e:
            await event.respond(f"❌ Yuborishda xato: {e}")
        finally:
            # Faylni o‘chirish
            if file_path and os.path.exists(file_path):
                os.unlink(file_path)

        await event.respond("✅ Tayyor!")

        # Foydalanuvchi natijalarini tozalash (ixtiyoriy)
        if user_id in user_search_results:
            del user_search_results[user_id]

# ------------------- ASOSIY -------------------
async def main():
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
