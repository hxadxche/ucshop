import os
import hashlib
import sqlite3
import logging
from flask import Flask, request
from aiogram import Bot
from aiogram.enums import ParseMode
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=5)

# Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("YooMoneyWebhook")

# Конфигурация
NOTIFICATION_SECRET = os.getenv("NOTIFICATION_SECRET", "sgtipI6iQlaXCB1XCgksTaP5")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8024102805:AAEcu22cIkfe49UNNC_XlKB1mZMxFRx6aDk")
DATABASE_PATH = os.getenv("DATABASE_PATH", "users_orders.db")

bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
bot_loop = asyncio.get_event_loop()

def verify_sha1(data: dict) -> bool:
    """Проверяет подпись от YooMoney"""
    required = ['notification_type', 'operation_id', 'amount', 'currency', 'datetime', 'sender', 'codepro', 'label']
    if any(k not in data for k in required):
        return False

    raw = (
        f"{data['notification_type']}&{data['operation_id']}&{data['amount']}&{data['currency']}&"
        f"{data['datetime']}&{data['sender']}&{data['codepro']}&{NOTIFICATION_SECRET}&{data['label']}"
    )
    return hashlib.sha1(raw.encode()).hexdigest() == data.get("sha1_hash")

async def send_telegram(user_id: int, codes: list, pack_label: str):
    text = f"✅ <b>Ваша оплата подтверждена!</b>\n🎁 Ваши UC-коды ({pack_label}):\n\n"
    text += "\n".join(f"<code>{c[1]}</code>" for c in codes)
    try:
        await bot.send_message(chat_id=user_id, text=text)
        logger.info(f"✅ Коды отправлены пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")

def process_payment(data: dict):
    if not verify_sha1(data):
        logger.warning("⚠️ Подпись не прошла проверку!")
        return "Invalid hash", 400

    label = data.get("label")
    try:
        user_id = int(label)
    except:
        return "Invalid label format", 400

    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, pack_label, quantity, amount FROM orders WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        order = cursor.fetchone()
        if not order:
            return "No pending order", 200

        order_id, pack_label, quantity, order_amount = order
        if float(data["amount"]) != order_amount:
            return "Amount mismatch", 400

        cursor.execute(
            "SELECT id, code FROM uc_codes WHERE pack_label = ? AND used = 0 LIMIT ?",
            (pack_label, quantity)
        )
        codes = cursor.fetchall()
        if len(codes) < quantity:
            return "Not enough codes", 200

        code_ids = [c[0] for c in codes]
        cursor.executemany(
            "UPDATE uc_codes SET used = 1, order_id = ? WHERE id = ?",
            [(order_id, cid) for cid in code_ids]
        )
        cursor.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
        conn.commit()

        # Асинхронно отправляем сообщение
        asyncio.run_coroutine_threadsafe(send_telegram(user_id, codes, pack_label), bot_loop)

        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка обработки: {e}")
        return "Internal error", 500
    finally:
        conn.close()

@app.route("/yoomoney_webhook", methods=["POST"])
def webhook():
    data = request.form.to_dict()
    future = executor.submit(process_payment, data)
    result, status = future.result()
    return result, status

if __name__ == "__main__":
    # Инициализация базы, если не существует
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            pack_label TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'canceled')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS uc_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            pack_label TEXT NOT NULL,
            used BOOLEAN DEFAULT 0,
            order_id INTEGER,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )""")
        conn.commit()

    logger.info("✅ Сервер запущен: http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)

