# 🚚 Delivery Bot

Telegram-бот и REST API для управления доставкой заказов. Система связывает магазины, курьеров и администраторов в единый процесс обработки заказов.

## 📋 Содержание

- [Стек технологий](#-стек-технологий)
- [Архитектура](#-архитектура)
- [Структура проекта](#-структура-проекта)
- [Установка](#-установка)
- [Переменные окружения](#-переменные-окружения)
- [Запуск](#-запуск)
- [API Эндпоинты](#-api-эндпоинты)

---

## 🛠 Стек технологий

| Категория | Технология |
|-----------|------------|
| **Backend** | FastAPI 0.117, Uvicorn |
| **Telegram Bot** | aiogram 3.22 |
| **ORM** | SQLAlchemy 2.0 (async) |
| **База данных** | PostgreSQL / SQLite |
| **Кеш / FSM** | Redis |
| **Аутентификация** | JWT (python-jose) |
| **Валидация** | Pydantic 2.11 |
| **HTTP-клиент** | httpx, aiohttp |
| **Python** | 3.13+ |

---

## 🏗 Архитектура

Проект разделён на две основные части:

### Backend (FastAPI REST API)

Отвечает за:
- Хранение и обработку данных
- Аутентификацию и авторизацию (JWT)
- Бизнес-логику заказов
- CRUD-операции для всех сущностей

### Bot (aiogram Telegram Bot)

Отвечает за:
- Интерфейс взаимодействия с пользователями
- Регистрацию по инвайт-кодам
- Создание и отслеживание заказов
- Уведомления участников процесса

### Роли пользователей

| Роль | Возможности |
|------|-------------|
| **Admin** | Управление пользователями, кодами регистрации, просмотр статистики |
| **Shop** | Создание заказов, просмотр своих заказов |
| **Courier** | Принятие и выполнение заказов, загрузка фото-отчётов |
| **Guest** | Ограниченный доступ (гостевой режим) |

---

## 📁 Структура проекта

```
delivery_bot_project/
├── backend/
│   └── src/
│       ├── admin/         # Админ-панель: статистика, управление
│       ├── api/           # Роутинг API
│       ├── auth/          # Аутентификация, JWT
│       ├── common/        # Общие модули (enums, utils)
│       ├── core/          # Конфигурация, БД, логирование
│       ├── couriers/      # Логика курьеров
│       ├── disputes/      # Споры (в разработке)
│       ├── models/        # SQLAlchemy модели
│       ├── orders/        # Заказы: CRUD, статусы
│       ├── shops/         # Логика магазинов
│       ├── users/         # Управление пользователями
│       └── main.py        # Точка входа API
├── bot/
│   ├── clients/           # HTTP-клиенты для API
│   ├── filters/           # Фильтры aiogram
│   ├── handlers/          # Обработчики сообщений
│   │   ├── admin/         # Хендлеры админа
│   │   ├── auth/          # Авторизация/регистрация
│   │   ├── common/        # Общие хендлеры
│   │   ├── courier/       # Хендлеры курьера
│   │   ├── public/        # Публичные команды
│   │   └── shop/          # Хендлеры магазина
│   ├── keyboards/         # Инлайн и reply клавиатуры
│   ├── messages/          # Тексты сообщений
│   ├── middleware/        # Middleware (auth, throttling)
│   ├── utils/             # Утилиты
│   └── main.py            # Точка входа бота
├── .env.example           # Пример переменных окружения
├── pyproject.toml         # Зависимости и конфигурация
├── run_bot.py             # Запуск бота с hot-reload
└── requirements.txt       # Альтернативный файл зависимостей
```

---

## 🚀 Установка

### Требования

- Python 3.13+
- PostgreSQL (опционально, можно SQLite)
- Redis

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

```

### Основные переменные

```env
# Приложение
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

# JWT (сгенерировать: openssl rand -hex 32)
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

Полный список переменных см. в [.env.example](.env.example).

---

## ▶️ Запуск

### Запуск API (Backend)

```bash
# Стандартный запуск
python -m backend.src.main

# Только API без визуализации
python -m backend.src.main api

# Через uvicorn напрямую
uvicorn backend.src.main:app --host 0.0.0.0 --port 8000 --reload
```

API будет доступен: `http://localhost:8000`
Документация Swagger: `http://localhost:8000/docs`

### Запуск Telegram-бота

```bash
# С автоматической перезагрузкой при изменениях
python run_bot.py

# Напрямую без hot-reload
python -m bot.main
```

### Запуск обоих компонентов

Рекомендуется запускать в разных терминалах:

```bash
# Терминал 1 — API
python -m backend.src.main

# Терминал 2 — Bot
python run_bot.py
```

---

## 📡 API Эндпоинты

Базовый URL: `http://localhost:8000/api/v1`

### Аутентификация (`/auth`)

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | `/auth/code` | Регистрация по инвайт-коду |
| POST | `/auth/guest` | Гостевая регистрация |
| POST | `/auth/login` | Вход для существующих пользователей |
| POST | `/auth/refresh` | Обновление access-токена |
| POST | `/auth/token` | OAuth2 для Swagger UI |

### Заказы (`/orders`)

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| POST | `/orders` | Создание заказа (магазин) |
| GET | `/orders` | Список заказов с фильтрами |
| GET | `/orders/{id}` | Детали заказа |
| PATCH | `/orders/{id}` | Обновление заказа |
| POST | `/orders/{id}/complete` | Завершение с фото-отчётом |

### Магазины (`/shops`)

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/shops` | Список магазинов |
| GET | `/shops/{id}` | Информация о магазине |

### Курьеры (`/couriers`)

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/couriers` | Список курьеров |
| GET | `/couriers/{id}` | Информация о курьере |

### Администрирование (`/admin`)

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/admin/stats` | Системная статистика |
| GET | `/admin/users` | Список пользователей |
| POST | `/admin/codes` | Генерация инвайт-кода |

### Служебные

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| GET | `/` | Информация о приложении |
| GET | `/api/v1/health` | Проверка здоровья |

---
