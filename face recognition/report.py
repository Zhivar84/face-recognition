"""Daily attendance report to console and CSV.

Usage: python report.py [--date 2026-10-13]
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import database as db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=date.today().isoformat())
    args = parser.parse_args()
    day = datetime.strptime(args.date, "%Y-%m-%d").date()

    db.init_db()
    rows = db.daily_report(day)
    if not rows:
        print(f"روزی {day} رکوردی وجود ندارد.")
        return

    settings = db.get_settings()
    statuses = [db.classify_event(r["event"], r["logged_at"], settings) for r in rows]

    print(f"{'نام':<25} {'شماره':<12} {'اتفاق':<6} {'ساعت':<10} {'sim':<5} {'وضعیت':<8}")
    print("-" * 70)
    for r, st in zip(rows, statuses):
        print(f"{r['full_name']:<25} {r['student_no']:<12} {r['event']:<6} "
              f"{r['logged_at'][11:]:<10} {'' if r['similarity'] is None else f'{r['similarity']:.2f}':<5} "
              f"{'مشکوک' if st == 'suspicious' else 'مجاز':<8}")

    out = f"attendance_{day}.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["full_name", "student_no", "event", "logged_at", "similarity", "status"])
        for r, st in zip(rows, statuses):
            w.writerow([r["full_name"], r["student_no"], r["event"], r["logged_at"], r["similarity"], st])
    print(f"\nخروجی CSV: {out}")


if __name__ == "__main__":
    main()
