import argparse
import sys
import threading
import time
from datetime import datetime

from ingest import run_pipeline as ingest_jobs
# Align these imports with your exact function names
from evaluate import run_evaluation_loop
from dispatch import dispatch_top_jobs
from bot_listener import run_listener


def run_scout_cycle():
    """Runs a complete end-to-end scout sweep."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*50}")
    print(f"🚀 [CYCLE START] Scout Pipeline Triggered at {timestamp}")
    print(f"{'='*50}\n")

    try:
        print("📥 Phase 1: Ingesting postings across adapters...")
        ingest_jobs()

        print("\n⚖️ Phase 2: Evaluating and scoring new postings...")
        run_evaluation_loop()

        print("\n📤 Phase 3: Generating LLM dossiers and dispatching alerts...")
        dispatch_top_jobs(min_score=60, limit=3)

        print(f"\n✅ [CYCLE COMPLETE] Finished at {datetime.now().strftime('%H:%M:%S')}.\n")

    except Exception as e:
        print(f"\n❌ [CYCLE ERROR] Pipeline failed: {e}\n")


def daemon_scheduler(interval_hours: float):
    """Runs the scout cycle repeatedly every interval_hours."""
    interval_seconds = int(interval_hours * 3600)
    print(f"⏱️ Scheduled recurring scout cycle every {interval_hours} hours ({interval_seconds}s).")

    while True:
        time.sleep(interval_seconds)
        run_scout_cycle()


def start_orchestrator(interval_hours: float = 6.0):
    print("🛰️ Starting Unified Job Scout Orchestrator...")
    
    # 1. Immediate sweep on boot
    run_scout_cycle()

    # 2. Launch background scheduler thread
    scheduler_thread = threading.Thread(
        target=daemon_scheduler,
        args=(interval_hours,),
        daemon=True,
        name="ScoutSchedulerThread"
    )
    scheduler_thread.start()

    # 3. Keep main thread polling for Telegram actions
    print("🎧 Launching Telegram listener (Ctrl+C to stop)...")
    try:
        run_listener()
    except KeyboardInterrupt:
        print("\n🛑 Orchestrator shut down cleanly.")


def main():
    parser = argparse.ArgumentParser(description="Unified Autonomous Job Scout Pipeline")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single ingest-evaluate-dispatch sweep and immediately exit."
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=6.0,
        help="Polling interval in hours when running in daemon mode (default: 6.0)."
    )

    args = parser.parse_args()

    if args.once:
        run_scout_cycle()
    else:
        start_orchestrator(interval_hours=args.interval)


if __name__ == "__main__":
    main()