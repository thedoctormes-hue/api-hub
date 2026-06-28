#!/bin/bash
# Инициализация PostgreSQL для api-hub
# Создаёт пользователя, БД и таблицы если они не существуют

set -e

DB_USER="apihub"
DB_PASS="apihub"
DB_NAME="apihub"

echo "=== Initializing api-hub database ==="

# Создаём пользователя если не существует
sudo -u postgres psql -tc "SELECT 1 FROM pg_user WHERE usename='$DB_USER'" | grep -q 1 || {
    echo "Creating user: $DB_USER"
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
}

# Создаём БД если не существует
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || {
    echo "Creating database: $DB_NAME"
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
}

echo "=== Database ready ==="
