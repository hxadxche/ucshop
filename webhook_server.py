from flask import Flask, request, abort
import hashlib
import hmac
import sqlite3
import asyncio

from aiogram import Bot
from aiogram.enums import ParseMode

app = Flask(__name__)

# === Твой Telegram-бот ===
bot = Bot(token="8024102805:AAEcu22cIkfe49UNNC_XlKB1mZMxFRx6aDk", parse_mode=ParseMode.HTML)

# === Секрет ЮMoney ===
NOTIFICATION_SECRET = "sgtipI6iQlaXCB1XCgksTaP5"

# === Проверка SHA1 ===
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

# === Webhook-обработчик ===
@app.route("/yoomoney_webhook", methods=["POST"])
def yoomoney_webhook():
    data = request.form.to_dict()
    print("Получен запрос:", data)

    if not verify_sha1(data):
        abort(400, "Invalid hash")

    label = data.get("label")  # Telegram user_id
    if not label:
        abort(400, "Label is empty")

    conn = sqlite3.connect("users_orders.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT label, quantity FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 1",
        (label,)
    )
    result = cursor.fetchone()
    if not result:
        conn.close()
        return "No order", 200

    pack_label, quantity = result

    cursor.execute(
        "SELECT id, code FROM uc_codes WHERE label = ? AND used = 0 LIMIT ?",
        (pack_label, quantity)
    )
    codes = cursor.fetchall()

    if len(codes) < quantity:
        conn.close()
        return "Not enough codes", 200

    code_ids = [c[0] for c in codes]
    cursor.executemany("UPDATE uc_codes SET used = 1 WHERE id = ?", [(i,) for i in code_ids])
    conn.commit()

    text = f"✅ Ваша оплата подтверждена!\n🎁 Ваши UC-коды ({pack_label}):\n\n"
    text += "\n".join(f"<code>{c[1]}</code>" for c in codes)

    try:
        asyncio.run(bot.send_message(chat_id=int(label), text=text))
    except Exception as e:
        print("❌ Ошибка отправки сообщения:", e)

    conn.close()
    return "OK", 200

# === Запуск сервера ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
