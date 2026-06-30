"""
main.py — PEDIA AI AGENT v3.0 Entry Point
WhatsApp AI Agent + Admin Dashboard
"""
import sys, logging, threading
from pathlib import Path

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=[logging.StreamHandler(sys.stdout)])
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
    print("  PEDIA AI AGENT v3.0")
    print("  WhatsApp AI Agent + Admin Dashboard")
    print("══════════════════════════════════════════")

    from jarvis.config import validate, GEMINI_API_KEY, CEREBRAS_API_KEY, GROQ_API_KEY, DASHBOARD_PORT
    if not validate():
        print("\n❌ Set minimal satu API key di .env")
        sys.exit(1)

    setup_log_file()

    from jarvis import memory
    memory.init_db()

    providers = []
    if GEMINI_API_KEY:   providers.append("Gemini ✅")
    if CEREBRAS_API_KEY: providers.append("Cerebras ✅")
    if GROQ_API_KEY:     providers.append("Groq ✅")
    print("  AI Providers: " + " → ".join(providers))

    if "--cli" in sys.argv:
        run_cli_mode()
        return

    if "--dashboard-only" in sys.argv:
        run_dashboard_only()
        return

    # Default: WhatsApp + Dashboard
    run_all()

def run_dashboard_only():
    from dashboard.app import run_dashboard
    print("  Mode: Dashboard Only")
    run_dashboard()

def run_all():
    from jarvis.config import DASHBOARD_PORT
    print("  Mode: WhatsApp Bot + Admin Dashboard")
    print(f"  Dashboard: http://localhost:{DASHBOARD_PORT}")
    print("  Scan QR Code yang muncul untuk login WhatsApp.")
    print("")

    # Start dashboard di thread terpisah
    from dashboard.app import run_dashboard
    t_dash = threading.Thread(target=run_dashboard, daemon=True)
    t_dash.start()

    # Start WhatsApp bot (blocking)
    from jarvis.whatsapp import WhatsAppAgent
    agent = WhatsAppAgent(session_id="default")
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
    except Exception as e:
        logger.exception("Fatal: %s", e)
        sys.exit(1)

def run_cli_mode():
    from jarvis.ai import chat
    from jarvis.config import AGENT_NAME
    TEST_USER = "cli-user"
    print("  Mode: CLI Testing\n  Ketik 'quit' untuk keluar.\n")
    while True:
        try:
            user_input = input("Kamu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSampai jumpa!"); break
        if not user_input: continue
        if user_input.lower() in ("quit","exit","keluar"):
            print("Sampai jumpa!"); break
        print(AGENT_NAME + ": ", end="", flush=True)
        try:
            r = chat(TEST_USER, user_input, sender_phone=TEST_USER, sender_name="Tester")
            print(r)
        except Exception as e:
            print("Error:", e)
        print()

if __name__ == "__main__":
    main()
