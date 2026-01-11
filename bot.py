import asyncio
import json
import random
import sqlite3
import time

from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import *


import os
from dotenv import load_dotenv

load_dotenv()
# ================== CONFIG ==================
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not API_TOKEN:
    raise ValueError("❌ BOT_TOKEN topilmadi (.env yoki Railway Variables)")

if not ADMIN_PASSWORD:
    raise ValueError("❌ ADMIN_PASSWORD topilmadi (.env yoki Railway Variables)")

bot = Bot(API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))




DB_NAME = "quiz.db"
QUESTIONS_PER_TEST = 25

bot = Bot(API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ================== DATABASE ==================
def db():
    return sqlite3.connect(DB_NAME)


def init_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        fullname TEXT,
        blocked INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS results(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        correct INTEGER,
        wrong INTEGER,
        skipped INTEGER,
        total INTEGER,
        duration REAL,
        created REAL
    )
    """)

    con.commit()
    con.close()


init_db()

# ================== HELPERS ==================
def safe_option(text):
    t = str(text)
    return t[:95] + "…" if len(t) > 95 else t


def load_questions():
    p = Path("test.json")
    if not p.exists():
        return []
    return json.load(open(p, encoding="utf-8"))


def ensure_user(u):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (u.id,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users(user_id, username, fullname, blocked) VALUES(?,?,?,0)",
            (u.id, u.username or "", u.full_name)
        )
        con.commit()
    con.close()


def is_blocked(uid):
    con = db()
    cur = con.cursor()
    cur.execute("SELECT blocked FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    con.close()
    return bool(row and row[0] == 1)

# ================== STATE ==================
sessions = {}
admin_auth = set()
admin_broadcast = set()


# ================== KEYBOARDS ==================
def main_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="🧪 Yangi test"), KeyboardButton(text="👤 Profil")],
        [KeyboardButton(text="🏆 Reyting"), KeyboardButton(text="📞 Admin bilan bog‘lanish")],
        [KeyboardButton(text="/start")]
    ])


def test_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="⛔ Testni yakunlash")]
    ])


def fan_menu():
    fans = [
        "Sun'iy intellekt asoslari",
        "Kiber xavfsizlik",
        "Elektron sxemalar",
        "Diskret strukturalar",
        "Chiziqli algebra"
    ]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f, callback_data=f"fan|{f}")]
        for f in fans
    ])

# ================== START ==================
@dp.message(Command("start"))
async def start(msg: Message):
    ensure_user(msg.from_user)

    if is_blocked(msg.from_user.id):
        return await msg.answer(
            "🚫 <b>Siz bloklangansiz</b>\n\n"
            "Botdan foydalanish uchun to‘lov qilishingiz kerak.\n"
            "📞 Admin bilan bog‘laning."
        )

    await msg.answer(
        f"Salom, <b>{msg.from_user.first_name}</b>! 🎓\n"
        "Yakuniy nazorat test botiga xush kelibsiz.",
        reply_markup=main_menu()
    )

# ================== PROFILE ==================
@dp.message(F.text == "👤 Profil")
async def profile(msg: Message):
    if is_blocked(msg.from_user.id):
        return await msg.answer("🚫 Siz bloklangansiz!!!\n Sabab: siz bot uchun to'lov qilmagansiz. Bot admini bilan bog'laning iltimos")

    con = db()
    cur = con.cursor()
    cur.execute(
        "SELECT COUNT(*), SUM(correct), SUM(total) FROM results WHERE user_id=?",
        (msg.from_user.id,)
    )
    r = cur.fetchone()
    con.close()

    attempts = r[0] or 0
    correct = r[1] or 0
    total = r[2] or 0
    percent = round(correct / total * 100, 2) if total else 0

    await msg.answer(
        f"👤 <b>Sizning profilingiz</b>\n\n"
        f"📝 Testlar: <b>{attempts}</b>\n"
        f"✔️ To‘g‘ri: <b>{correct}</b>\n"
        f"📊 Savollar: <b>{total}</b>\n"
        f"🎯 Natija: <b>{percent}%</b>"
    )

# ================== ADMIN CONTACT ==================
@dp.message(F.text == "📞 Admin bilan bog‘lanish")
async def admin_contact(msg: Message):
    await msg.answer(
        "📞 <b>Admin bilan bog‘lanish</b>\n\n"
        "👤 Baxtiyorov Ixtiyor\n"
        "Telegram / Instagram / YouTube: @ixtiyor_bv\n"
        "☎️ +998 93 833 77 06"
    )

# ================== TEST FLOW ==================
@dp.message(F.text == "🧪 Yangi test")
async def new_test(msg: Message):
    if is_blocked(msg.from_user.id):
        return await msg.answer( "🚫 <b>Siz bloklangansiz</b>\n\n"
            "Botdan foydalanish uchun to‘lov qilishingiz kerak.\n"
            "📞 Admin bilan bog‘laning.")

    await msg.answer("📚 Fan tanlang:", reply_markup=fan_menu())


@dp.callback_query(F.data.startswith("fan|"))
async def choose_fan(call: CallbackQuery):
    if is_blocked(call.from_user.id):
        return await call.message.answer( "🚫 <b>Siz bloklangansiz</b>\n\n"
            "Botdan foydalanish uchun to‘lov qilishingiz kerak.\n"
            "📞 Admin bilan bog‘laning.")

    fan = call.data.split("|")[1]
    qs = [q for q in load_questions() if q.get("fan") == fan]

    if not qs:
        return await call.message.answer("❗ Bu fan uchun savollar yo‘q")

    parts = (len(qs) + QUESTIONS_PER_TEST - 1) // QUESTIONS_PER_TEST
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{i}-bo‘lim", callback_data=f"part|{fan}|{i}")]
        for i in range(1, parts + 1)
    ])

    await call.message.answer(
        f"📘 <b>{fan}</b>\n"
        f"Jami savollar: <b>{len(qs)}</b>\n"
        f"Bo‘limlar: <b>{parts}</b>",
        reply_markup=kb
    )


@dp.callback_query(F.data.startswith("part|"))
async def choose_part(call: CallbackQuery):
    sessions[call.from_user.id] = {
        "fan": call.data.split("|")[1],
        "part": int(call.data.split("|")[2])
    }

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5 sekund", callback_data="time|5")],
        [InlineKeyboardButton(text="10 sekund", callback_data="time|10")],
        [InlineKeyboardButton(text="25 sekund", callback_data="time|25")]
    ])

    await call.message.answer("⏳ Vaqtni tanlang:", reply_markup=kb)


@dp.callback_query(F.data.startswith("time|"))
async def start_test(call: CallbackQuery):
    uid = call.from_user.id
    sec = int(call.data.split("|")[1])
    s = sessions[uid]

    qs = [q for q in load_questions() if q.get("fan") == s["fan"]]
    start = (s["part"] - 1) * QUESTIONS_PER_TEST
    selected = qs[start:start + QUESTIONS_PER_TEST]
    random.shuffle(selected)

    prepared = []
    for q in selected:
        opts = [safe_option(v) for v in q["variantlar"]]
        mix = list(zip(opts, range(len(opts))))
        random.shuffle(mix)
        prepared.append({
            "q": q["savol"][:300],
            "opts": [m[0] for m in mix],
            "correct": [i for _, i in mix].index(q["togri"])
        })

    s.update({
        "questions": prepared,
        "i": 0,
        "correct": 0,
        "wrong": 0,
        "skipped": 0,
        "time": sec,
        "start": time.time()
    })

    await call.message.answer("✅ Test boshlandi!", reply_markup=test_menu())
    await send_question(uid)

# ================== QUESTIONS ==================
async def send_question(uid):
    s = sessions.get(uid)
    if not s or s["i"] >= len(s["questions"]):
        return await finish(uid)

    q = s["questions"][s["i"]]
    await bot.send_poll(
        uid,
        f"{s['i']+1}-savol:\n{q['q']}",
        q["opts"],
        type="quiz",
        correct_option_id=q["correct"],
        is_anonymous=False
    )
    asyncio.create_task(auto_skip(uid, s["i"]))


async def auto_skip(uid, snap):
    await asyncio.sleep(sessions[uid]["time"])
    if uid in sessions and sessions[uid]["i"] == snap:
        sessions[uid]["skipped"] += 1
        sessions[uid]["i"] += 1
        await send_question(uid)


@dp.poll_answer()
async def poll_answer(ans: PollAnswer):
    uid = ans.user.id
    s = sessions.get(uid)
    if not s:
        return

    if ans.option_ids and ans.option_ids[0] == s["questions"][s["i"]]["correct"]:
        s["correct"] += 1
    else:
        s["wrong"] += 1

    s["i"] += 1
    await send_question(uid)

# ================== FINISH ==================
@dp.message(F.text == "⛔ Testni yakunlash")
async def stop(msg: Message):
    if msg.from_user.id in sessions:
        await finish(msg.from_user.id)


async def finish(uid):
    s = sessions.pop(uid)
    total = len(s["questions"])
    skipped = total - (s["correct"] + s["wrong"])
    duration = round(time.time() - s["start"], 2)

    con = db()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO results(user_id, correct, wrong, skipped, total, duration, created) VALUES(?,?,?,?,?,?,?)",
        (uid, s["correct"], s["wrong"], skipped, total, duration, time.time())
    )
    con.commit()
    con.close()

    await bot.send_message(
        uid,
        f"🏁 <b>Test yakunlandi</b>\n\n"
        f"✔️ To‘g‘ri: <b>{s['correct']}</b>\n"
        f"❌ Xato: <b>{s['wrong']}</b>\n"
        f"⏭ O‘tkazilgan: <b>{skipped}</b>\n"
        f"📊 Jami: <b>{total}</b>\n"
        f"⏱ Vaqt: <b>{duration}s</b>",
        reply_markup=main_menu()
    )

# ================== RATING ==================
@dp.message(F.text == "🏆 Reyting")
async def rating(msg: Message):
    con = db()
    cur = con.cursor()
    cur.execute("""
        SELECT u.username, u.fullname, SUM(r.correct)
        FROM results r
        JOIN users u ON u.user_id = r.user_id
        GROUP BY r.user_id
        ORDER BY SUM(r.correct) DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    con.close()

    if not rows:
        return await msg.answer("📉 Reyting yo‘q")

    text = "🏆 <b>Umumiy Reyting</b>\n\n"
    for i, (u, f, s) in enumerate(rows, 1):
        name = f"@{u}" if u else f
        text += f"{i}. {name} — {s} to‘g‘ri\n"

    await msg.answer(text)

# ================== ADMIN ==================
@dp.message(Command("admin"))
async def admin(msg: Message):
    await msg.answer("🔐 Ixtiyor agar siz bo'lsangiz parolni tasdiqlang:")


@dp.message(F.text == ADMIN_PASSWORD)
async def admin_login(msg: Message):
    admin_auth.add(msg.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Userlar (bloklash)", callback_data="admin_users")],
        [InlineKeyboardButton(text="♻️ Natijalarni 0 qilish", callback_data="admin_reset")],
        [InlineKeyboardButton(text="📢 Foydalanuvchilarga xabar yuborish", callback_data="admin_broadcast")]
    ])
    await msg.answer("🛠 <b>Admin Panel</b>", reply_markup=kb)






@dp.message(F.from_user.id.in_(lambda: admin_broadcast))
async def admin_send_broadcast(msg: Message):
    uid = msg.from_user.id

    if uid not in admin_auth:
        return

    admin_broadcast.discard(uid)

    con = db()
    cur = con.cursor()
    cur.execute("SELECT user_id FROM users WHERE blocked = 0")
    users = cur.fetchall()
    con.close()

    sent = 0
    failed = 0

    for (user_id,) in users:
        try:
            await bot.send_message(user_id, msg.text)
            sent += 1
            await asyncio.sleep(0.05)  # flooddan saqlaydi
        except:
            failed += 1

    await msg.answer(
        f"✅ <b>Xabar yuborildi</b>\n\n"
        f"👥 Yuborildi: <b>{sent}</b>\n"
        f"❌ Yetib bormadi: <b>{failed}</b>"
    )







@dp.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):
    if call.from_user.id not in admin_auth:
        return

    con = db()
    cur = con.cursor()
    cur.execute("SELECT user_id, username, fullname, blocked FROM users")
    rows = cur.fetchall()
    con.close()

    kb = []
    for uid, u, f, b in rows:
        name = f"@{u}" if u else f or uid
        status = "🚫" if b else "✔️"
        kb.append([
            InlineKeyboardButton(
                text=f"{status} {name}",
                callback_data=f"toggle|{uid}"
            )
        ])

    await call.message.answer(
        "👥 Userlar (bosib bloklash / ochish):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@dp.callback_query(F.data.startswith("toggle|"))
async def toggle(call: CallbackQuery):
    if call.from_user.id not in admin_auth:
        return

    uid = int(call.data.split("|")[1])
    con = db()
    cur = con.cursor()
    cur.execute("SELECT blocked FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()

    new = 0 if row and row[0] else 1
    cur.execute("UPDATE users SET blocked=? WHERE user_id=?", (new, uid))
    con.commit()
    con.close()

    await call.answer("Holat o‘zgartirildi", show_alert=True)



@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery):
    if call.from_user.id not in admin_auth:
        return await call.answer("❌ Ruxsat yo‘q", show_alert=True)

    admin_broadcast.add(call.from_user.id)
    await call.message.answer(
        "📢 <b>Barcha foydalanuvchilarga yuboriladigan xabarni yozing:</b>\n\n"
        "❗ Keyingi yuborgan xabaringiz hammaga jo‘natiladi."
    )
    await call.answer()






@dp.callback_query(F.data == "admin_reset")
async def admin_reset(call: CallbackQuery):
    # faqat admin kirgan bo‘lishi shart
    if call.from_user.id not in admin_auth:
        return await call.answer("❌ Ruxsat yo‘q", show_alert=True)

    con = db()
    cur = con.cursor()

    # 🔥 ASOSIY RESET
    cur.execute("DELETE FROM results")
    con.commit()
    con.close()

    await call.message.answer("♻️ <b>Barcha natijalar 0 qilindi</b>")
    await call.answer()


# ================== RUN ==================
async def main():
    print("BOT ISHGA TUSHDI...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())



print("BOT VERSION FROM VSCODE")

