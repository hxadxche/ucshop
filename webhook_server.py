from flask import Flask, request, abort
import hashlib
import sqlite3
import asyncio
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

app = Flask(__name__)
NOTIFICATION_SECRET = "sgtipI6iQlaXCB1XCgksTaP5"

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
        abort(400, "Invalid SHA-1")

    label = data.get("label")
    if not label:
        abort(400, "Empty label")

    try:
        conn = sqlite3.connect("users_orders.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT label, quantity FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 1",
            (label,)
        )
        result = cursor.fetchone()
        if not result:
            conn.close()
            return "No order found", 200

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
        conn.close()

        async def send_telegram():
            session = AiohttpSession()
            bot = Bot(token="8024102805:AAEcu22cIkfe49UNNC_XlKB1mZMxFRx6aDk", session=session, parse_mode=ParseMode.HTML)
            text = f"✅ Ваш платёж подтверждён!\n🎁 Ваши UC-коды ({pack_label}):\n\n"
            text += "\n".join(f"<code>{c[1]}</code>" for c in codes)
            try:
                await bot.send_message(chat_id=int(label), text=text)
            except Exception as e:
                print("Ошибка Telegram:", e)
            await session.close()

        asyncio.run(send_telegram())
        return "OK", 200

    except Exception as e:
        print("Ошибка обработки запроса:", e)
        abort(500, "Server Error")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
