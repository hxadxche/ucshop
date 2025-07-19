
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
    CREATE TABLE IF NOT EXISTS uc_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT,
        code TEXT,
        used INTEGER DEFAULT 0
    )
""")
conn.commit()
sample_data = [
    ("60 UC", "60CODE1"), ("60 UC", "60CODE2"),("60 UC", "60CODE3"),("60 UC", "60CODE4"),("60 UC", "60CODE5"),
    ("325 UC", "325CODE1"), ("325 UC", "325CODE2"),("325 UC", "325CODE3"), ("325 UC", "325CODE4"),
    ("385 UC", "385CODE1"), ("385 UC", "385CODE2"),("385 UC", "385CODE3"), ("385 UC", "385CODE4"),
    ("660 UC", "660CODE1"), ("660 UC", "660CODE2"),("660 UC", "660CODE3"), ("660 UC", "660CODE4"),
    ("720 UC", "720CODE1"), ("720 UC", "720CODE2"),("720 UC", "720CODE3"), ("720 UC", "720CODE4"),
    ("1320 UC", "1320CODE1"), ("1320 UC", "1320CODE2"),("1320 UC", "1320CODE3"), ("1320 UC", "1320CODE4"),
]
# Очищаем старые данные (если были)
#cursor.execute("DELETE FROM uc_codes")

# Вставляем новые
for label, code in sample_data:
    cursor.execute("INSERT INTO uc_codes (label, code) VALUES (?, ?)", (label, code))

conn.commit()

# Покажем все доступные коды
cursor.execute("SELECT label, code FROM uc_codes WHERE used = 0 ORDER BY id")
available_codes = cursor.fetchall()
available_codes
conn.commit()

sample_data = [
    ("60 UC", "60CODE1"), ("60 UC", "60CODE2"),("60 UC", "60CODE3"),("60 UC", "60CODE4"),("60 UC", "60CODE5"),
    ("325 UC", "325CODE1"), ("325 UC", "325CODE2"),("325 UC", "325CODE3"), ("325 UC", "325CODE4"),
    ("385 UC", "385CODE1"), ("385 UC", "385CODE2"),("385 UC", "385CODE3"), ("385 UC", "385CODE4"),
    ("660 UC", "660CODE1"), ("660 UC", "660CODE2"),("660 UC", "660CODE3"), ("660 UC", "660CODE4"),
    ("720 UC", "720CODE1"), ("720 UC", "720CODE2"),("720 UC", "720CODE3"), ("720 UC", "720CODE4"),
    ("1320 UC", "1320CODE1"), ("1320 UC", "1320CODE2"),("1320 UC", "1320CODE3"), ("1320 UC", "1320CODE4"),

]
cursor.execute("SELECT COUNT(*) FROM uc_codes")
if cursor.fetchone()[0] == 0:
    for label, code in sample_data:
        cursor.execute("INSERT INTO uc_codes (label, code) VALUES (?, ?)", (label, code))
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
    def register_handler(lbl, prc):
        @dp.message(F.text.startswith(lbl))
        async def handle(message: Message, state: FSMContext):
            await handle_uc_package(message, state, lbl, prc)
    register_handler(label, price)


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

    # ─── ПРОВЕРКА НАЛИЧИЯ ─────────────────────────────────
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
    # ────────────────────────────────────────────────────
    # ——— Сохранить заказ в БД с правильным количеством ———
    user_id = message.from_user.id
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO orders (user_id, label, quantity, price, date) VALUES (?, ?, ?, ?, ?)",
        (user_id, label, quantity, total_price, now_str)
    )
    conn.commit()
    # ————————————————————————————————————————————————

    # если всё ок — показываем способы оплаты
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

@dp.message(UCState.choosing_payment_method, F.text == "🟣 Оплата через Ю-Money")
async def payment_umoney(message: Message, state: FSMContext):
    data = await state.get_data()
    print(f"[DEBUG] Payment state data: {data}")
    label = data.get("label", "UC")
    unit_price = data.get("unit_price", 0)
    quantity = data.get("quantity", 1)
    total_price = quantity * unit_price
    now = datetime.now()

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

@dp.message(F.text == "Я оплатил")
async def handle_payment_confirmation(message: Message, state: FSMContext):
    await message.answer("📸 Пожалуйста, отправьте фото чека (скриншот подтверждения перевода).")
    await state.set_state(UCState.waiting_for_receipt_photo)

@dp.message(UCState.waiting_for_receipt_photo, F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext):
    ADMIN_ID = 1001953510
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
    user_id = int(call.data.split("_")[1])

    # 1) Достанем из orders последний созданный заказ для этого пользователя
    cursor.execute(
        "SELECT label, quantity FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 1",
        (user_id,)
    )
    order = cursor.fetchone()
    if not order:
        await call.answer("❌ Заказ не найден.", show_alert=True)
        return

    label, quantity = order

    # 2) Выбираем ровно столько кодов нужного пакета
    cursor.execute(
        "SELECT id, code FROM uc_codes WHERE label = ? AND used = 0 LIMIT ?",
        (label, quantity)
    )
    codes = cursor.fetchall()
    if len(codes) < quantity:
        await call.answer("❌ Недостаточно кодов в наличии.", show_alert=True)
        return

    # 3) Помечаем их как использованные
    code_ids = [row[0] for row in codes]
    cursor.executemany(
        "UPDATE uc_codes SET used = 1 WHERE id = ?",
        [(cid,) for cid in code_ids]
    )
    conn.commit()

    # 4) Отправляем пользователю _именно_ эти коды
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
        await bot.send_message(user_id, "❌ Ваш чек не прошёл проверку.\nЕсли вы уверены, что всё правильно — свяжитесь с @chudoo_19.")
        await call.answer("Отказ отправлен пользователю.", show_alert=True)
    except:
        await call.answer("❌ Не удалось отправить сообщение пользователю.")

@dp.message(UCState.waiting_for_receipt_photo)
async def invalid_receipt(message: Message):
    await message.answer("❌ Пожалуйста, отправьте именно фото чека.")

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

@dp.message(UCState.choosing_payment_method, F.text == "🟣 Оплата через Ю-Money")
async def payment_umoney(message: Message, state: FSMContext):
    data = await state.get_data()
    quantity = data.get("quantity", 1)
    unit_price = data.get("unit_price", 0)
    label = data.get("label", "UC")
    total_price = quantity * unit_price
    order_id = data.get("order_id")
    user_id = message.from_user.id
    now = datetime.now()
    deadline = now + timedelta(minutes=30)

    # Сохраняем уникальный label для webhook
    if order_id:
        yoomoney_label = f"{user_id}_{order_id}"
        cursor.execute(
            "UPDATE orders SET payment_method = ?, yoomoney_label = ? WHERE id = ?",
            ("yoomoney", yoomoney_label, order_id))
        conn.commit()
    else:
        await message.answer("❌ Ошибка при создании заказа.")
        return

    # Ссылка на оплату с webhook URL
    payment_url = (
        f"https://yoomoney.ru/quickpay/confirm.xml?"
        f"receiver={YOOMONEY_WALLET}&"
        f"quickpay-form=shop&"
        f"targets=Оплата UC кодов (заказ #{order_id})&"
        f"sum={total_price}&"
        f"label={yoomoney_label}&"
        f"notification_url=https://ucshop.up.railway.app/yoomoney_webhook&"
        f"paymentType=AC"
    )

    # Кнопка на оплату
    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через ЮMoney", url=payment_url)]
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

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Я оплатил")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"⌛️ <b>Необходимо оплатить до:</b> {deadline.strftime('%H:%M')}\n"
        "После оплаты нажмите «✅ Я оплатил» и дождитесь автоматической проверки.",
        reply_markup=kb
    )

    await state.set_state(UCState.choosing_payment_method)


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

    cursor.execute("SELECT label, quantity, price, date FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 5", (user_id,))
    orders = cursor.fetchall()
    text = (
        f"<b>👤 Профиль</b>\nИмя: {user[2]}\nUsername: @{user[1]}\nID: {user[0]}\nДата регистрации: {user[3]}\n\n"
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
