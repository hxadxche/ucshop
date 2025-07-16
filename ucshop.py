import asyncio
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup

# === SQLite ===
conn = sqlite3.connect("users_orders.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        reg_date TEXT
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        label TEXT,
        quantity INTEGER,
        price INTEGER,
        date TEXT
    )
""")
conn.commit()

# === Bot config ===
API_TOKEN = "8024102805:AAEcu22cIkfe49UNNC_XlKB1mZMxFRx6aDk"
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


class UCState(StatesGroup):
    choosing_quantity = State()


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


@dp.message(F.text == "Купить UC")
async def show_categories(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="UC Pubg Mobile")
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup(resize_keyboard=True))


@dp.message(F.text == "UC в наличии")
async def uc_in_stock(message: Message):
    stock_info = (
        "<b>📦 UC в наличии:</b>\n\n"
        "• 60 UC — 38 шт.\n"
        "• 325 UC — 17 шт.\n"
        "• 385 UC — 12 шт.\n"
        "• 660 UC — 9 шт.\n"
        "• 720 UC — 6 шт.\n"
        "• 1320 UC — 3 шт.\n"
    )
    await message.answer(stock_info)


@dp.message(F.text == "Помощь")
async def help_message(message: Message):
    await message.answer("ℹ️ Для оказания помощи по боту обращайтесь к: @chudoo_19")


@dp.message(F.text == "Профиль")
async def profile(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        await message.answer("Вы ещё не зарегистрированы.")
        return

    cursor.execute("SELECT label, quantity, price, date FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 5", (user_id,))
    orders = cursor.fetchall()
    text = (
        f"<b>👤 Профиль</b>\n"
        f"Имя: {user[2]}\n"
        f"Username: @{user[1] if user[1] else 'не указано'}\n"
        f"ID: {user[0]}\n"
        f"Дата регистрации: {user[3]}\n\n"
        f"<b>📜 Последние заказы:</b>\n"
    )
    if orders:
        for label, qty, price, date in orders:
            text += f"• {qty} x {label} — {price} RUB ({date})\n"
    else:
        text += "Нет заказов."

    await message.answer(text)


@dp.message(F.text == "UC Pubg Mobile")
async def show_uc_packages(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="60 UC | 80 RUB | 38 шт.")
    kb.button(text="325 UC | 380 RUB | 17 шт.")
    kb.button(text="385 UC | 450 RUB | 12 шт.")
    kb.button(text="660 UC | 790 RUB | 9 шт.")
    kb.button(text="720 UC | 900 RUB | 6 шт.")
    kb.button(text="1320 UC | 1580 RUB | 3 шт.")
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


# === Генерация обработчиков пакетов ===
async def handle_uc_package(message: Message, state: FSMContext, label: str, unit_price: int):
    await state.set_state(UCState.choosing_quantity)
    await state.update_data(quantity=1, unit_price=unit_price, label=label)
    await send_quantity_menu(message, 1, unit_price, label)


for label, price in [
    ("60 UC", 80),
    ("325 UC", 380),
    ("385 UC", 450),
    ("660 UC", 790),
    ("720 UC", 900),
    ("1320 UC", 1580),
]:
    @dp.message(F.text.startswith(label))
    async def _(message: Message, state: FSMContext, l=label, p=price):
        await handle_uc_package(message, state, l, p)


@dp.message(UCState.choosing_quantity, F.text.in_({"+1", "+3", "+5", "-1", "-3", "-5"}))
async def change_quantity(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity = data.get("quantity", 1)
    unit_price = data.get("unit_price", 0)
    label = data.get("label", "UC")

    try:
        delta = int(message.text)
        quantity = max(1, quantity + delta)
        await state.update_data(quantity=quantity)
        await send_quantity_menu(message, quantity, unit_price, label)
    except ValueError:
        await message.answer("Неверный формат")


@dp.message(UCState.choosing_quantity, F.text == "✅ Подтверждаю")
async def confirm_order(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    quantity = data.get("quantity", 1)
    unit_price = data.get("unit_price", 0)
    label = data.get("label", "UC")
    price = quantity * unit_price
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # сохраняем заказ
    cursor.execute(
        "INSERT INTO orders (user_id, label, quantity, price, date) VALUES (?, ?, ?, ?, ?)",
        (user_id, label, quantity, price, date)
    )
    conn.commit()

    await message.answer(
        f"Вы выбрали {quantity} шт. {label} (общая цена: {price} RUB)\n"
        "Далее реализуем оплату и активацию..."
    )
    await state.clear()


@dp.message(UCState.choosing_quantity, F.text == "❌ Отмена")
async def cancel_order(message: Message, state: FSMContext):
    await state.clear()
    kb = ReplyKeyboardBuilder()
    kb.button(text="Купить UC")
    kb.button(text="UC в наличии")
    kb.button(text="Помощь")
    kb.button(text="Профиль")
    kb.adjust(2)
    await message.answer("Вы вернулись в главное меню", reply_markup=kb.as_markup(resize_keyboard=True))


@dp.message(UCState.choosing_quantity, F.text == "🔙 Назад")
async def back_to_package_list(message: Message):
    await show_uc_packages(message)


@dp.message(F.text == "⬅️ Назад ко всем категориям")
async def back_to_categories(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="UC Pubg Mobile")
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup(resize_keyboard=True))


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
