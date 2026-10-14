"""ساخت فایل اکسل گزارش حضور و غیاب یک روز (حاضر/غایب + نمودار کنار هر نفر).

اجرا:
    python export.py                 # گزارش امروز
    python export.py --date 2026-10-14
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import jdatetime
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import database as db

REPORTS_DIR = Path(__file__).parent / "reports"
TREND_DAYS = 14

INK = "1F2937"
HEAD_FILL = PatternFill("solid", fgColor="2F7D51")
TITLE_FILL = PatternFill("solid", fgColor="EAF1F9")
ABSENT_FILL = PatternFill("solid", fgColor="FBECEC")
SUSP_FILL = PatternFill("solid", fgColor="FDF4E4")
CENTER = Alignment(horizontal="center", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")
THIN = Side(style="thin", color="E6EAF0")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


J_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
J_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def jalali_str(day: date) -> str:
    j = jdatetime.date.fromgregorian(date=day)
    return f"{J_WEEKDAYS[j.weekday()]} {j.day} {J_MONTHS[j.month - 1]} {j.year}"


def _parse(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _presence_counts(day: date) -> dict[int, int]:
    """تعداد روزهایی که هر دانشجو در بازه TREND_DAYS روز اخیر حضور داشته."""
    start = day - timedelta(days=TREND_DAYS - 1)
    with db.get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT student_id, date(logged_at) AS d
            FROM attendance
            WHERE event = 'IN' AND date(logged_at) BETWEEN ? AND ?
            """,
            (start.isoformat(), day.isoformat()),
        ).fetchall()
    counts: dict[int, int] = {}
    for r in rows:
        counts[r["student_id"]] = counts.get(r["student_id"], 0) + 1
    return counts


def _trend(day: date) -> list[tuple[str, int, int]]:
    """(برچسب شمسی, تعداد حاضر, تعداد غایب) برای TREND_DAYS روز اخیر."""
    out = []
    for i in range(TREND_DAYS - 1, -1, -1):
        d = day - timedelta(days=i)
        present = {r["student_id"] for r in db.daily_report(d) if r["event"] == "IN"}
        total = len(db.list_students())
        j = jdatetime.date.fromgregorian(date=d)
        out.append((f"{j.year}/{j.month:02d}/{j.day:02d}", len(present), max(total - len(present), 0)))
    return out


def collect(day: date) -> dict:
    """همه داده‌های لازم گزارش یک روز، یک‌جا."""
    settings = db.get_settings()
    events = [dict(r) for r in db.daily_report(day)]
    for e in events:
        e["status"] = db.classify_event(e["event"], e["logged_at"], settings)

    by_student: dict[int, list[dict]] = {}
    for e in events:
        by_student.setdefault(e["student_id"], []).append(e)

    presence = _presence_counts(day)
    hour_hist: dict[str, int] = {}
    for e in events:
        if e["event"] == "IN":
            h = (e["logged_at"] or "")[11:13] or "--"
            hour_hist[h] = hour_hist.get(h, 0) + 1

    end_ref = datetime.now() if day == date.today() else None

    def build(row, present: bool) -> dict:
        sid = row["id"]
        evs = sorted(by_student.get(sid, []), key=lambda e: e["logged_at"])
        ins = [_parse(e["logged_at"]) for e in evs if e["event"] == "IN"]
        outs = [_parse(e["logged_at"]) for e in evs if e["event"] == "OUT"]
        ins = [t for t in ins if t]
        outs = [t for t in outs if t]
        first_in = min(ins) if ins else None
        minutes = 0
        if first_in:
            last_end = max(outs) if outs else (end_ref or max(ins))
            minutes = max(int((last_end - first_in).total_seconds() // 60), 0)
        suspicious = sum(1 for e in evs if e["status"] == "suspicious")
        if evs and not ins:
            state = "بدون ورود (فقط خروج)"
        elif present:
            state = "حاضر"
        else:
            state = "غایب"
        return {
            "id": sid,
            "full_name": row["full_name"],
            "student_no": row["student_no"],
            "major": row["major"] or "—",
            "state": state,
            "first_in": first_in.strftime("%H:%M") if first_in else "—",
            "last_out": max(outs).strftime("%H:%M") if outs else "—",
            "duration": (
                "—" if not minutes
                else f"{minutes // 60} ساعت و {minutes % 60} دقیقه"
                     + (" (تا الان)" if not outs and end_ref else "")
            ),
            "minutes": minutes,
            "events": len(evs),
            "suspicious": suspicious,
            "days14": presence.get(sid, 0),
        }

    students = db.list_students()
    records = []
    for s in students:
        present = s["id"] in by_student and any(e["event"] == "IN" for e in by_student[s["id"]])
        records.append(build(s, present))
    present_rows = sorted((r for r in records if r["state"] == "حاضر"), key=lambda r: r["first_in"])
    other_rows = sorted((r for r in records if r["state"] != "حاضر"), key=lambda r: r["full_name"])
    return {
        "day": day,
        "jalali": jalali_str(day),
        "events": events,
        "present": present_rows,
        "absent": other_rows,
        "hours": dict(sorted(hour_hist.items())),
        "trend": _trend(day),
        "enabled_hours": settings["hours_enabled"] == "1",
        "window_in": f"{settings['in_start']}–{settings['in_end']}",
        "window_out": f"{settings['out_start']}–{settings['out_end']}",
    }


def _write_title(ws, text: str, span: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    c = ws.cell(row=1, column=1, value=text)
    c.font = Font(size=15, bold=True, color=INK)
    c.alignment = CENTER
    c.fill = TITLE_FILL
    ws.row_dimensions[1].height = 30


def _style_header(ws, row: int, cols: int) -> None:
    for i in range(1, cols + 1):
        c = ws.cell(row=row, column=i)
        c.fill = HEAD_FILL
        c.font = Font(bold=True, color="FFFFFF", size=11)
        c.alignment = CENTER
        c.border = BOX
    ws.row_dimensions[row].height = 22


def sheet_daily(wb, data: dict) -> None:
    ws = wb.active
    ws.title = "گزارش روز"
    ws.sheet_view.rightToLeft = True
    headers = ["ردیف", "نام و نام خانوادگی", "شماره دانشجویی", "رشته", "وضعیت",
               "اولین ورود", "آخرین خروج", "مدت حضور", "رویداد مشکوک", "نمودار حضور ۱۴ روز اخیر"]
    widths = [6, 26, 15, 16, 12, 11, 11, 18, 12, 26]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    _write_title(ws, f"گزارش حضور و غیاب — {data['jalali']}", len(headers))
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(headers))
    sub = ws.cell(row=2, column=1, value=(
        f"حاضر: {len(data['present'])} نفر · غایب/بدون ورود: {len(data['absent'])} نفر · رویدادها: {len(data['events'])}"
        + (f" · ساعت مجاز: ورود {data['window_in']}، خروج {data['window_out']}" if data["enabled_hours"] else " · ساعت مجاز غیرفعال")
    ))
    sub.font = Font(size=10, color="6B7280")
    sub.alignment = RIGHT
    for i, h in enumerate(headers, start=1):
        ws.cell(row=3, column=i, value=h)
    _style_header(ws, 3, len(headers))
    ws.freeze_panes = "A4"

    r = 4
    for idx, rec in enumerate(data["present"] + data["absent"], start=1):
        vals = [idx, rec["full_name"], rec["student_no"], rec["major"], rec["state"],
                rec["first_in"], rec["last_out"], rec["duration"],
                rec["suspicious"] or "—", None]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BOX
            c.alignment = CENTER if i in (1, 3, 5, 6, 7, 9) else RIGHT
            c.font = Font(size=11)
        # نمودار متنی: هر بلوک = یک روز حضور در ۱۴ روز اخیر
        bar = ws.cell(row=r, column=10, value=f'=REPT("█",{max(rec["days14"], 0)}) & "  {rec["days14"]}/14 روز"')
        bar.alignment = RIGHT
        bar.font = Font(size=11, color="2F7D51" if rec["days14"] >= 7 else "96691F", bold=True)
        bar.border = BOX
        state_cell = ws.cell(row=r, column=5)
        if rec["state"] == "غایب":
            for i in range(1, len(headers) + 1):
                ws.cell(row=r, column=i).fill = ABSENT_FILL
            state_cell.font = Font(bold=True, color="A84949", size=11)
        elif rec["state"] == "حاضر":
            state_cell.font = Font(bold=True, color="2F7D51", size=11)
        else:
            state_cell.font = Font(bold=True, color="96691F", size=11)
        if rec["suspicious"]:
            sc = ws.cell(row=r, column=9)
            sc.fill = SUSP_FILL
            sc.font = Font(bold=True, color="A84949", size=11)
        r += 1

    if not data["present"] and not data["absent"]:
        ws.cell(row=4, column=1, value="هیچ دانشجویی ثبت نشده است")

    total_row = r + 1
    ws.cell(row=total_row, column=2, value="جمع").font = Font(bold=True)
    ws.cell(row=total_row, column=5, value=f"{len(data['present'])} حاضر / {len(data['absent'])} غایب").font = Font(bold=True)
    ws.cell(row=total_row, column=5).alignment = CENTER


def sheet_events(wb, data: dict) -> None:
    ws = wb.create_sheet("رویدادها")
    ws.sheet_view.rightToLeft = True
    headers = ["زمان", "نام", "شماره دانشجویی", "رویداد", "شباهت", "وضعیت ساعت"]
    for i, w in enumerate([20, 26, 15, 10, 10, 14], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    _write_title(ws, f"رویدادهای ثبت‌شده — {data['jalali']}", len(headers))
    for i, h in enumerate(headers, start=1):
        ws.cell(row=2, column=i, value=h)
    _style_header(ws, 2, len(headers))
    ws.freeze_panes = "A3"
    r = 3
    for e in data["events"]:
        vals = [e["logged_at"], e["full_name"], e["student_no"],
                "ورود" if e["event"] == "IN" else "خروج",
                round(e["similarity"], 3) if e["similarity"] else "—",
                "مشکوک" if e["status"] == "suspicious" else "مجاز"]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = BOX
            c.alignment = CENTER if i in (1, 4, 5, 6) else RIGHT
        if e["status"] == "suspicious":
            ws.cell(row=r, column=6).font = Font(bold=True, color="A84949")
            ws.cell(row=r, column=6).fill = ABSENT_FILL
        ws.cell(row=r, column=4).font = Font(bold=True, color="2F7D51" if e["event"] == "IN" else "3C6DA3")
        r += 1
    if not data["events"]:
        ws.cell(row=3, column=1, value="رویدادی برای این روز ثبت نشده است")


def sheet_charts(wb, data: dict) -> None:
    ws = wb.create_sheet("خلاصه و نمودارها")
    ws.sheet_view.rightToLeft = True
    _write_title(ws, f"نمودارهای {data['jalali']}", 8)
    kpis = [
        ("کل دانشجویان", len(data["present"]) + len(data["absent"])),
        ("حاضر", len(data["present"])),
        ("غایب / بدون ورود", len(data["absent"])),
        ("وردها", sum(1 for e in data["events"] if e["event"] == "IN")),
        ("خروج‌ها", sum(1 for e in data["events"] if e["event"] == "OUT")),
        ("رویدادهای مشکوک", sum(1 for e in data["events"] if e["status"] == "suspicious")),
    ]
    for i, (label, value) in enumerate(kpis):
        col = i + 1
        c = ws.cell(row=2, column=col, value=label)
        c.font = Font(size=9.5, color="6B7280")
        c.alignment = CENTER
        c.fill = TITLE_FILL
        v = ws.cell(row=3, column=col, value=value)
        v.font = Font(size=18, bold=True, color=INK)
        v.alignment = CENTER
    for i in range(1, 7):
        ws.column_dimensions[get_column_letter(i)].width = 15

    # بلوک داده نمودارها (ستون‌های H به بعد)
    data_row = 2
    ws.cell(row=data_row, column=9, value="ساعت ورود").font = Font(bold=True)
    ws.cell(row=data_row, column=10, value="تعداد").font = Font(bold=True)
    r = data_row + 1
    for h, n in data["hours"].items():
        ws.cell(row=r, column=9, value=h)
        ws.cell(row=r, column=10, value=n)
        r += 1
    hours_last = r - 1

    # بلوک روند باید بعد از بلندترین ردیف ساعت شروع شود، وگرنه روی داده ساعت‌ها می‌نویسد
    trend_start = max(data_row + 16, hours_last + 2)
    ws.cell(row=trend_start - 1, column=9, value="تاریخ").font = Font(bold=True)
    ws.cell(row=trend_start - 1, column=10, value="حاضر").font = Font(bold=True)
    ws.cell(row=trend_start - 1, column=11, value="غایب").font = Font(bold=True)
    for i, (label, pres, absent) in enumerate(data["trend"]):
        ws.cell(row=trend_start + i, column=9, value=label)
        ws.cell(row=trend_start + i, column=10, value=pres)
        ws.cell(row=trend_start + i, column=11, value=absent)
    trend_last = trend_start + len(data["trend"]) - 1

    pie_row = 6
    ws.cell(row=pie_row - 1, column=12, value="وضعیت").font = Font(bold=True)
    ws.cell(row=pie_row - 1, column=13, value="تعداد").font = Font(bold=True)
    ws.cell(row=pie_row, column=12, value="حاضر")
    ws.cell(row=pie_row, column=13, value=len(data["present"]))
    ws.cell(row=pie_row + 1, column=12, value="غایب")
    ws.cell(row=pie_row + 1, column=13, value=len(data["absent"]))

    for col in ("I", "J", "K", "L", "M"):
        ws.column_dimensions[col].hidden = True

    if hours_last >= data_row + 1:
        bar = BarChart()
        bar.type = "col"
        bar.title = "تردد ورود به تفکیک ساعت"
        bar.height, bar.width = 8, 16
        bar.legend = None
        bar.add_data(Reference(ws, min_col=10, min_row=data_row, max_row=hours_last), titles_from_data=True)
        bar.set_categories(Reference(ws, min_col=9, min_row=data_row + 1, max_row=hours_last))
        ws.add_chart(bar, "A6")

    trend = LineChart()
    trend.title = f"حضور و غیاب {TREND_DAYS} روز اخیر"
    trend.height, trend.width = 8.5, 24
    trend.add_data(Reference(ws, min_col=10, max_col=11, min_row=trend_start - 1, max_row=trend_last), titles_from_data=True)
    trend.set_categories(Reference(ws, min_col=9, min_row=trend_start, max_row=trend_last))
    ws.add_chart(trend, "A25")

    pie = PieChart()
    pie.title = "سهم حاضر و غایب"
    pie.height, pie.width = 8, 12
    pie.add_data(Reference(ws, min_col=13, min_row=pie_row - 1, max_row=pie_row + 1), titles_from_data=True)
    pie.set_categories(Reference(ws, min_col=12, min_row=pie_row, max_row=pie_row + 1))
    ws.add_chart(pie, "A44")


def build(day: date, *, dest: Path | None = None) -> Path:
    data = collect(day)
    wb = Workbook()
    sheet_daily(wb, data)
    sheet_events(wb, data)
    sheet_charts(wb, data)
    REPORTS_DIR.mkdir(exist_ok=True)
    path = dest or REPORTS_DIR / f"attendance_{day.isoformat()}.xlsx"
    wb.save(path)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ساخت فایل اکسل گزارش یک روز")
    parser.add_argument("--date", help="تاریخ میلادی YYYY-MM-DD (پیش‌فرض: امروز)")
    args = parser.parse_args()
    target = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    out = build(target)
    print(f"✅ فایل ساخته شد: {out}")
