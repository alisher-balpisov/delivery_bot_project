from watchfiles import run_process


def start():
    from bot.main import main

    main()


if __name__ == "__main__":
    run_process(".", target=start)
