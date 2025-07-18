
import asyncio
import sqlite3
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import requests

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TelegramBot")

# === SQLite ===
conn = sqlite3.connect("users_orders.db")
cursor = conn.cursor()

# Создание таблиц с обновленной структурой
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        reg_date TEXT
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS uc_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT,
        code TEXT,
        used INTEGER DEFAULT 0
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        pack_label TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        amount REAL NOT NULL,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'completed', 'canceled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        payment_method TEXT
    )
""")
conn.commit()

# Заполнение тестовыми данными
sample_data = [
    ("60 UC", "60CODE1"), ("60 UC", "60CODE2"), ("60 UC", "60CODE3"), ("60 UC", "60CODE4"), ("60 UC", "60CODE5"),
    ("325 UC", "325CODE1"), ("325 UC", "325CODE2"), ("325 UC", "325CODE3"), ("325 UC", "325CODE4"),
    ("385 UC", "385CODE1"), ("385 UC", "385CODE2"), ("385 UC", "385CODE3"), ("385 UC", "385CODE4"),
    ("660 UC", "660CODE1"), ("660 UC", "660CODE2"), ("660 UC", "660CODE3"), ("660 UC", "660CODE4"),
    ("720 UC", "720CODE1"), ("720 UC", "720CODE2"), ("720 UC", "720CODE3"), ("720 UC", "720CODE4"),
    ("1320 UC", "1320CODE1"), ("1320 UC", "1320CODE2"), ("1320 UC", "1320CODE3"), ("1320 UC", "1320CODE4"),
]

# Проверка и заполнение кодов
cursor.execute("SELECT COUNT(*) FROM uc_codes")
if cursor.fetchone()[0] == 0:
    for label, code in sample_data:
        cursor.execute("INSERT INTO uc_codes (label, code) VALUES (?, ?)", (label, code))
    conn.commit()

# === Bot config ===
API_TOKEN = "8024102805:AAEcu22cIkfe49UNNC_XlKB1mZMxFRx6aDk"
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Конфигурация вебхук-сервера
WEBHOOK_URL = "https://your-webhook-server.com/yoomoney_webhook"  # Замените на реальный URL
YOOMONEY_WALLET = "4100111899459093"  # Ваш кошелек YooMoney

# === Состояния ===
class UCState(StatesGroup):
    choosing_quantity = State()
    choosing_payment_method = State()
    waiting_for_receipt_photo = State()

# === Команда /start ===
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, reg_date) VALUES (?, ?, ?, ?)",
            (user_id, message.from_user.username, message.from_user.first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

    kb = ReplyKeyboardBuilder()
    kb.button(text="Купить UC")
    kb.button(text="UC в наличии")
    kb.button(text="Помощь")
    kb.button(text="Профиль")
    kb.adjust(2)

    await state.clear()
    await message.answer(
        "⚡️Приветствуем тебя в автоматическом боте покупки UC кодов 🔥\n\n"
        "Официальная группа: https://t.me/CHUDO_UC_SHOP\n\n"
        "Бот работает 24/7 с паками от 60 UC\n\n"
        "Если возникнут какие-то вопросы: @chudoo_19",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == "UC в наличии")
async def uc_in_stock(message: Message):
    stock_info = "<b>📦 UC в наличии:</b>\n\n"
    for label in ["60 UC", "325 UC", "385 UC", "660 UC", "720 UC", "1320 UC"]:
        cursor.execute("SELECT COUNT(*) FROM uc_codes WHERE label = ? AND used = 0", (label,))
        count = cursor.fetchone()[0]
        stock_info += f"• {label} — {count} шт.\n"
    await message.answer(stock_info)

@dp.message(F.text == "Купить UC")
async def show_categories(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="UC Pubg Mobile")
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text == "UC Pubg Mobile")
async def show_uc_packages(message: Message):
    kb = ReplyKeyboardBuilder()
    uc_packages = [
        ("60 UC", 80), 
        ("325 UC", 380), 
        ("385 UC", 450), 
        ("660 UC", 790), 
        ("720 UC", 900), 
        ("1320 UC", 1580)
    ]
    
    for label, price in uc_packages:
        cursor.execute("SELECT COUNT(*) FROM uc_codes WHERE label = ? AND used = 0", (label,))
        count = cursor.fetchone()[0]
        kb.button(text=f"{label} | {price} RUB | {count} шт.")
    
    kb.button(text="⬅️ Назад ко всем категориям")
    kb.adjust(1)
    await message.answer("Категория: UC Pubg Mobile", reply_markup=kb.as_markup(resize_keyboard=True))

async def send_quantity_menu(message: Message, quantity: int, unit_price: int, label: str):
    total_price = quantity * unit_price
    kb = ReplyKeyboardBuilder()
    for val in [-5, -3, -1, +1, +3, +5]:
        kb.button(text=f"{'+' if val > 0 else ''}{val}")
    kb.adjust(3)
    kb.button(text="✅ Подтверждаю")
    kb.button(text="❌ Отмена")
    kb.button(text="🔙 Назад")
    kb.button(text="⬅️ Назад ко всем категориям")
    kb.adjust(2)
    await message.answer(
        f"<b>🛒 Товар:</b> {label}\n"
        f"<b>💰 Цена за штуку:</b> {unit_price} RUB\n"
        f"<b>📦 Количество:</b> {quantity} шт.\n"
        f"<b>💸 Общая сумма:</b> {total_price} RUB",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

async def handle_uc_package(message: Message, state: FSMContext, label: str, unit_price: int):
    await state.set_state(UCState.choosing_quantity)
    await state.update_data(quantity=1, unit_price=unit_price, label=label)
    await send_quantity_menu(message, 1, unit_price, label)

# Обработчики для каждого пакета UC
uc_packages = [
    ("60 UC", 80), 
    ("325 UC", 380), 
    ("385 UC", 450), 
    ("660 UC", 790), 
    ("720 UC", 900), 
    ("1320 UC", 1580)
]

for label, price in uc_packages:
    @dp.message(F.text.startswith(label))
    async def handle_uc_package_wrapper(message: Message, state: FSMContext, lbl=label, prc=price):
        await handle_uc_package(message, state, lbl, prc)

@dp.message(UCState.choosing_quantity, F.text.in_(["+1", "+3", "+5", "-1", "-3", "-5"]))
async def change_quantity(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity = max(1, data.get("quantity", 1) + int(message.text))
    await state.update_data(quantity=quantity)
    await send_quantity_menu(message, quantity, data.get("unit_price", 0), data.get("label", "UC"))

@dp.message(UCState.choosing_quantity, F.text == "✅ Подтверждаю")
async def confirm_order(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity    = data.get("quantity", 1)
    unit_price  = data.get("unit_price", 0)
    label       = data.get("label", "UC")
    total_price = quantity * unit_price

    # Проверка наличия кодов
    cursor.execute(
        "SELECT COUNT(*) FROM uc_codes WHERE label = ? AND used = 0",
        (label,)
    )
    available = cursor.fetchone()[0]

    if available < quantity:
        kb = ReplyKeyboardBuilder()
        kb.button(text="⬅️ Назад ко всем категориям")
        kb.button(text="❌ Отмена")
        kb.adjust(1)

        await message.answer(
            f"❌ Недостаточно UC-кодов в наличии для {label}.\n"
            f"Вы выбрали: {quantity}, доступно: {available}.\n\n"
            "Пожалуйста, выберите меньшее количество или другой пакет.",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )
        return
    
    # Сохранение заказа в БД
    user_id = message.from_user.id
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute(
        "INSERT INTO orders (user_id, pack_label, quantity, amount, status) VALUES (?, ?, ?, ?, ?)",
        (user_id, label, quantity, total_price, "pending")
    )
    order_id = cursor.lastrowid
    conn.commit()
    
    await state.update_data(order_id=order_id, total_price=total_price)
    
    # Переход к выбору способа оплаты
    await state.set_state(UCState.choosing_payment_method)
    kb = ReplyKeyboardBuilder()
    kb.button(text="💳 Оплата переводом на карту")
    kb.button(text="🟣 Оплата через Ю-Money")
    kb.button(text="❌ Отмена")
    kb.adjust(1)

    await message.answer(
        f"<b>🧾 Вы выбрали:</b>\n"
        f"{quantity} x {label}\n"
        f"<b>💸 К оплате:</b> {total_price} RUB\n\n"
        "Выберите способ оплаты:",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message(UCState.choosing_payment_method, F.text == "💳 Оплата переводом на карту")
async def payment_card(message: Message, state: FSMContext):
    data = await state.get_data()
    label = data.get("label", "UC")
    unit_price = data.get("unit_price", 0)
    quantity = data.get("quantity", 1)
    total_price = quantity * unit_price
    now = datetime.now()
    
    # Обновление метода оплаты в заказе
    order_id = data.get("order_id")
    if order_id:
        cursor.execute(
            "UPDATE orders SET payment_method = ? WHERE id = ?",
            ("card", order_id)
        )
        conn.commit()

    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Я оплатил")], [KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

    await message.answer(
        f"📦 <b>Товар:</b> {label}\n"
        f"💰 <b>Цена:</b> {unit_price} RUB\n"
        f"📦 <b>Кол-во:</b> {quantity} шт.\n"
        f"⏰ <b>Время заказа:</b> {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"💸 <b>Итоговая сумма:</b> {total_price} RUB\n"
        "============================\n"
        f"⚠️ <b>ПЕРЕВОДИТЬ СТРОГО УКАЗАННУЮ СУММУ</b>\n"
        "Если вы перевели не туда — деньги не возвращаются.\n\n"
        f"Для оплаты переведите <b>{total_price} RUB</b> на карту:\n"
        "<code>2202 2084 3750 2835</code>\n"
        "СБП - Альфа Банк: <code>+79648469752</code>\n\n"
        "<b>Сохраните чек!</b>\n"
        "После оплаты нажмите на кнопку <b>«Я оплатил»</b> и отправьте фото.",
        reply_markup=kb
    )
    await state.set_state(UCState.waiting_for_receipt_photo)

@dp.message(F.text == "Я оплатил")
async def handle_payment_confirmation(message: Message, state: FSMContext):
    await message.answer("📸 Пожалуйста, отправьте фото чека (скриншот подтверждения перевода).")
    await state.set_state(UCState.waiting_for_receipt_photo)

@dp.message(UCState.waiting_for_receipt_photo, F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext):
    ADMIN_ID = 1001953510
    user = message.from_user
    data = await state.get_data()
    order_id = data.get("order_id")
    
    caption = (
        f"📩 Новый платёж по карте!\n\n"
        f"👤 Пользователь: @{user.username or 'без username'}\n"
        f"🆔 ID: {user.id}\n"
        f"👁 Имя: {user.first_name}\n"
        f"📊 Заказ: #{order_id}\n\n"
        f"🧾 Проверьте чек:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждено", callback_data=f"confirm_{user.id}_{order_id}")],
        [InlineKeyboardButton(text="❌ Отказ", callback_data=f"reject_{user.id}_{order_id}")]
    ])

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=caption,
        reply_markup=keyboard
    )

    await message.answer("✅ Чек отправлен администратору на проверку. Мы сообщим, как только он подтвердит оплату.")
    await state.clear()

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(call: CallbackQuery):
    parts = call.data.split("_")
    user_id = int(parts[1])
    order_id = int(parts[2])

    # Получение данных заказа
    cursor.execute(
        "SELECT pack_label, quantity FROM orders WHERE id = ?",
        (order_id,)
    )
    order = cursor.fetchone()
    
    if not order:
        await call.answer("❌ Заказ не найден.", show_alert=True)
        return

    label, quantity = order

    # Получение кодов
    cursor.execute(
        "SELECT id, code FROM uc_codes WHERE label = ? AND used = 0 LIMIT ?",
        (label, quantity)
    )
    codes = cursor.fetchall()
    
    if len(codes) < quantity:
        await call.answer("❌ Недостаточно кодов в наличии.", show_alert=True)
        return

    # Обновление кодов и заказа
    code_ids = [row[0] for row in codes]
    cursor.executemany(
        "UPDATE uc_codes SET used = 1 WHERE id = ?",
        [(cid,) for cid in code_ids]
    )
    
    cursor.execute(
        "UPDATE orders SET status = 'completed' WHERE id = ?",
        (order_id,)
    )
    conn.commit()

    # Отправка кодов пользователю
    text = f"✅ Ваш платёж подтверждён!\n🎁 Ваши UC-коды ({label}):\n\n"
    text += "\n".join(f"<code>{row[1]}</code>" for row in codes)

    try:
        await bot.send_message(user_id, text)
        await call.answer("Коды отправлены пользователю ✅", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        await call.answer("❌ Не удалось отправить пользователю.", show_alert=True)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_payment(call: CallbackQuery):
    parts = call.data.split("_")
    user_id = int(parts[1])
    order_id = int(parts[2])
    
    # Обновление статуса заказа
    cursor.execute(
        "UPDATE orders SET status = 'canceled' WHERE id = ?",
        (order_id,)
    )
    conn.commit()
    
    try:
        await bot.send_message(
            user_id, 
            "❌ Ваш чек не прошёл проверку.\nЕсли вы уверены, что всё правильно — свяжитесь с @chudoo_19."
        )
        await call.answer("Отказ отправлен пользователю.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        await call.answer("❌ Не удалось отправить сообщение пользователю.")

@dp.message(UCState.waiting_for_receipt_photo)
async def invalid_receipt(message: Message):
    await message.answer("❌ Пожалуйста, отправьте именно фото чека.")

@dp.message(UCState.choosing_payment_method, F.text == "🟣 Оплата через Ю-Money")
async def payment_umoney(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity = data.get("quantity", 1)
    unit_price = data.get("unit_price", 0)
    label = data.get("label", "UC")
    total_price = quantity * unit_price
    order_id = data.get("order_id")
    user_id = message.from_user.id

    # Обновление метода оплаты в заказе
    if order_id:
        cursor.execute(
            "UPDATE orders SET payment_method = ? WHERE id = ?",
            ("yoomoney", order_id)
        )
        conn.commit()

    # Создаем кнопку для оплаты
    payment_url = "https://yoomoney.ru/quickpay/fundraise/button?billNumber=1BJ69PUJVS2.250718"
    payment_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить через ЮMoney", url=payment_url)]
        ]
    )

    payment_text = f"""
    <b>📦 Товар:</b> {label}
    <b>💰 Цена:</b> {unit_price} RUB
    <b>📦 Кол-во:</b> {quantity} шт.
    <b>💳 Итоговая сумма:</b> {total_price} RUB
    <b>⏰ Время на оплату:</b> 30 минут
    
    Нажмите кнопку ниже для оплаты:
    """

    # Отправляем сообщение с инлайн-кнопкой
    await message.answer(
        payment_text,
        reply_markup=payment_keyboard,
        parse_mode=ParseMode.HTML
    )

    # Отправляем дополнительное сообщение с инструкцией
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Я оплатил")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "После завершения оплаты нажмите кнопку ниже:",
        reply_markup=kb
    )
    await message.answer(
        f"📦 <b>Товар:</b> {label}\n"
        f"💰 <b>Цена:</b> {unit_price} RUB\n"
        f"📦 <b>Кол-во:</b> {quantity} шт.\n"
        f"🕒 <b>Время заказа:</b> {now.strftime('%Y-%m-%d %H:%M')}\n"
        f"💳 <b>Итоговая сумма:</b> {total_price} RUB\n"
        f"───────────────\n"
        f"<b>Для оплаты перейдите по ссылке:</b>\n"
        f"{payment_url}\n\n"
        f"💵 <b>Сумма оплаты:</b> {total_price} RUB\n"
        f"⏰ <b>Время на оплату:</b> 30 минут\n"
        f"⌛️ <b>Необходимо оплатить до:</b> {deadline.strftime('%H:%M')}",
        reply_markup=kb
    )

def generate_payment_url(user_id: int, amount: float, order_id: int) -> str:
    """Генерирует URL для оплаты через YooMoney"""
    base_url = "https://yoomoney.ru/quickpay/confirm.xml"
    params = {
        "receiver": YOOMONEY_WALLET,
        "quickpay-form": "shop",
        "targets": f"Оплата UC кодов (заказ #{order_id})",
        "sum": amount,
        "label": f"{user_id}_{order_id}",
        "paymentType": "AC",
        "successURL": "https://t.me/your_bot"
    }
    return f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

@dp.message(UCState.choosing_payment_method, F.text == "✅ Я оплатил")
async def wait_for_umoney_check(message: Message, state: FSMContext):
    await message.answer(
        "⏳ <b>Ожидаем подтверждение оплаты от сервера...</b>\n"
        "Вы получите сообщение автоматически, как только оплата будет подтверждена."
    )
    await state.clear()

@dp.message(F.text == "❌ Отмена")
async def cancel_any_state(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    
    if order_id:
        cursor.execute(
            "UPDATE orders SET status = 'canceled' WHERE id = ?",
            (order_id,)
        )
        conn.commit()

    await state.clear()

    kb = ReplyKeyboardBuilder()
    kb.button(text="Купить UC")
    kb.button(text="UC в наличии")
    kb.button(text="Помощь")
    kb.button(text="Профиль")
    kb.adjust(2)

    await message.answer("❌ Действие отменено. Возвращаемся в главное меню:", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text == "⬅️ Назад ко всем категориям")
async def back_to_categories(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="UC Pubg Mobile")
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text == "Помощь")
async def help_msg(message: Message):
    await message.answer("Обратитесь к @chudoo_19")

@dp.message(F.text == "Профиль")
async def profile(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        await message.answer("Вы ещё не зарегистрированы.")
        return

    cursor.execute(
        "SELECT id, pack_label, quantity, amount, status, created_at "
        "FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", 
        (user_id,)
    )
    orders = cursor.fetchall()
    
    text = (
        f"<b>👤 Профиль</b>\n"
        f"Имя: {user[2]}\n"
        f"Username: @{user[1]}\n"
        f"ID: {user[0]}\n"
        f"Дата регистрации: {user[3]}\n\n"
        f"<b>📜 Последние заказы:</b>\n"
    )
    
    if orders:
        for order_id, label, qty, price, status, date in orders:
            status_emoji = "🟢" if status == "completed" else "🟡" if status == "pending" else "🔴"
            text += f"• #{order_id}: {qty}x {label} - {price}RUB ({status_emoji} {status})\n"
    else:
        text += "Нет заказов."
    
    await message.answer(text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
