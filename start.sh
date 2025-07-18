#!/bin/bash

# Установка зависимостей
echo "Устанавливаем зависимости..."
pip install -r requirements.txt > /dev/null

# Скачиваем свежую базу данных (если нужно)
echo "Скачиваем свежую базу данных..."
curl -O https://example.com/path/to/database.db  # Замените на реальный URL

# Исправление предупреждения в webhook_server.py
sed -i "s/bot = Bot(token=TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)/from aiogram.client.default import DefaultBotProperties\nbot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))/" webhook_server.py

# Запуск бота и вебхук-сервера
echo "Запуск Telegram-бота и Webhook-сервера..."
python ucshop.py &
python webhook_server.py &

# Бесконечный цикл
while true; do sleep 3600; done
