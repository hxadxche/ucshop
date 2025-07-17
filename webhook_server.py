from flask import Flask, request, abort
import hashlib
import sqlite3
import asyncio
from aiogram import Bot
from aiogram.enums import ParseMode

app = Flask(__name__)

# 🔐 Секрет из настроек ЮMoney
NOTIFICATION_SECRET = "sgtipI6iQlaXCB1XCgksTaP5"

# 🎯 Проверка SHA-1 подписи
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

# 🧠 Webhook-обработчик
@app.route("/yoomoney_webhook", methods=["POST"])
def yoomoney_webhook():
    try:
        data = request.form.to_dict()
        print("📥 Получены данные от ЮMoney:", data)

        if not verify_sha1(data):
            print("❌ Хэш не совпадает!")
            abort(400, "Invalid hash")

        label = data.get("label")
        if not label:
            print("❌ Label отсутствует!")
            abort(400, "Label is empty")

        # 📦 Подключаемся к базе
        conn = sqlite3.connect("users_orders.db")
        cursor = conn.cursor()

        # 📝 Ищем последний заказ
        cursor.execute(
            "SELECT label, quantity FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 1",
            (label,)
        )
        result = cursor.fetchone()
        if not result:
            print("⚠️ Заказ по label не найден")
            conn.close()
            return "No order", 200

        pack_label, quantity = result
        print(f"📦 Заказ: {pack_label}, {quantity} шт.")

        # 🧾 Получаем коды
        cursor.execute(
            "SELECT id, code FROM uc_codes WHERE label = ? AND used = 0 LIMIT ?",
            (pack_label, quantity)
        )
        codes = cursor.fetchall()

        if len(codes) < quantity:
            print("⚠️ Недостаточно кодов для выдачи")
            conn.close()
            return "Not enough codes", 200

        # ✅ Отмечаем использованные коды
        code_ids = [c[0] for c in codes]
        cursor.executemany("UPDATE uc_codes SET used = 1 WHERE id = ?", [(i,) for i in code_ids])
        conn.commit()

        # 📤 Отправка в Telegram
        bot = Bot(token="8024102805:AAEcu22cIkfe49UNNC_XlKB1mZMxFRx6aDk", parse_mode=ParseMode.HTML)

        text = f"✅ Ваша оплата подтверждена!\n🎁 Ваши UC-коды ({pack_label}):\n\n"
        text += "\n".join(f"<code>{c[1]}</code>" for c in codes)

        asyncio.run(bot.send_message(chat_id=int(label), text=text))

        conn.close()
        return "OK", 200

    except Exception as e:
        print("🔥 ОШИБКА В ВЕБХУКЕ:", e)
        return "Ошибка на сервере", 500

# 🚀 Запуск сервера
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
