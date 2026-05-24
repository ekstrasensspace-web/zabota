"""
Экспорт чатов из папки "МАС учебные" в Telegram
Сохраняет каждый чат как .md файл в curator/knowledge/chats/
"""

import asyncio
import re
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogFiltersRequest

API_ID = 30546837
API_HASH = "763045c22fe289db86c7b6c291ec0f44"
FOLDER_NAME = "МАС учебные"
OUTPUT_DIR = Path(__file__).parent / "curator" / "knowledge" / "chats"
# Максимум сообщений на чат (0 = все)
MAX_MESSAGES = 3000


def clean_text(text: str) -> str:
    if not text:
        return ""
    # Убираем лишние пробелы и переносы
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with TelegramClient("vseveda_export", API_ID, API_HASH) as client:
        print("✅ Подключено к Telegram")

        # Получаем все папки
        filters = await client(GetDialogFiltersRequest())
        target_folder = None
        for f in filters.filters:
            raw_title = getattr(f, "title", None)
            title = str(raw_title) if raw_title is not None else ""
            if title and FOLDER_NAME.lower() in title.lower():
                target_folder = f
                print(f"✅ Найдена папка: {title}")
                break

        if not target_folder:
            print(f"❌ Папка '{FOLDER_NAME}' не найдена")
            print("Доступные папки:")
            for f in filters.filters:
                raw_title = getattr(f, "title", "—")
                title = str(raw_title) if raw_title is not None else "—"
                print(f"  - {title}")
            return

        # Получаем чаты из папки
        included_peers = getattr(target_folder, "include_peers", [])
        print(f"📁 Чатов в папке: {len(included_peers)}")

        for peer in included_peers:
            try:
                entity = await client.get_entity(peer)
                chat_title = getattr(entity, "title", None) or getattr(entity, "username", str(peer))
                safe_name = re.sub(r"[^\w\s-]", "", chat_title).strip().replace(" ", "_")[:60]
                out_file = OUTPUT_DIR / f"{safe_name}.md"

                print(f"\n📥 Скачиваю: {chat_title} ...", end="", flush=True)

                messages = []
                async for msg in client.iter_messages(entity, limit=MAX_MESSAGES or None):
                    if not msg.text:
                        continue
                    sender = ""
                    if msg.sender:
                        first = getattr(msg.sender, "first_name", "") or ""
                        last = getattr(msg.sender, "last_name", "") or ""
                        sender = (first + " " + last).strip() or getattr(msg.sender, "username", "")
                    text = clean_text(msg.text)
                    if text and len(text) > 10:
                        messages.append(f"**{sender}:** {text}" if sender else text)

                messages.reverse()  # Хронологический порядок

                if messages:
                    content = f"# {chat_title}\n\n" + "\n\n".join(messages)
                    out_file.write_text(content, encoding="utf-8")
                    print(f" {len(messages)} сообщений → {out_file.name}")
                else:
                    print(f" пусто, пропускаю")

            except Exception as e:
                print(f" ❌ Ошибка: {e}")

        print(f"\n🎉 Готово! Файлы сохранены в {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
