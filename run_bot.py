import sys
from pathlib import Path

# Добавить backend/ в PYTHONPATH
from bot.main import main

backend_path = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_path))

if __name__ == "__main__":
    main()
