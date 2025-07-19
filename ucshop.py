import asyncio
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup

# === Настройки ===
API_TOKEN = "8024102805:AAEcu22cIkfe49UNNC_XlKB1mZMxFRx6aDk"
YOOMONEY_WALLET = "410011812000000"  # ← Укажи здесь настоящий кошелёк

# === Инициализация ===
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

conn = sqlite3.connect("users_orders.db")
cursor = conn.cursor()

# === Таблицы ===
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
    code TEXT UNIQUE,
    used INTEGER DEFAULT 0,
    order_id INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    date TEXT NOT NULL,
    payment_method TEXT,
    yoomoney_label TEXT
)
""")
conn.commit()

# === Состояния ===
class UCState(StatesGroup):
    choosing_quantity = State()
    choosing_payment_method = State()
    waiting_for_receipt_photo = State()

# === /start ===
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, username, first_name, reg_date) VALUES (?, ?, ?, ?)",
                       (user_id, message.from_user.username, message.from_user.first_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    kb = ReplyKeyboardBuilder()
    kb.button(text="Купить UC")
    kb.button(text="UC в наличии")
    kb.button(text="Помощь")
    kb.button(text="Профиль")
    kb.adjust(2)

    await state.clear()
    await message.answer(
        "⚡️Приветствуем в боте по покупке UC!\n\n"
        "Выберите действие ниже:",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message(F.text == "UC в наличии")
async def uc_stock(message: Message):
    reply = "<b>📦 UC в наличии:</b>\n"
    for label in ["60 UC", "325 UC", "385 UC", "660 UC", "720 UC", "1320 UC"]:
        cursor.execute("SELECT COUNT(*) FROM uc_codes WHERE label = ? AND used = 0", (label,))
        count = cursor.fetchone()[0]
        reply += f"• {label} — {count} шт.\n"
    await message.answer(reply)

@dp.message(F.text == "Купить UC")
async def choose_category(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="UC Pubg Mobile")
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text == "UC Pubg Mobile")
async def show_packages(message: Message):
    kb = ReplyKeyboardBuilder()
    for label, price in [("60 UC", 80), ("325 UC", 380), ("385 UC", 450), ("660 UC", 790), ("720 UC", 900), ("1320 UC", 1580)]:
        cursor.execute("SELECT COUNT(*) FROM uc_codes WHERE label = ? AND used = 0", (label,))
        count = cursor.fetchone()[0]
        kb.button(text=f"{label} | {price} RUB | {count} шт.")
    kb.button(text="⬅️ Назад ко всем категориям")
    kb.adjust(1)
    await message.answer("Категория: UC Pubg Mobile", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text.contains("UC"))
async def select_package(message: Message, state: FSMContext):
    text = message.text.split(" | ")
    if len(text) < 2:
        return
    label, price = text[0], int(text[1].split()[0])
    await state.set_state(UCState.choosing_quantity)
    await state.update_data(quantity=1, unit_price=price, label=label)
    await ask_quantity(message, 1, price, label)

async def ask_quantity(message, quantity, unit_price, label):
    total = quantity * unit_price
    kb = ReplyKeyboardBuilder()
    for i in [-5, -3, -1, 1, 3, 5]:
        kb.button(text=f"{'+' if i > 0 else ''}{i}")
    kb.adjust(3)
    kb.button(text="✅ Подтверждаю")
    kb.button(text="❌ Отмена")
    kb.adjust(2)
    await message.answer(
        f"<b>Товар:</b> {label}\n<b>Цена за шт:</b> {unit_price} RUB\n"
        f"<b>Кол-во:</b> {quantity}\n<b>Сумма:</b> {total} RUB",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message(UCState.choosing_quantity, F.text.in_({"+1", "+3", "+5", "-1", "-3", "-5"}))
async def change_quantity(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity = max(1, data.get("quantity", 1) + int(message.text))
    await state.update_data(quantity=quantity)
    await ask_quantity(message, quantity, data.get("unit_price"), data.get("label"))

@dp.message(UCState.choosing_quantity, F.text == "✅ Подтверждаю")
async def confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity = data["quantity"]
    label = data["label"]
    unit_price = data["unit_price"]
    total = quantity * unit_price
    user_id = message.from_user.id

    cursor.execute("SELECT COUNT(*) FROM uc_codes WHERE label = ? AND used = 0", (label,))
    if cursor.fetchone()[0] < quantity:
        await message.answer("❌ Недостаточно UC в наличии.")
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO orders (user_id, label, quantity, price, date) VALUES (?, ?, ?, ?, ?)",
                   (user_id, label, quantity, total, now))
    conn.commit()
    order_id = cursor.lastrowid

    await state.update_data(order_id=order_id)
    await state.set_state(UCState.choosing_payment_method)

    kb = ReplyKeyboardBuilder()
    kb.button(text="💳 Оплата переводом на карту")
    kb.button(text="🟣 Оплата через Ю-Money")
    kb.button(text="❌ Отмена")
    kb.adjust(1)

    await message.answer(
        f"📦 {quantity} x {label}\n💸 <b>К оплате:</b> {total} RUB\n\nВыберите способ оплаты:",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )

@dp.message(UCState.choosing_payment_method, F.text == "💳 Оплата переводом на карту")
async def card_payment(message: Message, state: FSMContext):
    data = await state.get_data()
    total = data["quantity"] * data["unit_price"]
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Я оплатил")], [KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )
    await message.answer(
        f"💳 Переведите <b>{total} RUB</b> на карту:\n<code>2202 2084 3750 2835</code>\n"
        f"или по СБП: <code>+79648469752</code>\n\n"
        "После перевода отправьте чек.",
        reply_markup=kb
    )
    await state.set_state(UCState.waiting_for_receipt_photo)

@dp.message(UCState.choosing_payment_method, F.text == "🟣 Оплата через Ю-Money")
async def yoomoney_payment(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    total = data["quantity"] * data["unit_price"]
    order_id = data["order_id"]
    label = f"{user_id}_{order_id}"

    cursor.execute("UPDATE orders SET yoomoney_label = ?, payment_method = ? WHERE id = ?", (label, "yoomoney", order_id))
    conn.commit()

    payment_url = (
        f"https://yoomoney.ru/quickpay/confirm.xml?"
        f"receiver={YOOMONEY_WALLET}&quickpay-form=shop&targets=UC+{order_id}&"
        f"sum={total}&label={label}&paymentType=AC&"
        f"notification_url=https://ucshop.up.railway.app/yoomoney_webhook"
    )

    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через ЮMoney", url=payment_url)]
    ])

    await message.answer("Нажмите кнопку ниже для перехода к оплате:", reply_markup=inline_kb)
    await message.answer("После оплаты нажмите «✅ Я оплатил».", reply_markup=ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Я оплатил")], [KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    ))

@dp.message(F.text == "✅ Я оплатил")
async def after_payment(message: Message, state: FSMContext):
    await message.answer("⏳ Ожидаем подтверждение оплаты... Вы получите сообщение автоматически.")
    await state.clear()

@dp.message(UCState.waiting_for_receipt_photo, F.photo)
async def photo_check(message: Message, state: FSMContext):
    ADMIN_ID = 1001953510
    photo = message.photo[-1].file_id
    user = message.from_user
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{user.id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user.id}")]
    ])
    caption = f"Чек от @{user.username or 'без username'} (ID: {user.id})"
    await bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=caption, reply_markup=kb)
    await message.answer("✅ Чек отправлен на проверку.")
    await state.clear()

@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_card(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])
    cursor.execute("SELECT label, quantity FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 1", (user_id,))
    order = cursor.fetchone()
    if not order:
        await call.answer("❌ Заказ не найден", show_alert=True)
        return
    label, quantity = order
    cursor.execute("SELECT id, code FROM uc_codes WHERE label = ? AND used = 0 LIMIT ?", (label, quantity))
    codes = cursor.fetchall()
    if len(codes) < quantity:
        await call.answer("❌ Недостаточно кодов", show_alert=True)
        return
    cursor.executemany("UPDATE uc_codes SET used = 1 WHERE id = ?", [(c[0],) for c in codes])
    conn.commit()
    text = f"✅ Ваш платёж подтверждён!\n🎁 Ваши UC-коды ({label}):\n\n"
    text += "\n".join(f"<code>{c[1]}</code>" for c in codes)
    try:
        await bot.send_message(user_id, text)
        await call.answer("Коды отправлены ✅", show_alert=True)
    except:
        await call.answer("❌ Ошибка отправки", show_alert=True)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_card(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])
    try:
        await bot.send_message(user_id, "❌ Ваш платёж не подтверждён. Свяжитесь с @chudoo_19.")
        await call.answer("Отклонено", show_alert=True)
    except:
        await call.answer("Ошибка", show_alert=True)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
