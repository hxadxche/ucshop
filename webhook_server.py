from flask import Flask, request, abort
import hashlib
import sqlite3
import asyncio
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

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
    try:
        data = request.form.to_dict()
        print("Получен webhook:", data)

        if not verify_sha1(data):
            print("❌ Хеш не совпадает")
            abort(400, "Invalid hash")

        label = data.get("label")
        if not label:
            abort(400, "Label is missing")

        conn = sqlite3.connect("users_orders.db")
        cursor = conn.cursor()

        cursor.execute("SELECT label, quantity FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 1", (label,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return "No order", 200

        pack_label, quantity = result

        cursor.execute("SELECT id, code FROM uc_codes WHERE label = ? AND used = 0 LIMIT ?", (pack_label, quantity))
        codes = cursor.fetchall()

        if len(codes) < quantity:
            conn.close()
            return "Not enough codes", 200

        code_ids = [c[0] for c in codes]
        cursor.executemany("UPDATE uc_codes SET used = 1 WHERE id = ?", [(i,) for i in code_ids])
        conn.commit()
        conn.close()

        async def send():
            session = AiohttpSession()
            bot = Bot(token="ТВОЙ_ТОКЕН", session=session, parse_mode=ParseMode.HTML)
            msg = f"✅ Оплата подтверждена!\n🎁 Ваши UC-коды ({pack_label}):\n\n"
            msg += "\n".join(f"<code>{c[1]}</code>" for c in codes)
            try:
                await bot.send_message(chat_id=int(label), text=msg)
            except Exception as e:
                print("❌ Ошибка при отправке:", e)
            await bot.session.close()

        asyncio.run(send())

        return "OK", 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return "CRASH", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
