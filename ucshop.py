import asyncio
import sqlite3
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
# Твой ЮMoney кошелек (замени на свой номер)
YOOMONEY_WALLET = "4100111899459093"

# === SQLite ===
conn = sqlite3.connect("users_orders.db")
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE orders ADD COLUMN yoomoney_label TEXT UNIQUE")
    conn.commit()
except sqlite3.OperationalError:
    # Колонка уже есть — игнорируем ошибку
    pass

# Пользователи
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        reg_date TEXT
    )
""")

# UC-коды
cursor.execute("""
    CREATE TABLE IF NOT EXISTS uc_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT,
        code TEXT UNIQUE,
        used INTEGER DEFAULT 0,
        order_id INTEGER
    )
""")

# Заказы (исправлено: pack_label → label, amount → price для согласованности)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        label TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        status TEXT DEFAULT 'pending' CHECK(status IN ('pending','completed','cancelled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        yoomoney_label TEXT UNIQUE
    )
""")
conn.commit()
# После создания таблиц


# Добавление UC-кодов, только если их ещё нет
cursor.execute("SELECT COUNT(*) FROM uc_codes")
if cursor.fetchone()[0] == 0:
    sample_data = [
        ("60 UC", "60CODE1"), ("60 UC", "60CODE2"), ("60 UC", "60CODE3"), ("60 UC", "60CODE4"), ("60 UC", "60CODE5"),
        ("325 UC", "325CODE1"), ("325 UC", "325CODE2"), ("325 UC", "325CODE3"), ("325 UC", "325CODE4"),
        ("385 UC", "385CODE1"), ("385 UC", "385CODE2"), ("385 UC", "385CODE3"), ("385 UC", "385CODE4"),
        ("660 UC", "660CODE1"), ("660 UC", "660CODE2"), ("660 UC", "660CODE3"), ("660 UC", "660CODE4"),
        ("720 UC", "720CODE1"), ("720 UC", "720CODE2"), ("720 UC", "720CODE3"), ("720 UC", "720CODE4"),
        ("1320 UC", "1320CODE1"), ("1320 UC", "1320CODE2"), ("1320 UC", "1320CODE3"), ("1320 UC", "1320CODE4"),
    ]
    for label, code in sample_data:
        cursor.execute("INSERT OR IGNORE INTO uc_codes (label, code) VALUES (?, ?)", (label, code))
    conn.commit()

# === Bot config ===
API_TOKEN = "8024102805:AAEcu22cIkfe49UNNC_XlKB1mZMxFRx6aDk"
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# === Состояния ===
class UCState(StatesGroup):
    choosing_quantity = State()
    choosing_payment_method = State()
    waiting_for_receipt_photo = State()
    waiting_for_umoney_payment = State()
  

# === Команда /start ===
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO users (user_id, username, first_name, reg_date) VALUES (?, ?, ?, ?)",
            (
                user_id,
                message.from_user.username,
                message.from_user.first_name,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
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
    for label, price in [("60 UC", 80), ("325 UC", 380), ("385 UC", 450), ("660 UC", 790), ("720 UC", 900), ("1320 UC", 1580)]:
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

uc_packages = [("60 UC", 80), ("325 UC", 380), ("385 UC", 450), ("660 UC", 790), ("720 UC", 900), ("1320 UC", 1580)]

for label, price in uc_packages:
    @dp.message(F.text.startswith(label))
    async def handle(message: Message, state: FSMContext, lbl=label, prc=price):
        await handle_uc_package(message, state, lbl, prc)


@dp.message(UCState.choosing_quantity, F.text.in_({"+1", "+3", "+5", "-1", "-3", "-5"}))
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

    # Проверка наличия
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
            f"Вы выбрали: {quantity}, доступно: {available}.",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )
        return

        # Сохраняем заказ
    user_id = message.from_user.id
    cursor.execute(
    "INSERT INTO orders (user_id, label, quantity, price) VALUES (?, ?, ?, ?)",
    (user_id, label, quantity, total_price)
)

    conn.commit()
    # Получаем ID последнего заказа
    order_id = cursor.lastrowid

    # Сохраняем в состояние
    await state.update_data(order_id=order_id)

    # Выбор способа оплаты
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
async def payment_by_card(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity = data.get("quantity", 1)
    unit_price = data.get("unit_price", 0)
    label = data.get("label", "UC")
    total_price = quantity * unit_price
    now = datetime.now()

    await message.answer(
        f"📦 <b>Товар:</b> {label}\n"
        f"💰 <b>Цена за штуку:</b> {unit_price} RUB\n"
        f"📦 <b>Количество:</b> {quantity} шт.\n"
        f"💸 <b>Итого к оплате:</b> {total_price} RUB\n"
        f"⏰ <b>Время:</b> {now.strftime('%H:%M')}\n\n"
        f"💳 <b>Реквизиты для оплаты:</b>\n"
        f"<code>2202 2084 3750 2835</code> (СБП)\n"
        f"<code>+79648469752</code> (Альфа Банк)\n\n"
        f"<b>❗️ Обязательно отправьте фото чека после оплаты</b>."
    )

    # Клавиатура для подтверждения оплаты
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Я оплатил")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

    await message.answer("После оплаты нажмите «✅ Я оплатил» и отправьте фото чека.", reply_markup=kb)




@dp.message(F.text == "✅ Я оплатил")
async def handle_payment_confirmation(message: Message, state: FSMContext):
    # Отправляем сообщение, что пользователь оплатил
    await message.answer("💳 Вы подтвердили оплату! Пожалуйста, отправьте фото чека (скриншот подтверждения перевода).")

    # Переходим в состояние ожидания фото
    await state.set_state(UCState.waiting_for_receipt_photo)



@dp.message(UCState.waiting_for_receipt_photo, F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext):
    # Проверка, что фотография есть
    photo = message.photo[-1] if message.photo else None
    if not photo:
        await message.answer("❌ Пожалуйста, отправьте фото чека.")
        return

    ADMIN_ID = 1001953510  # Твой ID
    user = message.from_user
    caption = (
        f"📩 Новый платёж по карте!\n\n"
        f"👤 Пользователь: @{user.username or 'без username'}\n"
        f"🆔 ID: {user.id}\n"
        f"👁 Имя: {user.first_name}\n\n"
        f"🧾 Проверьте чек:"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждено", callback_data=f"confirm_{user.id}")],
        [InlineKeyboardButton(text="❌ Отказ", callback_data=f"reject_{user.id}")]
    ])

    # Отправляем фото администратору
    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo.file_id,  # Фото чека
        caption=caption,
        reply_markup=keyboard
    )

    # Сообщаем пользователю, что чек отправлен на проверку
    await message.answer("✅ Чек отправлен администратору на проверку. Мы сообщим, как только он подтвердит оплату.")

    # Очищаем состояние
    await state.clear()



@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])

    # Получаем последний заказ
    cursor.execute(
    "SELECT label, quantity FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 1",
    (user_id,)
)
    order = cursor.fetchone()
    if not order:
        await call.answer("❌ Заказ не найден.", show_alert=True)
        return

    label, quantity = order

    # Ищем доступные коды
    cursor.execute(
        "SELECT id, code FROM uc_codes WHERE label = ? AND used = 0 LIMIT ?",
        (label, quantity)
    )
    codes = cursor.fetchall()
    if len(codes) < quantity:
        await call.answer("❌ Недостаточно кодов в наличии.", show_alert=True)
        return

    # Отмечаем коды как использованные
    code_ids = [row[0] for row in codes]
    cursor.executemany("UPDATE uc_codes SET used = 1 WHERE id = ?", [(cid,) for cid in code_ids])
    conn.commit()

    # Отправка кодов пользователю
    text = f"✅ Ваш платёж подтверждён!\n🎁 Ваши UC-коды ({label}):\n\n"
    text += "\n".join(f"<code>{row[1]}</code>" for row in codes)

    try:
        await bot.send_message(user_id, text)
        await call.answer("Коды отправлены пользователю ✅", show_alert=True)
    except:
        await call.answer("❌ Не удалось отправить пользователю.", show_alert=True)



@dp.callback_query(F.data.startswith("reject_"))
async def reject_payment(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])
    try:
        await bot.send_message(
            user_id,
            "❌ Ваш чек не прошёл проверку.\nЕсли вы уверены, что всё правильно — свяжитесь с @chudoo_19."
        )
        await call.answer("Отказ отправлен пользователю.", show_alert=True)
    except:
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

    if not order_id:
        await message.answer("❌ Ошибка при создании заказа.")
        return

    # Уникальный label с таймштампом, чтобы избежать кэша
    yoomoney_label = f"{user_id}_{order_id}_{int(datetime.now().timestamp())}"

    # Обновляем в базе
    cursor.execute(
        "UPDATE orders SET yoomoney_label = ? WHERE id = ?",
        (yoomoney_label, order_id)
    )
    conn.commit()

    # Генерация ссылки на оплату
    payment_url = (
    f"https://yoomoney.ru/quickpay/confirm?"
    f"receiver={YOOMONEY_WALLET}&"
    f"quickpay-form=shop&"
    f"targets=Покупка UC-кодов (заказ #{order_id})&"
    f"sum={total_price}&"
    f"label={user_id}_{order_id}&"
    f"paymentType=AC"
    )


    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через ЮMoney", url=payment_url)],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order")]
    ])

    await message.answer(
        f"<b>📦 Товар:</b> {label}\n"
        f"<b>💰 Цена за единицу:</b> {unit_price} RUB\n"
        f"<b>📦 Количество:</b> {quantity} шт.\n"
        f"<b>💸 Итоговая сумма:</b> {total_price} RUB\n"
        f"<b>⏰ Время на оплату:</b> 30 минут\n\n"
        f"Нажмите кнопку ниже для оплаты:",
        reply_markup=pay_kb
    )

    await state.set_state(UCState.waiting_for_umoney_payment)





@dp.message(UCState.choosing_payment_method, F.text == "✅ Я оплатил")
async def wait_for_umoney_check(message: Message, state: FSMContext):
    await message.answer(
        "⏳ <b>Ожидаем подтверждение оплаты от сервера...</b>\n"
        "Вы получите сообщение автоматически, как только оплата будет подтверждена."
    )
    await state.clear()


@dp.message(F.text == "❌ Отмена")
async def cancel_any_state(message: Message, state: FSMContext):
    await state.clear()

    kb = ReplyKeyboardBuilder()
    kb.button(text="Купить UC")
    kb.button(text="UC в наличии")
    kb.button(text="Помощь")
    kb.button(text="Профиль")
    kb.adjust(2)

    await message.answer("❌ Действие отменено. Возвращаемся в главное меню:",
                         reply_markup=kb.as_markup(resize_keyboard=True))


@dp.message(F.text == "⬅️ Назад ко всем категориям")
async def back_to_categories(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="UC Pubg Mobile")
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup(resize_keyboard=True))


@dp.message(F.text == "Помощь")
async def help_msg(message: Message):
    await message.answer("ℹ️ По всем вопросам обращайтесь: @chudoo_19")


@dp.message(F.text == "Профиль")
async def profile(message: Message):
    user_id = message.from_user.id
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        await message.answer("Вы ещё не зарегистрированы.")
        return

    cursor.execute(
        "SELECT pack_label, quantity, amount, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
        (user_id,))
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
        for label, qty, price, date in orders:
            text += f"• {qty} x {label} — {price} RUB ({date})\n"
    else:
        text += "Нет заказов."

    await message.answer(text)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
