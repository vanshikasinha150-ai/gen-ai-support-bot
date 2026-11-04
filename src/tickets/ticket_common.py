from datetime import datetime, timedelta, time
from pathlib import Path

import yaml


def load_cfg():
    # re-read on every call, so changes to config.yaml apply at runtime
    return yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8-sig"))["tickets"]


def parse_dt(value):
    if isinstance(value, datetime):
        return value
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def is_workday(day, cfg):
    holidays = [str(h) for h in cfg["holidays"]]
    return day.weekday() not in cfg["weekend_days"] and day.isoformat() not in holidays


def _next_midnight(dt):
    return datetime.combine(dt.date() + timedelta(days=1), time.min)


def working_hours_between(start, end, cfg):
    """SLA clock: hours elapsed, counting only working days (weekends and holidays excluded)."""
    total, cur = 0.0, start
    while cur < end:
        seg_end = min(end, _next_midnight(cur))
        if is_workday(cur.date(), cfg):
            total += (seg_end - cur).total_seconds() / 3600
        cur = seg_end
    return total


def due_time(start, hours, cfg):
    remaining, cur = float(hours), start
    for _ in range(3650):
        day_end = _next_midnight(cur)
        if is_workday(cur.date(), cfg):
            free = (day_end - cur).total_seconds() / 3600
            if free >= remaining:
                return cur + timedelta(hours=remaining)
            remaining -= free
        cur = day_end
    raise ValueError("no working days configured")


def _hm(text):
    h, m = map(int, text.split(":"))
    return time(h, m)


def in_business_hours(now, cfg):
    bh = cfg["business_hours"]
    return is_workday(now.date(), cfg) and _hm(bh["start"]) <= now.time() < _hm(bh["end"])


def next_business_open(now, cfg):
    start = _hm(cfg["business_hours"]["start"])
    day = now.date()
    if is_workday(day, cfg) and now.time() < start:
        return datetime.combine(day, start)
    day += timedelta(days=1)
    while not is_workday(day, cfg):
        day += timedelta(days=1)
    return datetime.combine(day, start)
