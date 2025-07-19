import os
import asyncio
import hashlib
import sqlite3
from flask import Flask, request, abort
from aiogram import Bot
from aiogram.enums import ParseMode

app = Flask(__name__)
NOTIFICATION_SECRET = "sgtipI6iQlaXCB1XCgksTaP5"
BOT_TOKEN = "8024102805:AAEcu22cIkfe49UNNC_XlKB1mZMxFRx6aDk"

def verify_sha1(data: dict):
    raw_string = (
        f"{data.get('notification_type')}&"
        f"{data.get('operation_id')}&"
        f"{data.get('amount')}&"
        f"{data.get('currency')}&"
        f"{data.get('datetime')}&"
        f"{data.get('sender')}&"
        f"{data.get('codepro')}&"
        f"{NOTIFICATION_SECRET}&"
        f"{data.get('label')}"
    )
    sha1 = hashlib.sha1(raw_string.encode("utf-8")).hexdigest()
    return sha1 == data.get("sha1_hash")

@app.route("/yoomoney_webhook", methods=["POST"])
def yoomoney_webhook():
    data = request.form.to_dict()

    if not verify_sha1(data):
        abort(400, "Invalid hash")

    label = data.get("label")
    if not label:
        abort(400, "Label is empty")

    conn = sqlite3.connect("users_orders.db")
    cursor = conn.cursor()

    # Получаем заказ по метке
    cursor.execute(
        "SELECT label, quantity, user_id FROM orders WHERE yoomoney_label = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
        (label,)
    )
    result = cursor.fetchone()
    if not result:
        conn.close()
        return "No matching order", 200

    pack_label, quantity, user_id = result
    order_id = label.split("_")[1]

    # Достаём коды
    cursor.execute(
        "SELECT id, code FROM uc_codes WHERE label = ? AND used = 0 LIMIT ?",
        (pack_label, quantity)
    )
    codes = cursor.fetchall()
    if len(codes) < quantity:
        conn.close()
        return "Not enough codes", 200

    code_ids = [c[0] for c in codes]
    cursor.executemany(
        "UPDATE uc_codes SET used = 1, order_id = ? WHERE id = ?",
        [(order_id, i) for i in code_ids]
    )
    cursor.execute("UPDATE orders SET status = 'completed' WHERE yoomoney_label = ?", (label,))
    conn.commit()

    text = f"✅ Ваша оплата подтверждена!\n🎁 Ваши UC-коды ({pack_label}):\n\n"
    text += "\n".join(f"<code>{c[1]}</code>" for c in codes)

    async def send_codes():
        bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
        try:
            await bot.send_message(chat_id=user_id, text=text)
        finally:
            await bot.session.close()

    asyncio.run(send_codes())

    conn.close()
    return "OK", 200

@app.route("/")
def home():
    return "Webhook is working", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
