# Delivery Bot Project

Telegram bot for delivery management system with FastAPI backend.

## Features

- 🤖 Telegram Bot interface
- 🚀 FastAPI REST API
- 🗄️ PostgreSQL/SQLite database support
- 🔐 JWT authentication
- 📦 Redis caching
- 🎨 Clean architecture

## Requirements

- Python 3.13+
- PostgreSQL (or SQLite for development)
- Redis

## Installation

### Using uv (recommended)

```bash
# Clone repository
git clone https://github.com/alisher-balpisov/delivery_bot_project.git
cd delivery_bot_project

# Install dependencies
uv pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run database migrations (if using Alembic)
# alembic upgrade head
```

### Using pip

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env
```

### Using make

```bash
# First-time setup
make setup

# Install dependencies
make install-dev
```

## Configuration

1. Copy `.env.example` to `.env`
2. Fill in your configuration:
   - `TELEGRAM__BOT_TOKEN` - from @BotFather
   - `DATABASE__URL` - database connection string
   - `JWT__SECRET_KEY` - generate with: `openssl rand -hex 32`
   - `REDIS__HOST` and `REDIS__PORT` - Redis connection

## Running

### Telegram Bot

```bash
# Using Python
python -m bot.main

# Using make
make run-bot
```

### FastAPI Backend

```bash
# Using uvicorn
uvicorn backend.src.main:app --reload

# Using make
make run-api
```

## Development

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Fix issues automatically
make fix

# Run all checks
make check
```

### Testing

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run fast tests only
make test-fast
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run manually
make pre-commit
```

## Project Structure

```
delivery_bot_project/
├── backend/              # FastAPI backend
│   ├── src/
│   │   ├── core/        # Core configuration
│   │   ├── api/         # API routes
│   │   ├── models/      # Database models
│   │   └── services/    # Business logic
│   └── tests/           # Backend tests
├── bot/                 # Telegram bot
│   ├── handlers/        # Message handlers
│   ├── keyboards/       # Bot keyboards
│   ├── states/          # FSM states
│   └── main.py         # Bot entry point
├── .env.example        # Environment variables template
├── pyproject.toml      # Project configuration
└── README.md          # This file
```

## Available Commands (Make)

```bash
make help          # Show all available commands
make setup         # Initial project setup
make install-dev   # Install development dependencies
make test          # Run tests
make lint          # Check code quality
make format        # Format code
make check         # Run all checks
make run-bot       # Start Telegram bot
make run-api       # Start FastAPI server
make clean         # Clean temporary files
```

## Environment Variables

See `.env.example` for all available configuration options.

### Required Variables

- `TELEGRAM__BOT_TOKEN` - Telegram bot token
- `DATABASE__URL` - Database connection URL
- `JWT__SECRET_KEY` - Secret key for JWT tokens

### Optional Variables

- `REDIS__HOST` - Redis host (default: localhost)
- `DEBUG` - Enable debug mode (default: true)
- `API_PORT` - API server port (default: 8000)

## License

This project is private.

## Authors

- Alisher Balpisov

## Contributing

This is a private project. For contributions, please contact the repository owner.

## Support

For issues and questions, please open an issue on GitHub or contact the maintainer.
