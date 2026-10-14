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

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import database as db
import engine

PHOTOS_DIR = Path(__file__).parent / "photos"


def save_photo(student_id: int, frame) -> str | None:
    """بهترین فریم ثبت‌نام را به‌عنوان عکس پروفایل نگه می‌دارد تا در پنل دیده شود."""
    PHOTOS_DIR.mkdir(exist_ok=True)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        return None
    filename = f"student_{student_id}.jpg"
    (PHOTOS_DIR / filename).write_bytes(buf.tobytes())
    return filename


def collect_from_camera(shots: int, camera: int, angle_hints: list[str]) -> list[tuple]:
    cap = engine.open_camera(camera)
    samples: list[tuple] = []      # (embedding, frame, face_area)
    shot = 0
    print("از جلوی دوربین بنشینید. کلید: Space=بعدی (خودکار هم ثبت می‌شود) | ESC=لغو")
    while shot < shots:
        ok, frame = cap.read()
        if not ok:
            continue
        face = engine.capture_frame_for_enroll(frame)
        clean = frame.copy()       # عکس پروفایل بدون نوشته و کادر سبز ذخیره شود
        hint = angle_hints[shot] if shot < len(angle_hints) else ""
        cv2.putText(frame, f"Sample {shot + 1}/{shots}  {hint}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        if face is not None:
            x1, y1, x2, y2 = face.bbox.astype(int)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            samples.append((face.embedding, clean, float((x2 - x1) * (y2 - y1))))
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
    return samples


def collect_from_images(folder: Path) -> list[tuple]:
    samples: list[tuple] = []
    for p in sorted(folder.glob("*")):
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
        x1, y1, x2, y2 = face.bbox
        samples.append((face.embedding, frame, float((x2 - x1) * (y2 - y1))))
        print(f"  ثبت شد: {p.name}")
    return samples


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
        samples = collect_from_images(args.images)
    else:
        angles = ["center", "slightly left", "slightly right", "look at camera", "neutral", "natural"]
        samples = collect_from_camera(args.shots, args.camera, angles)

    if len(samples) < 3:
        sys.exit(f"کمتر از ۳ نمونه معتبر ({len(samples)}). با نور بهتر یا زوایای بیشتر دوباره تلاش کنید.")

    if not existing:
        student_id = db.add_student(args.name, args.code)
    else:
        db.update_student(student_id, {"full_name": args.name, "student_no": args.code})
    engine.add_embeddings(student_id, [emb for emb, _frame, _area in samples])
    best = max(samples, key=lambda s: s[2])[1]     # درشت‌ترین چهره = بهترین عکس پروفایل
    photo = save_photo(student_id, best)
    if photo:
        db.set_student_photo(student_id, photo)
    print(f"✅ {args.name} ({args.code}) با {len(samples)} نمونه ثبت شد. (student_id={student_id})"
          + (f" عکس پروفایل: photos/{photo}" if photo else ""))


if __name__ == "__main__":
    main()
