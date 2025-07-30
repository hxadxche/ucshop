import asyncpg
import asyncio
from datetime import datetime, timedelta
from yoomoney import Quickpay
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from functools import partial
import requests
from aiogram.types import ReplyKeyboardRemove
from aiogram.filters import Command
admin_router = Router()
API_URL = "https://synet.syntex-dev.ru/redeem"
API_TOKEN = "7712356486de523a"  # замените на свой

DB_CONFIG = {
    'user': 'postgres',
    'password': 'xRbtSljvnJweJPlmYvjbiCdvbqYequqF',
    'database': 'railway',
    'host': 'postgres.railway.internal',
    'port': '5432',
}

_pg_pool = None  # глобальная переменная

async def get_pg_pool():
    global _pg_pool  # СНАЧАЛА объявляем global — потом используем
    if _pg_pool is None:
        print("⏳ Подключение к PostgreSQL...")
        _pg_pool = await asyncpg.create_pool(
            **DB_CONFIG,
            min_size=1,
            max_size=5,
            max_inactive_connection_lifetime=60,
            max_queries=50000
        )
        print("✅ Подключено к PostgreSQL.")
    return _pg_pool





async def execute(query, *args):
    print("📥 Получаем соединение из пула...")
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(query, *args)

async def fetchrow(query, *args):
    print("📥 Получаем соединение из пула...")
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await conn.fetchrow(query, *args)

async def fetchall(query, *args):
    print("📥 Получаем соединение из пула...")
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await conn.fetch(query, *args)
async def fetchval(query, *args):
    print("📥 Получаем соединение из пула...")
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            return await conn.fetchval(query, *args)
async def init_db():
    print("🔗 Проверка подключения к базе...")
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute("SELECT 1")  # просто проверка соединения

def activate_uc_code(player_id, code):
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "codeType": "UC",
        "playerId": str(player_id),
        "code": code
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                return True, f"✅ UC-код успешно активирован для ID {player_id}"
            else:
                return False, f"⚠️ Не удалось активировать код: {data.get('message')}"
        else:
            return False, f"❌ Ошибка {response.status_code}: {response.text}"
    except Exception as e:
        return False, f"🚫 Ошибка подключения к API: {str(e)}"


main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Купить UC"), KeyboardButton(text="UC в наличии")],
        [KeyboardButton(text="Помощь"), KeyboardButton(text="Профиль")]
    ],
    resize_keyboard=True
)

# === Состояния ===
YOOMONEY_WALLET = "4100111899459093"

# === Bot config ===
BOT_TOKEN = "7587423228:AAHhVNFsKeWo8ck7xdDL1U8NHzTFsqDgZBE"
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(admin_router)

class UCState(StatesGroup):
    choosing_quantity = State()
    choosing_payment_method = State()
    waiting_for_receipt_photo = State()
    waiting_for_umoney_payment = State()
    entering_pubg_id = State()
class AdminState(StatesGroup):
    waiting_for_code = State()

# === Команда /start ===
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

    if user is None:
        await execute(
            "INSERT INTO users (user_id, username, first_name, reg_date) VALUES ($1, $2, $3, $4)",
            user_id,
            message.from_user.username,
            message.from_user.first_name,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

    result = await fetchrow("SELECT pubg_id FROM users WHERE user_id = $1", user_id)
    if not result or not result['pubg_id']:
        await state.set_state(UCState.entering_pubg_id)

        await message.answer(
            "⚠️ <b>Важно:</b> Пожалуйста, убедитесь, что вы правильно ввели свой PUBG ID.\n"
            "Если ID указан неверно, код может быть активирован на другой аккаунт.\n"
            "❗ Ответственность за неверный ID несёт покупатель.",
            parse_mode="HTML"
        )
        await message.answer("👤 Пожалуйста, отправьте свой PUBG ID, чтобы продолжить.")
        return

    await state.clear()
    await message.answer(
        "⚡️Приветствуем тебя в автоматическом боте покупки UC кодов 🔥\n\n"
        "Официальная группа: https://t.me/CHUDO_UC_SHOP\n\n"
        "Бот работает 24/7 с паками от 60 UC\n\n"
        "Если возникнут какие-то вопросы: @chudoo_19",
        reply_markup=main_menu_kb
    )


@dp.message(F.text == "UC в наличии")
async def uc_in_stock(message: Message):
    stock_info = "<b>📦 UC в наличии:</b>\n\n"
    for label in ["60 UC", "325 UC", "660 UC", "1800 UC", "3850 UC", "8100 UC"]:
        count = await fetchval(
            "SELECT COUNT(*) FROM uc_codes WHERE label = $1 AND used = FALSE",
            label
        )
        stock_info += f"• {label} — {count} шт.\n"
    await message.answer(stock_info)


@dp.message(F.text == "Купить UC")
async def show_categories(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="UC Pubg Mobile")
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup(resize_keyboard=True))


@dp.message(UCState.entering_pubg_id)
async def handle_pubg_id(message: Message, state: FSMContext):
    pubg_id = message.text.strip()
    user_id = message.from_user.id

    await execute(
        "UPDATE users SET pubg_id = $1 WHERE user_id = $2",
        pubg_id, user_id
    )

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


@dp.message(F.text == "UC Pubg Mobile")
async def show_uc_packages(message: Message):
    kb = ReplyKeyboardBuilder()
    for label, price in [("60 UC", 2), ("325 UC", 390), ("660 UC", 800),
                         ("1800 UC", 2050), ("3850 UC", 4000), ("8100 UC", 7700)]:
        count = await fetchval(
            "SELECT COUNT(*) FROM uc_codes WHERE label = $1 AND used = FALSE",
            label
        )
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


uc_packages = [("60 UC", 2), ("325 UC", 390), ("660 UC", 800),
               ("1800 UC", 2050), ("3850 UC", 4000), ("8100 UC", 7700)]

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
    quantity    = data["quantity"]
    unit_price  = data["unit_price"]
    label       = data["label"]
    total_price = quantity * unit_price

    # проверим наличие
    available = await fetchval(
        "SELECT COUNT(*) FROM uc_codes WHERE label = $1 AND used = FALSE",
        label
    )

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

    user_id = message.from_user.id
    row = await fetchrow(
        """
        INSERT INTO orders (user_id, label, quantity, price)
        VALUES ($1, $2, $3, $4)
        RETURNING id
        """,
        user_id, label, quantity, total_price
    )
    order_id = row["id"]

    await state.update_data(order_id=order_id)

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
    await message.answer("💳 Вы подтвердили оплату! Пожалуйста, отправьте фото чека (скриншот подтверждения перевода).")
    await state.set_state(UCState.waiting_for_receipt_photo)


@dp.message(UCState.waiting_for_receipt_photo, F.photo)
async def handle_receipt_photo(message: Message, state: FSMContext):
    photo = message.photo[-1] if message.photo else None
    if not photo:
        await message.answer("❌ Пожалуйста, отправьте фото чека.")
        return

    ADMIN_IDS = [1073756996, 1001953510, 1349751236]
    user = message.from_user

    try:
        await message.bot.edit_message_reply_markup(
            chat_id=message.chat.id,
            message_id=message.message_id - 1,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[])
        )
    except Exception as e:
        print(f"❗ Не удалось удалить клавиатуру: {e}")

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

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=caption,
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"❗ Не удалось отправить фото админу {admin_id}: {e}")

    await message.answer("✅ Чек отправлен администратору на проверку. Мы сообщим, как только он подтвердит оплату.")
    await state.clear()


@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_payment(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])
    order = await fetchrow(
        "SELECT id, label, quantity FROM orders WHERE user_id = $1 AND status = 'pending' ORDER BY id DESC LIMIT 1",
        user_id
    )

    if not order:
        await call.answer("❌ Заказ не найден.", show_alert=True)
        return

    order_id = order['id']
    label = order['label']
    quantity = order['quantity']

    codes = await fetchall(
        "SELECT id, code FROM uc_codes WHERE label = $1 AND used = FALSE LIMIT $2",
        label, quantity
    )

    if len(codes) < quantity:
        await call.answer("❌ Недостаточно кодов в наличии.", show_alert=True)
        return

    try:
        for code in codes:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Активировать через бота",
                                      callback_data=f"activate:{code['code']}:{user_id}")],
                [InlineKeyboardButton(text="🌐 Открыть Midasbuy",
                                      url="https://www.midasbuy.com/midasbuy/ru/redeem/pubgm")]
            ])

            await bot.send_message(
                chat_id=user_id,
                text=f"🎁 Ваш UC-код ({label}):\n\n<code>{code['code']}</code>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            await execute(
                "UPDATE uc_codes SET used = TRUE WHERE id = $1",
                code['id']
            )

        await execute(
            "UPDATE orders SET status = 'completed' WHERE id = $1",
            order_id
        )

        admin_msg = (
                f"📤 Выданы коды:\n"
                f"👤 Пользователь: <code>{user_id}</code>\n"
                f"💳 Способ: КАРТА\n"
                f"🏷 Пакет: {label}\n"
                f"🔢 Кол-во: {quantity}\n"
                f"🎁 Коды:\n" + "\n".join(f"<code>{code['code']}</code>" for code in codes)
        )

        ADMIN_IDS = [1073756996, 1001953510, 1349751236]
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_msg, parse_mode="HTML")
            except Exception as e:
                print(f"❌ Не удалось отправить админу: {e}")

        kb = ReplyKeyboardBuilder()
        kb.button(text="Купить UC")
        kb.button(text="UC в наличии")
        kb.button(text="Помощь")
        kb.button(text="Профиль")
        kb.adjust(2)

        await bot.send_message(
            chat_id=user_id,
            text="📲 Возвращаю вас в главное меню. Выберите действие:",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )

        await call.answer("Коды отправлены пользователю ✅", show_alert=True)

    except Exception as e:
        print(f"❌ Ошибка при выдаче кодов: {e}")
        await call.answer("❗️ Не удалось отправить коды.", show_alert=True)


@dp.callback_query(F.data.startswith("activate:"))
async def handle_activation_callback(callback_query: CallbackQuery):
    await callback_query.answer()
    _, code, user_id = callback_query.data.split(":")
    user_id = int(user_id)

    result = await fetchrow(
        "SELECT pubg_id FROM users WHERE user_id = $1",
        user_id
    )

    if result and result['pubg_id']:
        player_id = result['pubg_id']
        success, msg = activate_uc_code(player_id, code)
    else:
        msg = "❌ PUBG ID не найден. Активация невозможна."

    await bot.send_message(callback_query.from_user.id, msg)


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

    yoomoney_label = f"{user_id}_{order_id}_{int(datetime.now().timestamp())}"

    await execute(
        "UPDATE orders SET yoomoney_label = $1 WHERE id = $2",
        yoomoney_label, order_id
    )

    quickpay = Quickpay(
        receiver="4100111899459093",
        quickpay_form="shop",
        targets="Sponsor this project",
        paymentType="AB",
        sum=total_price,
        label=yoomoney_label
    )

    pay_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить через ЮMoney", url=quickpay.redirected_url)],
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
    await message.answer("❌ Действие отменено. Возвращаемся в главное меню:",
                         reply_markup=main_menu_kb)


@dp.message(F.text == "⬅️ Назад ко всем категориям")
async def back_to_categories(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text="UC Pubg Mobile")
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup(resize_keyboard=True))

@admin_router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in [1001953510]:  # 🔁 Добавь своих админов
        await message.answer("❌ У тебя нет доступа.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить код", callback_data="admin_add_code")],
        [InlineKeyboardButton(text="➖ Удалить код", callback_data="admin_delete_code")],
        [InlineKeyboardButton(text="📋 Все коды", callback_data="admin_list_codes")],
        [InlineKeyboardButton(text="✅ Активные заказы", callback_data="admin_active_orders")],
        [InlineKeyboardButton(text="🔍 Поиск заказа по ID", callback_data="admin_search_order")],
        [InlineKeyboardButton(text="👤 Все пользователи", callback_data="admin_all_users")],
        [InlineKeyboardButton(text="🧹 Удалить пользователя", callback_data="admin_delete_user")]
    ])
@admin_router.callback_query(F.data == "admin_add_code")
async def handle_add_code_callback(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("🔧 Введите код, который хотите добавить:")
    # Здесь потом FSM → add_code_state

@admin_router.callback_query(F.data == "admin_delete_code")
async def handle_delete_code_callback(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("🧹 Введите код, который хотите удалить:")
    # FSM → delete_code_state

@admin_router.callback_query(F.data == "admin_list_codes")
async def handle_list_codes_callback(callback_query: CallbackQuery):
    await callback_query.message.answer("📋 Здесь будут отображены все коды.")
    # Тут в будущем — SELECT из базы и вывод в сообщении

@admin_router.callback_query(F.data == "admin_active_orders")
async def handle_active_orders_callback(callback_query: CallbackQuery):
    await callback_query.message.answer("📦 Здесь будут активные (pending) заказы.")
    # SELECT * FROM orders WHERE status = 'pending'

@admin_router.callback_query(F.data == "admin_search_order")
async def handle_search_order_callback(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("🔍 Введите ID пользователя или order_id для поиска заказа:")
    # FSM → search_order_state

@admin_router.callback_query(F.data == "admin_all_users")
async def handle_all_users_callback(callback_query: CallbackQuery):
    await callback_query.message.answer("👥 Здесь будет список всех пользователей.")
    # SELECT * FROM users LIMIT 10 или что-то подобное

@admin_router.callback_query(F.data == "admin_delete_user")
async def handle_delete_user_callback(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("🧹 Введите user_id пользователя, которого нужно удалить:")
    # FSM → delete_user_state
    await message.answer("🔧 Админ-панель:", reply_markup=keyboard)
@admin_router.message(AdminState.waiting_for_code)
async def process_new_code(message: Message, state: FSMContext):
    code_text = message.text.strip()

    if not code_text:
        await message.answer("❌ Код не может быть пустым. Попробуйте снова.")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cursor = conn.cursor()

        # Тут ты можешь изменить label и price на нужные
        label = "default"
        price = 0
        cursor.execute(
            "INSERT INTO uc_codes (code, label, price, used) VALUES (%s, %s, %s, FALSE)",
            (code_text, label, price)
        )

        conn.commit()
        cursor.close()
        conn.close()

        await message.answer(f"✅ Код <code>{code_text}</code> успешно добавлен в базу.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при добавлении кода: {e}")

    await state.clear()
@dp.message(F.text == "Помощь")
async def help_msg(message: Message):
    await message.answer("ℹ️ По всем вопросам обращайтесь: @chudoo_19")


@dp.message(F.text == "Профиль")
async def profile(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user = await fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

    if not user:
        await message.answer("Вы ещё не зарегистрированы.")
        return

    text = (
        f"<b>👤 Профиль</b>\n"
        f"Имя: {user['first_name']}\n"
        f"Username: @{user['username']}\n"
        f"ID: {user['user_id']}\n"
        f"🎮 PUBG ID: <code>{user['pubg_id'] if user['pubg_id'] else 'не указан'}</code>\n"
        f"Дата регистрации: {user['reg_date']}\n\n"
        f"<b>📜 Последние заказы:</b>\n"
    )

    orders = await fetchall(
        "SELECT id, label, quantity, price, status, created_at FROM orders "
        "WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5",
        user_id
    )

    btns = []
    for order in orders:
        status_text = {
            "completed": "✅ Выполнен",
            "cancelled": "❌ Отменён"
        }.get(order['status'], "⏳ В обработке")

        text += f"• {order['quantity']} x {order['label']} — {order['price']} RUB ({order['created_at']}) — {status_text}\n"

        if order['status'] == 'pending':
            btns.append([InlineKeyboardButton(
                text=f"❌ Отменить заказ #{order['id']}",
                callback_data=f"cancel_{order['id']}"
            )])

    btns.append([InlineKeyboardButton(text="✏️ Изменить PUBG ID", callback_data="change_pubg_id")])
    kb = InlineKeyboardMarkup(inline_keyboard=btns)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_order_callback(call: CallbackQuery, state: FSMContext):
    try:
        order_id = int(call.data.split("_")[1])
        user_id = call.from_user.id

        status = await fetchval(
            "SELECT status FROM orders WHERE id = $1 AND user_id = $2",
            order_id, user_id
        )

        if status in ("cancelled", "completed"):
            await call.answer("⚠️ Заказ уже отменён или завершён.", show_alert=True)
            return

        await execute(
            "UPDATE orders SET status = 'cancelled' WHERE id = $1 AND user_id = $2",
            order_id, user_id
        )

        await call.message.edit_text("❌ Заказ отменён.")
        await bot.send_message(
            chat_id=user_id,
            text="📲 Возвращаю вас в главное меню. Выберите действие:",
            reply_markup=main_menu_kb
        )

        await state.clear()
        await call.answer("✅ Отменено")
    except Exception as e:
        print(f"[❌ Ошибка отмены] {e}")
        await call.answer("❗️ Ошибка при отмене заказа", show_alert=True)


@dp.callback_query(F.data == "change_pubg_id")
async def change_pubg_id(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("✏️ Пожалуйста, введите новый PUBG ID:")
    await state.set_state(UCState.entering_pubg_id)


ADMIN_IDS = [ 1001953510 ]


async def notify_admin_all_codes():
    async with _pg_pool.acquire() as conn:
        all_codes = await conn.fetch("SELECT code, label, used FROM uc_codes")

    if not all_codes:
        return

    msg = "📦 Все UC-коды в базе:\n\n"
    for i, code in enumerate(all_codes, 1):
        status = "✅" if code['used'] else "🟢"
        msg += f"{i}. {status} <code>{code['code']}</code> ({code['label']})\n"

    chunks = [msg[i:i + 4000] for i in range(0, len(msg), 4000)]

    for admin_id in ADMIN_IDS:
        for chunk in chunks:
            try:
                await bot.send_message(chat_id=admin_id, text=chunk)
            except Exception as e:
                print(f"❌ Не удалось отправить админу {admin_id}: {e}")


async def on_startup(dispatcher):
    await init_db()
    await notify_admin_all_codes()


async def main():
    try:
        dp.startup.register(on_startup)
        await dp.start_polling(bot)
    finally:
        if _pg_pool is not None:
            await _pg_pool.close()
            print("🔒 Пул соединений закрыт.")




if __name__ == "__main__":
    asyncio.run(main())
    fetch = fetchall
