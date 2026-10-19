import sys, time, argparse
from datetime import datetime, time as dtime
from pathlib import Path
import yaml

import update

CFG = yaml.safe_load(Path("config/config.yaml").read_text())["pipeline"]


def parse_hm(s):
    h, m = map(int, s.split(":"))
    return dtime(h, m)


def in_window(now):
    start, end = parse_hm(CFG["maintenance_start"]), parse_hm(CFG["maintenance_end"])
    t = now.time()
    return start <= t < end if start < end else (t >= start or t < end)


def active_version():
    return update.load_json(update.STATE, {"active": None})["active"]


def healthy():
    try:
        acc, _ = update.evaluate(update.LIVE)
    except Exception as e:
        print(f"  health check error: {e}")
        return False
    ok = acc >= CFG["health_min_accuracy"]
    print(f"  accuracy {acc:.0%} -> {'OK' if ok else 'FAILED'}")
    return ok


def health_watch(scale):
    total = CFG["health_check_minutes"]
    for minute in range(1, total + 1):
        print(f"Health check {minute}/{total} min")
        if not healthy():
            print("Health check failed: rolling back automatically")
            update.rollback()
            return False
        time.sleep(60 * scale)
    print("Health checks passed. Update is stable.")
    return True


def run_scheduled(now, scale, fail_times=0, break_live=False):
    print(f"Scheduled run at {now:%Y-%m-%d %H:%M}")
    if not in_window(now):
        print(f"Outside maintenance window ({CFG['maintenance_start']}-{CFG['maintenance_end']}). Update deferred.")
        return
    before = active_version()
    attempts = 0
    for i, delay in enumerate([0] + CFG["retry_minutes"]):
        if delay:
            print(f"Retry {i} in {delay} min ...")
            time.sleep(delay * 60 * scale)
        attempts += 1
        try:
            if attempts <= fail_times:                      # simulated failure for testing
                raise RuntimeError("simulated update failure")
            update.run_update()
            break
        except Exception as e:
            print(f"Attempt {attempts} failed: {e}")
    else:
        print("All retries failed. Alert: manual check needed.")
        return
    if active_version() != before:                          # a new version went live
        if break_live:
            Path(update.LIVE).write_text("{}")              # simulate a bad deployment
        health_watch(scale)


def daemon(scale):
    print(f"Scheduler running. Update time {CFG['update_time']}, "
          f"window {CFG['maintenance_start']}-{CFG['maintenance_end']}")
    last = None
    while True:
        now = datetime.now()
        if now.strftime("%H:%M") == CFG["update_time"] and last != now.date():
            run_scheduled(now, scale)
            last = now.date()
        time.sleep(20)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["run", "daemon"])
    p.add_argument("--now", help='simulated time, e.g. "2026-10-20 02:30"')
    p.add_argument("--fast", action="store_true", help="shrink waits for testing")
    p.add_argument("--fail", type=int, default=0, help="simulate N failed attempts")
    p.add_argument("--break-live", action="store_true", help="simulate a bad deployment")
    a = p.parse_args()
    scale = 0.01 if a.fast else 1
    if a.command == "daemon":
        daemon(scale)
    else:
        now = datetime.strptime(a.now, "%Y-%m-%d %H:%M") if a.now else datetime.now()
        run_scheduled(now, scale, a.fail, a.break_live)