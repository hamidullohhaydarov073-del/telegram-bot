import json
import os
import re
import logging
from difflib import SequenceMatcher
from telegram import Update, ChatMember
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# ===================== SOZLAMALAR =====================
BOT_TOKEN = "8607138752:AAHNZEiP6ZEMdvobtZ4tnkpAKmAaxtkXlpk"  # Bu yerga tokeningizni yozing

# Reklama filtri sozlamalari
FILTER_ENABLED = True          # True = yoqiq, False = o'chiq
WARN_BEFORE_BAN = True         # True = avval ogohlantirish, False = to'g'ri ban
WARN_LIMIT = 3                 # Necha ogohlantirishdan keyin ban

# Savol-javob sozlamalari
MIN_SIMILARITY = 0.55          # O'xshashlik darajasi (0.0 - 1.0)

# ======================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ma'lumotlar fayllari
QA_FILE = "javoblar.json"
WARNS_FILE = "ogohlantirishlar.json"

# Reklama kalit so'zlari
SPAM_KEYWORDS = [
    "reklama", "aksiya", "chegirma", "kanalga qo'shiling",
    "kanalga o'ting", "kanalga kiring", "follow", "subscribe",
    "👆👆", "📢", "📣", "🔔", "💰💰", "💵💵",
    "daromad", "pul ishlang", "biznes taklif",
    "100%", "kafolat", "foiz", "kredit",
    "casino", "stavka", "bet", "букмекер",
    "t.me/", "telegram.me/", "bit.ly", "tinyurl",
]


# =================== YORDAMCHI FUNKSIYALAR ===================

def load_json(filename: str, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filename: str, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_qa() -> list:
    return load_json(QA_FILE, [])


def save_qa(qa_list: list):
    save_json(QA_FILE, qa_list)


def get_warns() -> dict:
    return load_json(WARNS_FILE, {})


def save_warns(warns: dict):
    save_json(WARNS_FILE, warns)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def find_answer(question: str) -> str | None:
    qa_list = get_qa()
    best_match = None
    best_score = 0.0
    for item in qa_list:
        score = similarity(question, item["savol"])
        if score > best_score:
            best_score = score
            best_match = item["javob"]
    if best_score >= MIN_SIMILARITY:
        return best_match
    return None


async def is_admin(update: Update, user_id: int) -> bool:
    try:
        member = await update.effective_chat.get_member(user_id)
        return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception:
        return False


def is_spam(text: str) -> bool:
    text_lower = text.lower()
    # Kalit so'zlarni tekshirish
    for keyword in SPAM_KEYWORDS:
        if keyword.lower() in text_lower:
            return True
    # Havola borligini tekshirish
    url_pattern = r'(https?://|www\.)\S+'
    if re.search(url_pattern, text_lower):
        return True
    return False


# =================== KOMANDALAR ===================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men guruh yordamchisiman 🤖\n"
        "Savol bersangiz, javob beraman!\n\n"
        "Admin uchun: /yordam"
    )


async def yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_admin(update, user_id):
        return
    text = (
        "📋 *Admin komandalari:*\n\n"
        "*Savol-javob:*\n"
        "/qoshish savol | javob — yangi javob qo'shish\n"
        "/royxat — barcha javoblarni ko'rish\n"
        "/ochir [raqam] — javobni o'chirish\n\n"
        "*Reklama filtri:*\n"
        "/filter — filtr holati\n"
        "/filter on — filterni yoqish\n"
        "/filter off — filterni o'chirish\n"
        "/ogohlantirishlar — ogohlantirish ro'yxati\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def qoshish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_admin(update, user_id):
        await update.message.reply_text("Bu komanda faqat adminlar uchun!")
        return

    args = update.message.text.split(None, 1)
    if len(args) < 2 or "|" not in args[1]:
        await update.message.reply_text(
            "Format: /qoshish savol | javob\n"
            "Misol: /qoshish narx necha | Narx 50,000 so'm"
        )
        return

    parts = args[1].split("|", 1)
    savol = parts[0].strip()
    javob = parts[1].strip()

    qa_list = get_qa()
    qa_list.append({"savol": savol, "javob": javob})
    save_qa(qa_list)

    await update.message.reply_text(f"✅ Qo'shildi!\nSavol: {savol}\nJavob: {javob}")


async def royxat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_admin(update, user_id):
        return

    qa_list = get_qa()
    if not qa_list:
        await update.message.reply_text("Hech qanday javob yo'q. /qoshish bilan qo'shing.")
        return

    text = "📋 *Javoblar ro'yxati:*\n\n"
    for i, item in enumerate(qa_list, 1):
        text += f"{i}. *{item['savol']}*\n   → {item['javob']}\n\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def ochir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_admin(update, user_id):
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Format: /ochir [raqam]\nMisol: /ochir 3")
        return

    index = int(args[0]) - 1
    qa_list = get_qa()

    if index < 0 or index >= len(qa_list):
        await update.message.reply_text(f"Xato! {len(qa_list)} ta javob bor.")
        return

    removed = qa_list.pop(index)
    save_qa(qa_list)
    await update.message.reply_text(f"✅ O'chirildi: {removed['savol']}")


async def filter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FILTER_ENABLED
    user_id = update.effective_user.id
    if not await is_admin(update, user_id):
        return

    args = context.args
    if not args:
        status = "✅ Yoqiq" if FILTER_ENABLED else "❌ O'chiq"
        await update.message.reply_text(
            f"🛡 Reklama filtri: {status}\n"
            f"Ogohlantirish limiti: {WARN_LIMIT}\n\n"
            "Yoqish: /filter on\nO'chirish: /filter off"
        )
        return

    if args[0] == "on":
        FILTER_ENABLED = True
        await update.message.reply_text("✅ Reklama filtri yoqildi!")
    elif args[0] == "off":
        FILTER_ENABLED = False
        await update.message.reply_text("❌ Reklama filtri o'chirildi!")


async def ogohlantirishlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await is_admin(update, user_id):
        return

    warns = get_warns()
    if not warns:
        await update.message.reply_text("Hech kim ogohlantirilmagan.")
        return

    text = "⚠️ *Ogohlantirishlar:*\n\n"
    for uid, count in warns.items():
        text += f"User ID {uid}: {count} ta ogohlantirish\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# =================== XABAR HANDLERI ===================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    user = update.effective_user
    chat = update.effective_chat
    text = message.text

    # DM da faqat savol-javob
    if chat.type == "private":
        answer = find_answer(text)
        if answer:
            await message.reply_text(answer)
        return

    # Guruhda: admin tekshirish
    if await is_admin(update, user.id):
        # Adminlar uchun faqat savol-javob
        answer = find_answer(text)
        if answer:
            await message.reply_text(answer)
        return

    # Reklama filtri
    if FILTER_ENABLED and is_spam(text):
        try:
            await message.delete()
        except Exception:
            pass

        if WARN_BEFORE_BAN:
            warns = get_warns()
            uid = str(user.id)
            warns[uid] = warns.get(uid, 0) + 1
            save_warns(warns)

            if warns[uid] >= WARN_LIMIT:
                try:
                    await chat.ban_member(user.id)
                    await context.bot.send_message(
                        chat.id,
                        f"🚫 {user.first_name} guruhdan chiqarildi (reklama yubordi)."
                    )
                    warns.pop(uid, None)
                    save_warns(warns)
                except Exception as e:
                    logger.error(f"Ban xatosi: {e}")
            else:
                remaining = WARN_LIMIT - warns[uid]
                try:
                    await context.bot.send_message(
                        chat.id,
                        f"⚠️ {user.first_name}, reklama yuborish taqiqlangan!\n"
                        f"Ogohlantirish: {warns[uid]}/{WARN_LIMIT} "
                        f"(yana {remaining} ta qoldi)"
                    )
                except Exception as e:
                    logger.error(f"Ogohlantirish xatosi: {e}")
        else:
            try:
                await chat.ban_member(user.id)
                await context.bot.send_message(
                    chat.id,
                    f"🚫 {user.first_name} reklama uchun guruhdan chiqarildi."
                )
            except Exception as e:
                logger.error(f"Ban xatosi: {e}")
        return

    # Savol-javob
    answer = find_answer(text)
    if answer:
        await message.reply_text(answer)


# =================== ASOSIY FUNKSIYA ===================

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Xato: BOT_TOKEN ni o'zgartiring!")
        print("bot.py faylida BOT_TOKEN = '...' qatorini toping va tokeningizni yozing.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Komanda handlerlari
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yordam", yordam))
    app.add_handler(CommandHandler("qoshish", qoshish))
    app.add_handler(CommandHandler("royxat", royxat))
    app.add_handler(CommandHandler("ochir", ochir))
    app.add_handler(CommandHandler("filter", filter_cmd))
    app.add_handler(CommandHandler("ogohlantirishlar", ogohlantirishlar))

    # Xabar handleri
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot ishga tushdi!")
    print("Guruhga qo'shing va admin qiling.")
    print("To'xtatish uchun Ctrl+C bosing.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
