"""
main.py — Entry point PEDIA AI AGENT
"""
import sys
import os
import logging
from pathlib import Path

# Setup logging
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("pedia-agent")


def setup_log_file():
    """Add file handler setelah config loaded."""
    from jarvis.config import LOG_PATH
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(LOG_PATH))
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger().addHandler(fh)


def main():
    print("=" * 50)
    print("  PEDIA AI AGENT")
    print("  Android 11 · Termux · armeabi-v7a")
    print("=" * 50)

    # Validasi config
    from jarvis.config import validate, AGENT_NAME
    if not validate():
        print("\n❌ Konfigurasi tidak lengkap. Edit file .env terlebih dahulu.")
        sys.exit(1)

    setup_log_file()

    # Init database
    from jarvis import memory
    memory.init_db()
    logger.info("Database initialized.")

    # Run mode
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        run_cli_mode()
    else:
        run_telegram_mode()


def run_telegram_mode():
    """Mode default: Telegram Bot."""
    logger.info("Starting in Telegram Bot mode...")
    from jarvis.telegram import run_bot
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Bot dihentikan.")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


def run_cli_mode():
    """Mode CLI untuk testing langsung di terminal."""
    from jarvis.ai import chat
    from jarvis.config import AGENT_NAME

    TEST_USER = "cli-user"
    print(f"\n{AGENT_NAME} CLI Mode — ketik 'quit' untuk keluar\n")

    while True:
        try:
            user_input = input("Kamu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSampai jumpa!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "keluar"):
            print("Sampai jumpa!")
            break

        print(f"\n{AGENT_NAME}: ", end="", flush=True)
        try:
            response = chat(TEST_USER, user_input)
            print(response)
        except Exception as e:
            print(f"Error: {e}")
        print()


if __name__ == "__main__":
    main()
