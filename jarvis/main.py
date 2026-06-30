"""
main.py — Entry point PEDIA AI AGENT v2.0 (WhatsApp Edition)
"""
import sys
import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("pedia-agent")


def setup_log_file():
    from jarvis.config import LOG_PATH
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(str(LOG_PATH))
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.getLogger().addHandler(fh)


def main():
    print("")
    print("══════════════════════════════════════════")
    print("  PEDIA AI AGENT v2.0")
    print("  WhatsApp AI Agent · Android Termux")
    print("══════════════════════════════════════════")

    from jarvis.config import validate, AGENT_NAME, GEMINI_API_KEY, CEREBRAS_API_KEY, GROQ_API_KEY
    if not validate():
        print("\n❌ Set minimal satu API key di .env")
        sys.exit(1)

    setup_log_file()

    from jarvis import memory
    memory.init_db()
    logger.info("Database initialized.")

    # Tampilkan provider yang aktif
    providers = []
    if GEMINI_API_KEY:   providers.append("Gemini ✅")
    if CEREBRAS_API_KEY: providers.append("Cerebras ✅")
    if GROQ_API_KEY:     providers.append("Groq ✅")
    print("  AI Providers: " + " → ".join(providers))
    print("")

    if "--cli" in sys.argv:
        run_cli_mode()
    else:
        run_whatsapp_mode()


def run_whatsapp_mode():
    print("  Mode: WhatsApp Bot")
    print("  Memulai wa_bridge.js...")
    print("  Scan QR Code yang muncul untuk login WhatsApp.")
    print("  Session tersimpan permanen — tidak perlu scan ulang setelah restart.")
    print("")

    from jarvis.whatsapp import WhatsAppAgent
    agent = WhatsAppAgent()
    
    try:
        agent.start()
        print("")
        print("  ✅ WhatsApp connected! AI Agent aktif.")
        print("  Tekan Ctrl+C untuk berhenti.")
        print("")
        agent.wait()
    except KeyboardInterrupt:
        print("\n  Menghentikan agent...")
        agent.stop()
        print("  Sampai jumpa!")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


def run_cli_mode():
    from jarvis.ai import chat
    from jarvis.config import AGENT_NAME

    TEST_USER = "cli-user"
    print("  Mode: CLI Testing")
    print("  Ketik 'quit' untuk keluar.\n")

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

        print(AGENT_NAME + ": ", end="", flush=True)
        try:
            response = chat(TEST_USER, user_input,
                           sender_phone=TEST_USER,
                           sender_name="Tester")
            print(response)
        except Exception as e:
            print("Error: " + str(e))
        print()


if __name__ == "__main__":
    main()
