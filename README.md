# 🚚 Delivery Bot

**Delivery Bot** — это Telegram-бот для автоматизации доставки между магазинами, курьерами и администраторами.
Сервис помогает магазинам быстро находить курьеров, управлять заказами и контролировать спорные ситуации без хаоса в чатах.

---

## 📌 Описание проекта

Многие магазины координируют доставку через обычные чаты в мессенджерах, что приводит к путанице, потере заказов и отсутствию прозрачности.

**Delivery Bot решает эту проблему**, предоставляя единую систему, где:

* магазины создают заказы
* курьеры получают и выполняют доставки
* администраторы контролируют спорные ситуации
* система собирает аналитику по работе доставки

Проект является **коммерческим** и ориентирован на реальный спрос со стороны малого и среднего бизнеса.

---

## ⚙️ Технологии

| Зона           | Стек                   |
| -------------- | ---------------------- |
| Backend        | FastAPI 0.117, Uvicorn |
| Telegram Bot   | aiogram 3.22           |
| ORM            | SQLAlchemy 2.0 (async) |
| База данных    | PostgreSQL / SQLite    |
| Кеш / FSM      | Redis                  |
| Аутентификация | JWT (python-jose)      |
| Валидация      | Pydantic 2.11          |
| HTTP-клиенты   | httpx, aiohttp         |
| Язык           | Python 3.13+           |

---

## ✨ Основной функционал

* 👤 Регистрация пользователей (магазины, курьеры, админы)
* 📦 Создание и управление заказами
* 🚴 Назначение курьеров на заказы
* 🔄 Отслеживание статусов доставки
* 🛡 Контроль администраторов за спорными ситуациями
* 📊 Аналитика по заказам и работе системы

---

## 🚧 Планы по развитию

* 🤖 Оптимальное автоматическое распределение заказов между курьерами
* 📈 Расширенная статистика и отчёты
* 📍 Улучшенная логика отслеживания доставок

---

## 🚀 Установка

### Требования

* Python **3.13+**
* PostgreSQL *(опционально — можно использовать SQLite)*
* Redis

---

### Шаги установки

```bash
# Клонирование репозитория
git clone https://github.com/alisher-balpisov/delivery_bot_project.git
cd delivery_bot_project

# Создание виртуального окружения
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Установка зависимостей
pip install -e .
# или через uv:
uv pip install -e .
```

---

## ⚙️ Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

```env
APP_NAME=Delivery Bot
DEBUG=true
ENVIRONMENT=development

# Telegram Bot (получить у @BotFather)
TELEGRAM__BOT_TOKEN=your_bot_token_here

# База данных
DATABASE__URL=postgresql+asyncpg://user:password@localhost:5432/delivery_bot
# или для разработки:
DATABASE__URL=sqlite+aiosqlite:///./delivery_bot.db

# Redis
REDIS__HOST=localhost
REDIS__PORT=6379
REDIS__DB=0

# JWT
JWT__SECRET_KEY=your_jwt_secret_key_here
JWT__ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT__REFRESH_TOKEN_EXPIRE_DAYS=30

# API
API_HOST=localhost
API_PORT=8000
API_PREFIX=/api/v1

# Супер-администраторы (Telegram ID через запятую)
ADMIN__SUPER_ADMIN_TELEGRAM_IDS=123456789,987654321
```

👉 Чтобы получить права супер-админа, добавьте **свой Telegram ID** в
`ADMIN__SUPER_ADMIN_TELEGRAM_IDS`.

---

## ▶️ Запуск проекта

### Запуск API (Backend)

```bash
python -m backend.src.main
```

Или напрямую через uvicorn:

```bash
uvicorn backend.src.main:app --host 0.0.0.0 --port 8000 --reload
```

API будет доступен по адресу:
**[http://localhost:8000](http://localhost:8000)**
Swagger документация:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

---

### 🤖 Запуск Telegram-бота

```bash
python run_bot.py
```

Или без hot-reload:

```bash
python -m bot.main
```

---

### 🔄 Запуск обоих компонентов

Рекомендуется запускать в разных терминалах:

**Терминал 1 — API**

```bash
python -m backend.src.main
```

**Терминал 2 — Bot**

```bash
python run_bot.py
```

---

## 🧩 Использование

1. Пользователь взаимодействует с ботом через Telegram
2. Магазины создают заказы
3. Курьеры принимают и выполняют доставки
4. Администраторы управляют спорными ситуациями
5. Все действия синхронизируются через API и базу данных

---

## 👥 Авторы

Проект разработан командой из двух человек.

**GitHub:**

* [https://github.com/alisher-balpisov](https://github.com/alisher-balpisov)
* [https://github.com/ProstoShamik](https://github.com/ProstoShamik)


