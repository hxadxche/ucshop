import os
import hashlib
import sqlite3
import logging
from flask import Flask, request, abort
from aiogram import Bot
from aiogram.enums import ParseMode
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=5)

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("YooMoneyWebhook")

# Конфигурация из переменных окружения
NOTIFICATION_SECRET = os.getenv("YOOMONEY_SECRET", "sgtipI6iQlaXCB1XCgksTaP5")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
DATABASE_PATH = os.getenv("DATABASE_PATH", "users_orders.db")

# Инициализируем бота один раз при запуске
bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)

def verify_sha1(data: dict) -> bool:
    """Проверяет подпись уведомления от YooMoney"""
    required_fields = [
        'notification_type', 'operation_id', 'amount', 'currency', 
        'datetime', 'sender', 'codepro', 'label'
    ]
    
    if any(field not in data for field in required_fields):
        logger.error("Missing required fields in notification")
        return False

    raw_string = (
        f"{data['notification_type']}&"
        f"{data['operation_id']}&"
        f"{data['amount']}&"
        f"{data['currency']}&"
        f"{data['datetime']}&"
        f"{data['sender']}&"
        f"{data['codepro']}&"
        f"{NOTIFICATION_SECRET}&"
        f"{data['label']}"
    )
    
    sha1 = hashlib.sha1(raw_string.encode("utf-8")).hexdigest()
    return sha1 == data.get("sha1_hash")

async def send_telegram_message(user_id: int, codes: list, pack_label: str):
    """Асинхронно отправляет сообщение с кодами в Telegram"""
    try:
        text = (
            "✅ <b>Ваша оплата подтверждена!</b>\n"
            f"🎁 Ваши UC-коды ({pack_label}):\n\n"
        )
        text += "\n".join(f"<code>{code}</code>" for _, code in codes)
        
        await bot.send_message(chat_id=user_id, text=text)
        logger.info(f"Message sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending message to user {user_id}: {e}")

def process_payment(data: dict):
    """Обрабатывает платеж и выдает коды"""
    if not verify_sha1(data):
        logger.warning("Invalid SHA1 hash. Possible fraud attempt.")
        return "Invalid hash", 400

    label = data.get("label")
    if not label:
        logger.error("Empty label in payment notification")
        return "Label is empty", 400

    try:
        user_id = int(label)
    except ValueError:
        logger.error(f"Invalid user_id format: {label}")
        return "Invalid user_id format", 400

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Получаем последний заказ пользователя
        cursor.execute(
            "SELECT id, pack_label, quantity, amount FROM orders "
            "WHERE user_id = ? AND status = 'pending' "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        order = cursor.fetchone()
        
        if not order:
            logger.error(f"No pending orders for user {user_id}")
            return "No pending order found", 200

        order_id, pack_label, quantity, order_amount = order

        # Проверяем сумму платежа
        if float(data["amount"]) != order_amount:
            logger.error(
                f"Amount mismatch for order {order_id}: "
                f"payment {data['amount']} != order {order_amount}"
            )
            return "Amount mismatch", 400

        # Получаем коды
        cursor.execute(
            "SELECT id, code FROM uc_codes "
            "WHERE pack_label = ? AND used = 0 "
            "LIMIT ?",
            (pack_label, quantity)
        )
        codes = cursor.fetchall()

        if len(codes) < quantity:
            logger.error(
                f"Not enough codes for pack {pack_label}. "
                f"Needed: {quantity}, available: {len(codes)}"
            )
            return "Not enough codes", 200

        # Обновляем коды и заказ
        code_ids = [c[0] for c in codes]
        cursor.executemany(
            "UPDATE uc_codes SET used = 1, order_id = ? WHERE id = ?",
            [(order_id, cid) for cid in code_ids]
        )
        
        cursor.execute(
            "UPDATE orders SET status = 'completed' WHERE id = ?",
            (order_id,)
        )
        
        conn.commit()
        logger.info(f"Order {order_id} completed. {quantity} codes activated.")

        # Отправляем коды асинхронно
        asyncio.run(send_telegram_message(user_id, codes, pack_label))
        
        return "OK", 200
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return "Database error", 500
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "Internal server error", 500
    finally:
        conn.close()

@app.route("/yoomoney_webhook", methods=["POST"])
def yoomoney_webhook():
    """Эндпоинт для обработки вебхуков от YooMoney"""
    try:
        # Запускаем обработку в отдельном потоке
        data = request.form.to_dict()
        future = executor.submit(process_payment, data)
        result, status = future.result()
        return result, status
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return "Internal server error", 500

if __name__ == "__main__":
    # Создаем таблицы, если их нет
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        
        # Таблица заказов
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            pack_label TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'canceled')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Таблица кодов
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS uc_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            pack_label TEXT NOT NULL,
            used BOOLEAN DEFAULT 0,
            order_id INTEGER,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
        """)
        
        conn.commit()
    
    # Запускаем Flask-сервер
    app.run(host="0.0.0.0", port=5000, debug=False)
