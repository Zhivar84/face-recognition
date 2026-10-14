"""Register a student's face into the gallery.

Usage:
    python enroll.py --name "Ali Rezaei" --code 9912345 [--camera 0] [--shots 6]
    python enroll.py --images photos/9912345 --name "Ali Rezaei" --code 9912345
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import database as db
import engine


def collect_from_camera(shots: int, camera: int, angle_hints: list[str]) -> list[np.ndarray]:
    cap = engine.open_camera(camera)
    embeddings: list[np.ndarray] = []
    shot = 0
    print("از جلوی دوربین بنشینید. کلید: Space=بعدی (خودکار هم ثبت می‌شود) | ESC=لغو")
    while shot < shots:
        ok, frame = cap.read()
        if not ok:
            continue
        face = engine.capture_frame_for_enroll(frame)
        hint = angle_hints[shot] if shot < len(angle_hints) else ""
        cv2.putText(frame, f"Sample {shot + 1}/{shots}  {hint}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        if face is not None:
            x1, y1, x2, y2 = face.bbox.astype(int)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            embeddings.append(face.embedding)
            shot += 1
            print(f"  نمونه {shot}/{shots} ثبت شد")
        else:
            cv2.putText(frame, "No clear face", (20, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.imshow("Enroll", frame)
        key = cv2.waitKey(200 if face is None else 700) & 0xFF
        if key == 27:
            cap.release()
            cv2.destroyAllWindows()
            sys.exit("لغو شد.")
    cap.release()
    cv2.destroyAllWindows()
    return embeddings


def collect_from_images(folder: Path) -> list[np.ndarray]:
    paths = sorted(folder.glob("*"))
    embeddings = []
    for p in paths:
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        frame = cv2.imread(str(p))
        if frame is None:
            print(f"  نادیده گرفته شد (خوانده نشد): {p.name}")
            continue
        face = engine.capture_frame_for_enroll(frame)
        if face is None:
            print(f"  نادیده گرفته شد (چهره واضح نیست): {p.name}")
            continue
        embeddings.append(face.embedding)
        print(f"  ثبت شد: {p.name}")
    return embeddings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="نام و نام خانوادگی (لاتین، برای نمایش روی ویدیو)")
    parser.add_argument("--code", required=True, help="شماره دانشجویی")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--shots", type=int, default=6)
    parser.add_argument("--images", type=Path, help="پوشه‌ای از عکس‌های دانشجو (به‌جای وب‌کم)")
    args = parser.parse_args()

    db.init_db()
    existing = db.get_student(args.code)
    if existing:
        print(f"دانشجو با شماره {args.code} قبلاً ثبت شده: {existing['full_name']}")
        ans = input("جایگزین شود؟ (y/n) ").strip().lower()
        if ans != "y":
            sys.exit("انصراف.")
        student_id = existing["id"]
        engine.remove_student(student_id)

    if args.images:
        embeddings = collect_from_images(args.images)
    else:
        angles = ["center", "slightly left", "slightly right", "look at camera", "neutral", "natural"]
        embeddings = collect_from_camera(args.shots, args.camera, angles)

    if len(embeddings) < 3:
        sys.exit(f"کمتر از ۳ نمونه معتبر ({len(embeddings)}). با نور بهتر یا زوایای بیشتر دوباره تلاش کنید.")

    if not existing:
        student_id = db.add_student(args.name, args.code)
    else:
        db.update_student(student_id, {"full_name": args.name, "student_no": args.code})
    engine.add_embeddings(student_id, embeddings)
    print(f"✅ {args.name} ({args.code}) با {len(embeddings)} نمونه ثبت شد. (student_id={student_id})")


if __name__ == "__main__":
    main()
