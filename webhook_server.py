import os
import asyncio
import hashlib
from flask import Flask, request, abort
from aiogram import Bot
from aiogram.enums import ParseMode
import asyncpg

app = Flask(__name__)

# Настройки
NOTIFICATION_SECRET = "sgtipI6iQlaXCB1XCgksTaP5"
BOT_TOKEN = "7587423228:AAHhVNFsKeWo8ck7xdDL1U8NHzTFsqDgZBE"

# Функция подключения к PostgreSQL
_pg_pool = None
async def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await asyncpg.create_pool(
            dsn=os.environ.get("postgresql://postgres:xRbtSljvnJweJPlmYvjbiCdvbqYequqF@postgres.railway.internal:5432/railway")  # Railway использует DATABASE_URL
        )
    return _pg_pool

# Проверка SHA1
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

# Основной webhook
@app.route("/yoomoney_webhook", methods=["POST"])
def yoomoney_webhook():
    data = request.form.to_dict()
    print("\n=== YOOMONEY HOOK RECEIVED ===")
    print(data)

    if not verify_sha1(data):
        print("❌ Ошибка SHA1: неверная подпись")
        abort(400, "Invalid hash")

    label = data.get("label")
    if not label:
        print("❌ Нет label в запросе")
        abort(400, "Label is empty")

    # Обработка внутри асинхронной обёртки
    asyncio.run(handle_payment(data))

    return "OK", 200

# Обработка платежа
async def handle_payment(data):
    label = data.get("label")
    paid_price = float(data.get("amount", "0"))

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await conn.fetchrow(
                "SELECT label, quantity, user_id, price FROM orders WHERE yoomoney_label = $1 AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
                label
            )
            if not result:
                print("❌ Не найден заказ:", label)
                return

            pack_label = result["label"]
            quantity = result["quantity"]
            user_id = result["user_id"]
            expected_price = result["price"]

            print(f"✅ Найден заказ: {label}, user_id={user_id}, сумма={expected_price}")

            if paid_price < expected_price:
                print(f"❌ Недостаточная сумма: {paid_price} < {expected_price}")
                return

            order_id = label.split("_")[1]

            codes = await conn.fetch(
                "SELECT id, code FROM uc_codes WHERE label = $1 AND used = FALSE LIMIT $2",
                pack_label, quantity
            )

            if len(codes) < quantity:
                print("❌ Недостаточно кодов в наличии")
                return

            code_ids = [c["id"] for c in codes]
            for code_id in code_ids:
                await conn.execute(
                    "UPDATE uc_codes SET used = TRUE, order_id = $1 WHERE id = $2",
                    order_id, code_id
                )

            await conn.execute(
                "UPDATE orders SET status = 'completed' WHERE yoomoney_label = $1",
                label
            )

    # Отправка сообщения
    text = f"✅ Ваша оплата подтверждена!\n🎁 Ваши UC-коды ({pack_label}):\n\n"
    text += "\n".join(f"<code>{c['code']}</code>" for c in codes)

    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    try:
        await bot.send_message(chat_id=user_id, text=text)
    finally:
        await bot.session.close()


@app.route("/")
def home():
    return "Webhook is working", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
