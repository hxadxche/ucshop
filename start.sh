#!/bin/bash

echo "Скачиваем свежую базу данных..."
curl -o users_orders.db https://raw.githubusercontent.com/hxadxche/ucshop/main/users_orders.db

echo "Запуск Telegram-бота и Webhook-сервера..."
python3 ucshop.py &         # Бот
python3 webhook_server.py  # Flask-сервер
