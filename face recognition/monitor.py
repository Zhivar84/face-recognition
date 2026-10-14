"""Live camera monitor: recognizes students and logs IN/OUT attendance.

Logic:
- IN   : logged when a known student is recognized and has no open session.
- OUT  : logged automatically after the student stays unseen for --absence-minutes,
         or immediately when --mode alternate and the student is seen again later.

Usage: python monitor.py [--camera 0] [--threshold 0.4] [--absence-minutes 15]
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import database as db
import engine


def run(camera: int, threshold: float, absence_minutes: float, fps_limit: float) -> None:
    db.init_db()
    students = {s["id"]: s for s in db.list_students()}
    if not students:
        sys.exit("هنوز دانشجویی ثبت نشده. اول enroll.py را اجرا کنید.")
    cap = engine.open_camera(camera)
    open_sessions: dict[int, float] = {}      # student_id -> last seen ts
    last_evt_at: dict[int, float] = {}
    toast = ""
    toast_until = 0.0
    cooldown = 60.0  # seconds between two events for the same student

    print("در حال اجرا... Q=خروج | S=اسنپ‌شات | R=گزارش روز در کنسول")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        now = time.time()
        for face in engine.detect_faces(frame):
            if face.embedding is None:
                continue
            student_id, score = engine.match(face.embedding, threshold)
            x1, y1, x2, y2 = face.bbox.astype(int)
            if student_id is None:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, f"UNKNOWN {score:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                continue

            s = students[student_id]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{s['full_name']} ({s['student_no']}) {score:.2f}",
                        (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
            open_sessions[student_id] = now

            last = db.last_event(student_id)
            is_open = last is not None and last["event"] == "IN"
            if not is_open and last_evt_at.get(student_id, 0) + cooldown < now:
                db.log_event(student_id, "IN", score)
                last_evt_at[student_id] = now
                open_sessions[student_id] = now
                suspect = db.classify_event("IN", datetime.now().strftime("%Y-%m-%d %H:%M:%S")) == "suspicious"
                toast = f"IN  {s['full_name']}  {datetime.now():%H:%M:%S}" + ("  [OUT-OF-HOURS]" if suspect else "")
                toast_until = now + 4
                print(f"[{datetime.now():%H:%M:%S}] ورود: {s['full_name']} ({s['student_no']}) sim={score:.2f}"
                      + ("  ⚠ خارج از ساعت مجاز — مشکوک" if suspect else ""))

        # auto OUT for students with an open session not seen for absence_minutes
        for student_id, seen in list(open_sessions.items()):
            last = db.last_event(student_id)
            if last is None or last["event"] != "IN":
                open_sessions.pop(student_id, None)
                continue
            if now - seen > absence_minutes * 60 and last_evt_at.get(student_id, 0) + cooldown < now:
                s = students[student_id]
                db.log_event(student_id, "OUT", None)
                last_evt_at[student_id] = now
                open_sessions.pop(student_id, None)
                toast = f"OUT {s['full_name']} {datetime.now():%H:%M:%S} (auto)"
                toast_until = now + 4
                suspect = db.classify_event("OUT", datetime.now().strftime("%Y-%m-%d %H:%M:%S")) == "suspicious"
                if suspect:
                    toast += "  [OUT-OF-HOURS]"
                print(f"[{datetime.now():%H:%M:%S}] خروج (غیبت طولانی): {s['full_name']} ({s['student_no']})"
                      + ("  ⚠ خارج از ساعت مجاز — مشکوک" if suspect else ""))

        cv2.putText(frame, f"Students: {len(students)}  Open: {len(open_sessions)}  Q=quit",
                    (15, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        if now < toast_until:
            color = (0, 255, 0) if toast.startswith("IN") else (255, 180, 0)
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), color, -1)
            cv2.putText(frame, toast, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
        cv2.imshow("Attendance Monitor", frame)
        key = cv2.waitKey(max(1, int(1000 / fps_limit))) & 0xFF
        if key in (ord('q'), 27):
            break
        if key == ord('s'):
            name = f"snapshot_{datetime.now():%Y%m%d_%H%M%S}.jpg"
            cv2.imwrite(name, frame)
            print(f"اسنپ‌شات ذخیره شد: {name}")
        if key == ord('r'):
            for row in db.daily_report(datetime.now().date()):
                print(dict(row))

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--threshold", type=float, default=0.4)
    parser.add_argument("--absence-minutes", type=float, default=15.0)
    parser.add_argument("--fps", type=float, default=8.0)
    args = parser.parse_args()
    run(args.camera, args.threshold, args.absence_minutes, args.fps)
