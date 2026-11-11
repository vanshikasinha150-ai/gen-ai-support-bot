
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for folder in ("tickets", "sentiment", "security"):
    path = str(ROOT / "src" / folder)
    if path not in sys.path:
        sys.path.insert(0, path)

import sent_service
import ticket_service


def run_once(now=None):
    """Run sentiment timeout and ticket SLA checks independently."""
    timestamp = now or datetime.now()

    report = {
        "sentiment_escalations": [],
        "ticket_sla": [],
        "errors": [],
    }

    try:
        report["sentiment_escalations"] = (
            sent_service.check_timeouts(timestamp)
        )
    except Exception as exc:
        report["errors"].append({
            "service": "sentiment",
            "error": str(exc),
        })

    try:
        report["ticket_sla"] = ticket_service.check_sla(timestamp)
    except Exception as exc:
        report["errors"].append({
            "service": "tickets",
            "error": str(exc),
        })

    return report


def daemon(interval_seconds=60, stop_event=None):
    """Continuously monitor customer conversations and ticket SLAs."""
    if interval_seconds <= 0:
        raise ValueError("Monitoring interval must be positive")

    print(
        f"Customer monitoring started. "
        f"Interval: {interval_seconds} seconds."
    )

    while stop_event is None or not stop_event.is_set():
        report = run_once()

        print(
            f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
            f"Sentiment escalations: "
            f"{len(report['sentiment_escalations'])}, "
            f"Ticket SLA records: {len(report['ticket_sla'])}, "
            f"Errors: {len(report['errors'])}"
        )

        for error in report["errors"]:
            print(
                f"  {error['service']} monitoring error: "
                f"{error['error']}"
            )

        if stop_event is not None:
            if stop_event.wait(interval_seconds):
                break
        else:
            time.sleep(interval_seconds)

    print("Customer monitoring stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Customer service monitoring"
    )

    parser.add_argument(
        "command",
        choices=["once", "daemon"],
    )

    parser.add_argument(
        "--now",
        help='Test timestamp, e.g. "2026-11-10 10:00:00"',
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Monitoring interval in seconds",
    )

    args = parser.parse_args()

    if args.command == "once":
        timestamp = (
            datetime.strptime(args.now, "%Y-%m-%d %H:%M:%S")
            if args.now else datetime.now()
        )

        report = run_once(timestamp)

        print("Sentiment escalations:")
        for item in report["sentiment_escalations"]:
            print(f"  {item}")

        print("Ticket SLA report:")
        for item in report["ticket_sla"]:
            print(f"  {item}")

        print("Errors:")
        for item in report["errors"]:
            print(f"  {item}")

    else:
        daemon(args.interval)


if __name__ == "__main__":
    main()
