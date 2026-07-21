#!/bin/sh
set -e

echo "Đang chạy migration Alembic..."
alembic upgrade head

echo "Khởi động backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
