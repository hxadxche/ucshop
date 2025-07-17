#!/bin/bash

echo "🔁 Скачиваем свежую базу данных..."
curl -o users_orders.db https://raw.githubusercontent.com/hxadxche/название-репозитория/main/users_orders.db

echo "🚀 Запуск бота..."
python3 ucshop.py
