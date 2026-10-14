"""وب‌داشبورد حضور و غیاب چهره‌ای.

اجرا:  python dashboard.py  ->  http://127.0.0.1:8050
"""
from __future__ import annotations

import base64
import sys
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import cv2
import numpy as np
from flask import Flask, jsonify, make_response, request, send_from_directory

import database as db
import engine
import export

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024

PHOTOS_DIR = Path(__file__).parent / "photos"
REPORTS_DIR = Path(__file__).parent / "reports"

PAGE = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>داشبورد حضور و غیاب چهره‌ای</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/vazirmatn@33.0.3/misc/Farsi-Digits/Vazirmatn-FD-font-face.css">
<style>
  :root{
    --bg:#f5f7fa; --card:#ffffff; --ink:#1f2937; --muted:#8a94a3;
    --line:#e6eaf0; --soft:#f2f5f9;
    --green:#e9f5ee; --green-ink:#2f7d51; --green-dot:#3fa871;
    --red:#fbecec; --red-ink:#a84949;
    --amber:#fdf4e4; --amber-ink:#96691f;
    --blue:#eaf1f9; --blue-ink:#3c6da3;
    --radius:14px; --shadow:0 1px 2px rgba(16,24,40,.04),0 4px 14px rgba(16,24,40,.05);
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:Vazirmatn FD,Vazirmatn,Tahoma,'Segoe UI',sans-serif;font-size:14px}
  header{background:var(--card);border-bottom:1px solid var(--line);padding:14px 28px;
    display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;position:sticky;top:0;z-index:5}
  .brand{display:flex;align-items:center;gap:10px}
  .brand .dot{width:10px;height:10px;border-radius:50%;background:var(--green-dot);
    box-shadow:0 0 0 4px var(--green)}
  .brand h1{font-size:16px;font-weight:800;margin:0}
  .brand span{color:var(--muted);font-size:12px}
  .hgroup{display:flex;gap:12px;align-items:center}
  #clock{color:var(--muted);font-size:12.5px;direction:ltr;text-align:right}
  input[type=date]{font:inherit;font-size:13px;padding:7px 12px;border:1px solid var(--line);
    border-radius:10px;background:var(--card);color:var(--ink);box-shadow:var(--shadow)}
  main{max-width:1120px;margin:0 auto;padding:26px 20px;display:grid;gap:18px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
    padding:16px 18px;box-shadow:var(--shadow);display:flex;justify-content:space-between;align-items:center}
  .card .label{color:var(--muted);font-size:12px;margin-bottom:4px}
  .card .value{font-size:26px;font-weight:800;letter-spacing:-.5px}
  .ic{width:42px;height:42px;border-radius:12px;display:grid;place-items:center;flex-shrink:0}
  .ic svg{width:20px;height:20px}
  .ic.blue{background:var(--blue)} .ic.blue svg{stroke:var(--blue-ink)}
  .ic.green{background:var(--green)} .ic.green svg{stroke:var(--green-ink)}
  .ic.amber{background:var(--amber)} .ic.amber svg{stroke:var(--amber-ink)}
  .ic.red{background:var(--red)} .ic.red svg{stroke:var(--red-ink)}
  .grid2{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}
  @media(max-width:860px){.grid2{grid-template-columns:1fr}}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
    padding:18px 20px;box-shadow:var(--shadow)}
  .panel h2{font-size:14px;font-weight:800;margin:0 0 14px;display:flex;align-items:center;gap:8px}
  .panel h2 .count{background:var(--soft);border:1px solid var(--line);color:var(--muted);
    border-radius:999px;font-size:11.5px;padding:1px 9px;font-weight:600}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{padding:9px 10px;text-align:right;border-bottom:1px solid var(--soft)}
  tr:last-child td{border-bottom:none}
  th{color:var(--muted);font-weight:600;font-size:11.5px;background:var(--card)}
  tbody tr:hover{background:var(--soft)}
  td.num{direction:ltr;text-align:right;font-variant-numeric:tabular-nums}
  .chip{display:inline-flex;align-items:center;gap:5px;padding:2px 10px;border-radius:999px;
    font-size:11.5px;font-weight:600}
  .chip::before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}
  .chip.in{background:var(--green);color:var(--green-ink)}
  .chip.out{background:var(--red);color:var(--red-ink)}
  .chip.absent{background:var(--amber);color:var(--amber-ink)}
  .person{display:flex;align-items:center;gap:12px;padding:10px 4px;border-bottom:1px solid var(--soft)}
  .person:last-child{border-bottom:none}
  .avatar{width:38px;height:38px;border-radius:50%;display:grid;place-items:center;
    font-weight:800;font-size:15px;background:var(--blue);color:var(--blue-ink);flex-shrink:0}
  .person .meta{flex:1;min-width:0}
  .person .name{font-weight:700;font-size:13.5px}
  .person .sub{color:var(--muted);font-size:11.5px;direction:ltr;text-align:right}
  .pulse{width:8px;height:8px;border-radius:50%;background:var(--green-dot);position:relative;flex-shrink:0}
  .pulse::after{content:'';position:absolute;inset:-4px;border-radius:50%;background:var(--green);
    animation:p 2s ease-out infinite}
  @keyframes p{0%{transform:scale(.6);opacity:1}100%{transform:scale(1.6);opacity:0}}
  .chart{display:flex;align-items:flex-end;gap:6px;height:120px;padding-top:6px}
  .col{flex:1;height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;gap:5px;min-width:0}
  .col .bar{width:100%;max-width:26px;border-radius:6px 6px 3px 3px;background:var(--blue);
    border:1px solid #d9e5f3;transition:height .4s ease}
  .col.hot .bar{background:var(--green);border-color:#cfe7d9}
  .col small{color:var(--muted);font-size:10px;direction:ltr}
  .empty{color:var(--muted);font-size:13px;text-align:center;padding:26px 0;line-height:2}
  .empty b{display:block;font-size:13.5px;color:var(--ink)}
  .legend{display:flex;gap:16px;color:var(--muted);font-size:11.5px;margin-top:10px}
  .legend i{width:10px;height:10px;border-radius:3px;display:inline-block;margin-left:5px}
  .btn{font:inherit;font-size:13px;font-weight:600;border:1px solid var(--line);background:var(--card);
    color:var(--ink);border-radius:10px;padding:8px 16px;cursor:pointer;box-shadow:var(--shadow)}
  .btn:hover{border-color:#cfd8e3}
  .btn.primary{background:var(--green-ink);border-color:var(--green-ink);color:#fff}
  .btn.primary:hover{background:#276b45}
  .btn.tiny{padding:4px 11px;font-size:12px;border-radius:8px;box-shadow:none}
  .btn.danger{color:var(--red-ink);background:var(--red);border-color:#f2d9d9}
  td.act{white-space:nowrap}
  td.act .btn{margin-left:6px}
  .backdrop{position:fixed;inset:0;background:rgba(15,23,42,.45);display:none;place-items:center;z-index:20;padding:20px}
  .backdrop.on{display:grid}
  .modal{background:var(--card);border-radius:var(--radius);box-shadow:0 20px 50px rgba(16,24,40,.25);
    width:min(460px,100%);padding:22px 24px;max-height:calc(100vh - 40px);overflow:auto}
  .modal h3{margin:0 0 4px;font-size:15.5px;font-weight:800}
  .modal .hint{margin:0 0 16px;color:var(--muted);font-size:12px;line-height:1.8}
  .field{margin-bottom:12px}
  .field label{display:block;color:var(--muted);font-size:11.5px;font-weight:600;margin-bottom:5px}
  .field input{width:100%;font:inherit;font-size:13.5px;padding:9px 12px;border:1px solid var(--line);
    border-radius:10px;background:var(--soft);color:var(--ink)}
  .field input:focus{outline:none;border-color:var(--green-dot);background:var(--card)}
  .field input.ltr{direction:ltr;text-align:left}
  .modal .row{display:flex;gap:10px;margin-top:18px}
  .modal .row .btn{flex:1}
  .toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:var(--ink);color:#fff;
    padding:10px 20px;border-radius:999px;font-size:13px;z-index:30;opacity:0;transition:.3s;pointer-events:none}
  .toast.on{opacity:1}
  .toast.bad{background:var(--red-ink)}
  .offline{display:none;background:var(--red);color:var(--red-ink);padding:9px 14px;border-radius:10px;
    font-size:13px;font-weight:600;text-align:center}
  .offline.on{display:block}
  .chip.ok{background:var(--soft);color:var(--muted)}
  .chip.susp{background:var(--red);color:var(--red-ink)}
  tr.susp td{background:#fdf1f1}
  .daybox{position:relative;display:flex;flex-direction:column;gap:3px;align-items:stretch}
  .daybtn{font:inherit;font-size:13px;font-weight:600;padding:7px 14px;border:1px solid var(--line);
    border-radius:10px;background:var(--card);color:var(--ink);box-shadow:var(--shadow);cursor:pointer;
    display:flex;align-items:center;gap:8px;white-space:nowrap}
  .daybtn:hover{border-color:#cfd8e3}
  .daybtn::after{content:'▾';color:var(--muted);font-size:11px}
  .cal{position:absolute;top:calc(100% + 8px);left:0;z-index:30;background:var(--card);
    border:1px solid var(--line);border-radius:14px;box-shadow:0 14px 36px rgba(16,24,40,.2);
    padding:12px 14px;min-width:262px;display:none}
  .cal.on{display:block}
  .cal-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;
    font-weight:800;font-size:13px}
  .cal-head button{font:inherit;border:1px solid var(--line);background:var(--card);border-radius:8px;
    padding:2px 9px;cursor:pointer;color:var(--ink)}
  .cal-head button:hover{background:var(--soft)}
  .cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
  .cal-grid .wd{color:var(--muted);font-size:10.5px;text-align:center;padding:3px 0;font-weight:600}
  .cal-grid button{font:inherit;font-size:12.5px;border:none;background:transparent;color:var(--ink);
    border-radius:8px;padding:5px 0;cursor:pointer;font-variant-numeric:tabular-nums}
  .cal-grid button:hover{background:var(--soft)}
  .cal-grid button.sel{background:var(--green-ink);color:#fff;font-weight:700}
  .cal-grid button.today{box-shadow:inset 0 0 0 1px var(--green-dot)}
  .cal-foot{margin-top:9px;text-align:left}
  .cal-foot button{font:inherit;font-size:12px;font-weight:600;border:1px solid var(--line);background:var(--soft);
    color:var(--blue-ink);border-radius:8px;padding:4px 12px;cursor:pointer}
  .sub-fa{color:var(--muted);font-weight:600;font-size:12px}
  .hours{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end}
  .hfield label{display:block;color:var(--muted);font-size:11.5px;font-weight:600;margin-bottom:4px}
  .hfield input,.switch input{font:inherit}
  .hfield input{font-size:13px;padding:7px 10px;border:1px solid var(--line);border-radius:10px;
    background:var(--soft);color:var(--ink);direction:ltr}
  .hfield input:focus{outline:none;border-color:var(--green-dot);background:var(--card)}
  .switch{display:flex;gap:7px;align-items:center;font-size:13px;font-weight:700;
    background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:8px 12px;height:36px;cursor:pointer}
  .panel .hint{color:var(--muted);font-size:12px;margin:12px 0 0;line-height:1.9}
  .drop{display:flex;gap:14px;align-items:center;border:1px dashed #cfd8e3;border-radius:14px;
    background:var(--soft);padding:12px;transition:.2s}
  .drop.over{border-color:var(--green-dot);background:#eef7f1}
  .preview{width:104px;height:104px;border-radius:14px;border:1px solid var(--line);background:var(--card);
    display:grid;place-items:center;overflow:hidden;flex-shrink:0;color:var(--muted);font-size:11px;text-align:center;padding:4px;
    position:relative}
  .preview img{width:100%;height:100%;object-fit:cover;display:block}
  .preview .badge{position:absolute;bottom:0;right:0;left:0;background:rgba(15,23,42,.72);color:#fff;
    font-size:10.5px;padding:3px 0;text-align:center}
  .pbtns{display:flex;flex-direction:column;gap:7px;flex:1}
  .pbtns .btn{width:100%}
  .pnote{color:var(--muted);font-size:11.5px;margin:8px 0 0;line-height:1.8}
  .fstat{display:none;align-items:center;gap:8px;font-size:12px;font-weight:700;border-radius:10px;
    padding:8px 11px;margin:10px 0 0;line-height:1.6}
  .fstat.on{display:flex}
  .fstat i{width:9px;height:9px;border-radius:50%;background:currentColor;flex-shrink:0}
  .fstat.ok{background:var(--green);color:var(--green-ink)}
  .fstat.warn{background:var(--amber);color:var(--amber-ink)}
  .fstat.bad{background:var(--red);color:var(--red-ink)}
  .fstat.busy{background:var(--blue);color:var(--blue-ink)}
  .thumb{width:32px;height:32px;border-radius:9px;object-fit:cover;display:block;background:var(--soft)}
  td.pic{width:44px}
  .cammodal{width:min(560px,100%)}
  .camstage{position:relative}
  #camVideo,#camShotImg{width:100%;max-height:56vh;background:#0f172a;border-radius:12px;display:block;
    aspect-ratio:4/3;object-fit:cover}
  #camShotImg{display:none}
  .camstage.on-shot #camVideo{display:none}
  .camstage.on-shot #camShotImg{display:block}
  .guide{position:absolute;inset:0;pointer-events:none;display:grid;place-items:center}
  .guide span{width:52%;aspect-ratio:3/4;border:2px dashed rgba(255,255,255,.75);border-radius:50%}
  .camstage.on-shot .guide{display:none}
  #camVideo{transform:scaleX(-1)}
  .camhint{margin:0 0 10px;color:var(--muted);font-size:12px;line-height:1.8;min-height:20px}
  .camstep{margin:0 0 8px;font-size:12.5px;font-weight:700;line-height:1.8}
  .camstep b{font-size:13.5px}
  .pose{position:absolute;top:8px;right:8px;left:8px;text-align:center;pointer-events:none;
    background:rgba(15,23,42,.82);color:#fff;font-size:15px;font-weight:700;padding:9px 12px;
    border-radius:10px;line-height:1.7}
  .camstage.on-shot .pose{display:none}
  .shots{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
  .shots:empty{display:none}
  .shot{width:76px;font-size:10.5px;color:var(--muted);text-align:center;line-height:1.6}
  .shot img{width:76px;height:57px;object-fit:cover;border-radius:9px;display:block;border:2px solid var(--line)}
  .shot.good img{border-color:#2fae6b}
  .shot.bad img{border-color:#e05b5b}
  .camrow{display:flex;gap:8px;margin-top:12px}
  .camrow .btn{flex:1}
  .live{position:absolute;bottom:8px;right:8px;display:flex;align-items:center;gap:7px;
    background:rgba(15,23,42,.82);color:#fff;font-size:11.5px;font-weight:700;padding:5px 11px;border-radius:999px}
  .live i{width:9px;height:9px;border-radius:50%;background:#ff5a5a;animation:blink 1.1s infinite}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
  .dots{display:flex;gap:6px;justify-content:center;margin:4px 0 12px;flex-wrap:wrap}
  .dots b{display:flex;flex-direction:column;align-items:center;gap:5px;font-size:10.5px;
    font-weight:600;color:var(--muted);flex:1;min-width:68px}
  .dots b i{width:100%;height:5px;border-radius:999px;background:var(--line);display:block}
  .dots b.done{color:var(--green-ink)} .dots b.done i{background:#2fae6b}
  .dots b.cur{color:var(--blue-ink)} .dots b.cur i{background:var(--blue)}
  .autoline{display:flex;align-items:flex-start;gap:7px;font-size:11.5px;color:var(--muted);
    margin-top:10px;line-height:1.7;cursor:pointer}
  .autoline input{margin-top:2px}
  .files{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
  .files a{font-size:12px;font-weight:600;color:var(--blue-ink);background:var(--blue);
    border:1px solid #d7e5f3;border-radius:9px;padding:5px 11px;text-decoration:none;direction:ltr}
  .files a:hover{background:#dceaf7}
  .files .none{color:var(--muted);font-size:12px;font-weight:400}
  .switch input{width:15px;height:15px}
</style>
</head>
<body>
<header>
  <div class="brand">
    <span class="dot"></span>
    <div><h1>حضور و غیاب چهره‌ای</h1><span>دانشگاه — ورود خودکار با دوربین</span></div>
  </div>
  <div class="hgroup">
    <button class="btn primary" onclick="openModal()">+ افزودن دانشجو</button>
    <div class="daybox">
      <input type="hidden" id="day">
      <button class="daybtn" id="dayBtn" type="button" onclick="toggleCal(event)">—</button>
      <div class="cal" id="cal" onclick="event.stopPropagation()"></div>
    </div>
    <span id="clock"></span>
  </div>
</header>
<main>
  <div class="offline" id="offline">اتصال به سرور قطع است — با `.venv\\Scripts\\python dashboard.py` دوباره اجرا کنید</div>
  <section class="cards" id="cards"></section>
  <section class="grid2">
    <div class="panel">
      <h2>الان داخل هستند <span class="count" id="insideCount">—</span></h2>
      <div id="inside"></div>
    </div>
    <div class="panel">
      <h2>نمای ساعتی ورود</h2>
      <div class="chart" id="chart"></div>
      <div class="legend"><span><i style="background:var(--green)"></i>بیشترین تردد</span>
        <span><i style="background:var(--blue)"></i>سایر ساعت‌ها</span></div>
    </div>
  </section>
  <section class="panel">
    <h2>ساعت مجاز ورود و خروج <span class="sub-fa" id="hoursState">—</span></h2>
    <div class="hours">
      <label class="switch"><input type="checkbox" id="hEnabled"> فعال‌سازی</label>
      <div class="hfield"><label>ورود از</label><input type="time" id="hInStart"></div>
      <div class="hfield"><label>ورود تا</label><input type="time" id="hInEnd"></div>
      <div class="hfield"><label>خروج از</label><input type="time" id="hOutStart"></div>
      <div class="hfield"><label>خروج تا</label><input type="time" id="hOutEnd"></div>
      <button class="btn primary" onclick="saveHours()">ذخیره ساعت‌ها</button>
    </div>
    <p class="hint">هر رویداد بیرون از این بازه‌ها «مشکوک» علامت می‌خورد. بازه‌ای که از نیمه‌شب می‌گذرد هم پشتیبانی می‌شود (مثلاً ۲۲:۰۰ تا ۰۲:۰۰). این تنظیم روی رویدادهای ثبت‌شده هم اعمال می‌شود.</p>
  </section>
  <section class="panel">
    <h2>رویدادهای روز <span class="sub-fa" id="evtDay"></span><span class="count" id="evtCount">—</span></h2>
    <div id="events"></div>
  </section>
  <section class="panel">
    <h2>گزارش اکسل آخر شب <span class="sub-fa" id="eodState">—</span></h2>
    <div class="hours">
      <label class="switch"><input type="checkbox" id="eodEnabled"> ساخت خودکار</label>
      <div class="hfield"><label>ساعت</label><input type="time" id="eodTime"></div>
      <button class="btn primary" onclick="saveEod()">ذخیره</button>
      <button class="btn" onclick="makeNow(event)">ساخت فایل همین الان</button>
    </div>
    <p class="hint">در ساعت انتخابی، فایل <span style="direction:ltr;display:inline-block">reports/attendance_…xlsx</span> همان روز ساخته می‌شود: لیست حاضر و غایب، ساعت ورود/خروج، مدت حضور، رویدادهای مشکوک و نمودار حضور ۱۴ روز اخیر کنار هر نفر. اگر آن ساعت سیستم خاموش بود، در اولین اجرا بعد از آن جبران می‌شود — ولی داشبورد باید در ساعت مقرر در حال اجرا باشد.</p>
    <div class="files" id="reports"></div>
  </section>
  <section class="panel">
    <h2>تست تشخیص چهره <span class="sub-fa">با عکس یا ویدیوی خودتان بررسی کنید سیستم چه کسی را می‌شناسد</span></h2>
    <div class="drop" id="testDrop">
      <div class="preview" id="testPreview">بدون عکس</div>
      <div class="pbtns">
        <button type="button" class="btn tiny" onclick="document.getElementById('tFile').click()">انتخاب فایل (عکس یا ویدیو)</button>
        <button type="button" class="btn tiny" onclick="openCam('test')">ضبط زنده با وب‌کم</button>
        <button type="button" class="btn primary" id="tRun" onclick="runTest()">تست تشخیص با این عکس</button>
        <input type="file" id="tFile" accept="image/*,video/*" hidden onchange="pickTest(this)">
        <label class="hfield" style="margin-top:2px"><label>آستانه تشخیص (پیش‌فرض ۰.۴۰)</label>
          <input type="number" id="tThr" min="0.05" max="0.95" step="0.05" value="0.40"></label>
      </div>
    </div>
    <p class="fstat" id="tStat"><i></i><span id="tStatText"></span></p>
    <p class="pnote">این تست همان مسیری است که <span style="direction:ltr;display:inline-block">monitor.py</span> می‌رود: چهره در عکس پیدا می‌شود، بردار ۵۱۲بعدی ساخته می‌شود و با گالری <span style="direction:ltr;display:inline-block">data/embeddings.npz</span> مقایسه می‌شود. اگر اینجا شما را نشناسد، در دوربین زنده هم شما را نمی‌شناسد. با وب‌کم می‌توانید چهار حالت چهره را به‌صورت زنده تست کنید؛ نتیجه هر حالت جداگانه نشان داده می‌شود.</p>
    <div class="hours" style="margin-top:12px">
      <button class="btn" onclick="checkGallery()">اعتبارسنجی گالری (همه دانشجویان)</button>
    </div>
    <div id="galleryCheck"></div>
  </section>
  <section class="panel">
    <h2>گالری چهره‌ها و اطلاعات دانشجویان <span class="count" id="stCount">—</span></h2>
    <div id="students"></div>
  </section>
</main>
<div class="backdrop" id="backdrop" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <h3 id="mTitle">افزودن دانشجو</h3>
    <p class="hint" id="mHint">نام و شماره دانشجویی الزامی است. شماره دانشجویی باید یکتا باشد.</p>
    <form id="stForm" onsubmit="return saveStudent(event)">
      <input type="hidden" id="fId">
      <div class="field"><label for="fName">نام و نام خانوادگی *</label>
        <input id="fName" required placeholder="مثلاً علی رضایی"></div>
      <div class="field"><label for="fNo">شماره دانشجویی *</label>
        <input id="fNo" class="ltr" required placeholder="9912345"></div>
      <div class="field"><label for="fMajor">رشته تحصیلی</label>
        <input id="fMajor" placeholder="نرم‌افزار"></div>
      <div class="field"><label for="fEmail">ایمیل</label>
        <input id="fEmail" class="ltr" type="email" placeholder="ali@uni.ac.ir"></div>
      <div class="field"><label for="fPhone">شماره تماس</label>
        <input id="fPhone" class="ltr" type="tel" placeholder="09120000000"></div>
      <div class="field">
        <label>عکس یا ویدیوی دانشجو</label>
        <div class="drop" id="drop">
          <div class="preview" id="preview">بدون عکس</div>
          <div class="pbtns">
            <button type="button" class="btn tiny" onclick="document.getElementById('fFile').click()">۱. انتخاب فایل (عکس یا ویدیو)</button>
            <button type="button" class="btn tiny" onclick="openCam('form')">۲. ضبط زنده با وب‌کم (۴ حالت چهره)</button>
            <button type="button" class="btn tiny danger" id="pClear" onclick="clearPhoto()">حذف عکس</button>
            <input type="file" id="fFile" accept="image/*,video/*" hidden onchange="pickFile(this)">
          </div>
        </div>
        <div class="shots" id="formShots"></div>
        <p class="fstat" id="fstat"><i></i><span id="fstatText"></span></p>
        <p class="pnote" id="pNote">عکس یا ویدیو را اینجا بکشید (drag &amp; drop) یا از دکمه‌ها استفاده کنید. از ویدیو چند فریم برداشته می‌شود و فقط فریم‌های با چهره واضح به گالری می‌روند. در «ضبط زنده با وب‌کم» چهار حالت چهره با راهنمای روی صفحه گرفته می‌شود (رو به دوربین، کمی چپ، کمی راست، کمی بالا) و هر چهار بردار ثبت می‌شود — تشخیص با دوربین دقیق‌تر می‌شود.</p>
      </div>
      <div class="row">
        <button type="submit" class="btn primary" id="mSave">ذخیره</button>
        <button type="button" class="btn" onclick="closeModal()">انصراف</button>
      </div>
    </form>
  </div>
</div>
<div class="backdrop" id="camBackdrop" onclick="if(event.target===this)closeCam()">
  <div class="modal cammodal">
    <h3 id="camTitle">ضبط چهره با وب‌کم</h3>
    <div class="dots" id="camDots"></div>
    <p class="camstep" id="camStep"></p>
    <div class="camstage" id="camStage">
      <video id="camVideo" playsinline muted></video>
      <img id="camShotImg" alt="آخرین نمونه ثبت‌شده">
      <div class="guide"><span></span></div>
      <div class="pose" id="camPose"></div>
      <div class="live" id="camLiveBadge"><i></i><span>بررسی زنده چهره</span></div>
    </div>
    <p class="fstat" id="camStat"><i></i><span id="camStatText"></span></p>
    <div class="shots" id="camShots"></div>
    <p class="camhint" id="camHint">در حال راه‌اندازی دوربین…</p>
    <div class="camrow" id="camLive">
      <button type="button" class="btn primary" id="camShotBtn" onclick="captureManual()" disabled>ثبت همین حالا</button>
      <button type="button" class="btn" id="camSkipBtn" onclick="skipStep()" disabled>رد کردن این مرحله</button>
      <button type="button" class="btn" id="camDoneBtn" onclick="finishCam()" disabled>پایان و استفاده</button>
      <button type="button" class="btn" onclick="closeCam()">انصراف</button>
    </div>
    <label class="autoline"><input type="checkbox" id="camAuto" checked onchange="toggleAuto()">
      ثبت خودکار: هر حالت به‌محض اینکه چهره واضح و در زاویه خواسته بیاید گرفته می‌شود و مرحله بعد شروع می‌شود. با خاموش کردنش خودتان با «ثبت همین حالا» نمونه می‌گیرید.</label>
  </div>
</div>
<canvas id="upCanvas" hidden></canvas>
<div class="toast" id="toast"></div>
<script>
const IC = {
  users:'<svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-1a4 4 0 0 0-4-4h-4a4 4 0 0 0-4 4v1M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8m8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6M3 20v-1a4 4 0 0 1 4-4h2"/></svg>',
  in:'<svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 11l3-3m0 0l-3-3m3 3H9m4 11h6a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2h-6"/></svg>',
  out:'<svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4m7 14l5-5m0 0l-5-5m5 5H9"/></svg>',
  home:'<svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 0 0 1 1h3v-6h6v6h3a1 1 0 0 0 1-1V10"/></svg>',
  alert:'<svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4m0 3h.01M10.3 4L2.7 17a2 2 0 0 0 1.7 3h15.2a2 2 0 0 0 1.7-3L13.7 4a2 2 0 0 0-3.4 0z"/></svg>'
};
const fmt = n => new Intl.NumberFormat('fa-IR').format(n);
const faDate = (d, o) => {
  const parts = new Intl.DateTimeFormat('fa-IR-u-ca-persian', o).formatToParts(d);
  const get = t => (parts.find(p => p.type === t) || {}).value || '';
  return [get('weekday'), get('day'), get('month'), get('year')].filter(Boolean).join(' ');
};
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function chip(t, cls){ return `<span class="chip ${cls}">${t}</span>`; }
function card(ic, cls, label, value){
  return `<div class="card"><div><div class="label">${label}</div><div class="value">${value}</div></div>
    <div class="ic ${cls}">${IC[ic]}</div></div>`;
}
function avatar(name){
  const ch = name.trim()[0] || '؟';
  const hues = [['var(--blue)','var(--blue-ink)'],['var(--green)','var(--green-ink)'],['var(--amber)','var(--amber-ink)']];
  const h = hues[[...name].reduce((a,c)=>a+c.charCodeAt(0),0) % hues.length];
  return `<div class="avatar" style="background:${h[0]};color:${h[1]}">${esc(ch)}</div>`;
}
function photoTag(p, size){
  if (p.photo) return `<img class="thumb" style="width:${size}px;height:${size}px" src="/photo/${p.id}?v=${p.photo_v}" alt="">`;
  return avatar(p.full_name);
}
async function j(u){ const r = await fetch(u); return r.json(); }
function tick(){
  const d = new Date();
  document.getElementById('clock').textContent =
    d.toLocaleTimeString('fa-IR') + ' • ' + faDate(d, {weekday:'long', day:'numeric', month:'long', year:'numeric'});
}
function renderChart(rows){
  const buckets = {};
  rows.filter(r => r.event === 'IN').forEach(r => {
    const h = r.logged_at.slice(11, 13);
    buckets[h] = (buckets[h] || 0) + 1;
  });
  const hours = Object.keys(buckets).sort();
  if (!hours.length){ document.getElementById('chart').innerHTML =
    '<div class="empty" style="margin:auto">ورودی برای رسم نمودار نیست</div>'; return; }
  const max = Math.max(...hours.map(h => buckets[h]));
  document.getElementById('chart').innerHTML = hours.map(h => `
    <div class="col ${buckets[h] === max ? 'hot' : ''}">
      <div class="bar" style="height:${18 + 82 * buckets[h] / max}%"></div>
      <small>${h}</small>
    </div>`).join('');
}
async function refresh(){
  const day = document.getElementById('day').value;
  let s, rows, st;
  try {
    [s, rows, st] = await Promise.all([
      j(`/api/summary?date=${day}`), j(`/api/events?date=${day}`), j('/api/students')
    ]);
    document.getElementById('offline').classList.remove('on');
  } catch {
    document.getElementById('offline').classList.add('on');
    return;
  }
  const gSel = utcDay(...day.split('-').map(Number));
  document.getElementById('evtDay').textContent = '— ' + jalLabel(gSel, false);
  document.getElementById('cards').innerHTML =
    card('users','blue','دانشجویان ثبت‌نام‌شده', fmt(s.students)) +
    card('in','green','ورودهای امروز', fmt(s.ins)) +
    card('out','amber','خروج‌های امروز', fmt(s.outs)) +
    card('home','red','الان داخل هستند', fmt(s.inside.length)) +
    card('alert','red','خارج از ساعت مجاز', fmt(s.suspicious));
  document.getElementById('insideCount').textContent = fmt(s.inside.length);
  document.getElementById('inside').innerHTML = s.inside.length
    ? s.inside.map(p => `<div class="person">${avatar(p.name)}
        <div class="meta"><div class="name">${esc(p.name)}</div><div class="sub">${esc(p.code)}</div></div>
        <span class="pulse"></span><span class="sub num" style="color:var(--muted)">${p.last_in}</span></div>`).join('')
    : `<div class="empty"><b>فعلاً کسی داخل نیست</b>برای شروع، monitor.py را اجرا کنید</div>`;
  renderChart(rows);
  document.getElementById('evtCount').textContent = fmt(rows.length);
  document.getElementById('events').innerHTML = rows.length
    ? `<table><thead><tr><th>نام</th><th>شماره</th><th>اتفاق</th><th>ساعت</th><th>شباهت</th><th>وضعیت ساعت</th></tr></thead><tbody>` +
      rows.map(r => `<tr class="${r.status === 'suspicious' ? 'susp' : ''}"><td>${esc(r.full_name)}</td><td class="num">${esc(r.student_no)}</td>
        <td>${chip(r.event === 'IN' ? 'ورود' : 'خروج', r.event === 'IN' ? 'in' : 'out')}</td>
        <td class="num">${r.logged_at.slice(11)}</td>
        <td class="num">${r.similarity ? r.similarity.toFixed(2) : '—'}</td>
        <td>${r.status === 'suspicious' ? chip('مشکوک', 'susp') : chip('مجاز', 'ok')}</td></tr>`).join('') + `</tbody></table>`
    : `<div class="empty"><b>رکوردی برای این روز نیست</b>اول enroll و بعد monitor را اجرا کنید</div>`;
  STUDENTS = st;
  document.getElementById('stCount').textContent = fmt(st.length);
  document.getElementById('students').innerHTML = st.length
    ? `<table><thead><tr><th>عکس</th><th>نام</th><th>شماره</th><th>رشته</th><th>تماس</th><th>نمونه چهره</th><th>وضعیت امروز</th><th>عملیات</th></tr></thead><tbody>` +
      st.map(p => `<tr><td class="pic">${photoTag(p, 32)}</td><td>${esc(p.full_name)}</td><td class="num">${esc(p.student_no)}</td>
        <td>${esc(p.major || '—')}</td>
        <td class="num">${esc(p.phone || p.email || '—')}</td>
        <td class="num">${p.samples ? fmt(p.samples) : chip('۰ — قابل شناسایی نیست', 'susp')}</td>
        <td>${p.inside ? chip('داخل', 'in') : chip('خارج/غایب', 'absent')}</td>
        <td class="act"><button class="btn tiny" onclick="openModal(${p.id})">ویرایش</button>
          <button class="btn tiny danger" onclick="delStudent(${p.id})">حذف</button></td></tr>`).join('') + `</tbody></table>`
    : `<div class="empty"><b>گالری خالی است</b>با دکمه «افزودن دانشجو» یا enroll.py اولین دانشجو را ثبت کنید</div>`;
}
let STUDENTS = [];
function toast(msg, bad){
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast on' + (bad ? ' bad' : '');
  setTimeout(() => { t.className = 'toast'; }, 2800);
}
async function req(url, method, body){
  let r;
  try {
    r = await fetch(url, { method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined });
  } catch { throw new Error('سرور در دسترس نیست — dashboard.py در حال اجراست؟'); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `خطای سرور (${r.status})`);
  return d;
}
function openModal(id){
  const p = id ? STUDENTS.find(x => x.id === id) : null;
  document.getElementById('mTitle').textContent = p ? 'ویرایش اطلاعات دانشجو' : 'افزودن دانشجو';
  document.getElementById('mHint').textContent = p
    ? 'تغییرات فوراً در دیتابیس ذخیره می‌شود. عکس جدید به نمونه‌های چهره افزوده می‌شود؛ برای جایگزینی کامل چهره از enroll.py استفاده کنید.'
    : 'نام و شماره دانشجویی الزامی است؛ شماره دانشجویی باید یکتا باشد. عکس اختیاری است ولی تشخیص خودکار را ممکن می‌کند.';
  document.getElementById('fId').value = p ? p.id : '';
  document.getElementById('fName').value = p ? p.full_name : '';
  document.getElementById('fNo').value = p ? p.student_no : '';
  document.getElementById('fMajor').value = p ? (p.major || '') : '';
  document.getElementById('fEmail').value = p ? (p.email || '') : '';
  document.getElementById('fPhone').value = p ? (p.phone || '') : '';
  document.getElementById('fFile').value = '';
  photoData = null; photoExtras = []; photoRemove = false; existingPhoto = !!(p && p.photo);
  paintPreview(p ? { id: p.id, v: p.photo_v } : null);
  setFStat('fstat', null);
  document.getElementById('backdrop').classList.add('on');
  document.getElementById('fName').focus();
}
function closeModal(){
  document.getElementById('backdrop').classList.remove('on');
  document.getElementById('fFile').value = '';
  photoData = null; photoExtras = [];
  setFStat('fstat', null);
}
/* ---------- عکس دانشجو: آپلود فایل یا گرفتن با دوربین ---------- */
let photoData = null;        // data URL عکس انتخاب‌شده (هنوز ذخیره نشده)
let photoExtras = [];        // حالت‌های اضافه چهره از وب‌کم (بردارهای بیشتر)
let photoRemove = false;     // درخواست حذف عکس ذخیره‌شده
let existingPhoto = false;
let faceCheckTimer = null;
const FSTAT_MSG = {
  ok: 'چهره واضح و رو به دوربین پیدا شد — با «ذخیره» این دانشجو با دوربین شناسایی می‌شود.',
  small: 'چهره در عکس خیلی کوچک است. عکس نزدیک‌تر/کلوزآپ از صورت بفرستید (صورت حداقل یک‌سوم عرض کادر).',
  weak: 'چهره نصفه‌رو، تار یا در نور ضعیف است. تمام‌رخ و رو به دوربین عکس بگیرید.',
  noface: 'چهره‌ای در این تصویر پیدا نشد. عکس دیگری بفرستید یا با وب‌کم بگیرید.',
  error: 'بررسی چهره انجام نشد (dashboard را دوباره اجرا کنید). عکس ذخیره می‌شود ولی شاید شناسایی کار نکند.'
};
function setFStat(prefix, kind, text){
  const box = document.getElementById(prefix);
  const span = document.getElementById(prefix + 'Text');
  if (!kind){ box.className = 'fstat'; box.style.display = 'none'; return; }
  box.style.display = '';
  box.className = 'fstat on ' + kind;
  span.textContent = text || FSTAT_MSG[kind] || '';
}
function paintPreview(saved){
  const box = document.getElementById('preview');
  const clear = document.getElementById('pClear');
  if (photoData){
    box.innerHTML = `<img src="${photoData}" alt="پیش‌نمایش عکس">`;
    clear.style.display = '';
    return;
  }
  if (saved && existingPhoto && !photoRemove){
    box.innerHTML = `<img src="/photo/${saved.id}?v=${saved.v}" alt="عکس فعلی"><div class="badge">عکس فعلی</div>`;
    clear.style.display = '';
    return;
  }
  box.textContent = 'بدون عکس';
  clear.style.display = 'none';
}
async function probeFace(dataUrl){
  try { return await req('/api/facecheck', 'POST', { photo_data: dataUrl }); }
  catch (err) { return { found: false, reason: 'error', score: 0, yaw: 0, pitch: 0 }; }
}
async function checkFace(dataUrl, prefix, okText){
  clearTimeout(faceCheckTimer);
  if (!dataUrl){ setFStat(prefix, null); return { kind: null }; }
  setFStat(prefix, 'busy', 'در حال بررسی چهره… (اولین بار چند ثانیه طول می‌کشد)');
  const d = await probeFace(dataUrl);
  if (d.reason === 'error'){ setFStat(prefix, 'warn', FSTAT_MSG.error); return { kind: 'error' }; }
  if (d.found){
    setFStat(prefix, 'ok', `${okText || FSTAT_MSG.ok} (کیفیت ${Math.round(d.score * 100)}٪)`);
    return { kind: 'ok', reason: d.reason };
  }
  setFStat(prefix, d.reason === 'noface' ? 'bad' : 'warn', d.message || FSTAT_MSG[d.reason] || FSTAT_MSG.noface);
  return { kind: d.reason === 'noface' ? 'bad' : 'warn', reason: d.reason };
}
function scaleToCanvas(src, maxW){
  const c = document.getElementById('upCanvas');
  const w0 = src.videoWidth || src.width || maxW;
  const h0 = src.videoHeight || src.height || maxW;
  const k = Math.min(1, maxW / w0);
  c.width = Math.round(w0 * k);
  c.height = Math.round(h0 * k);
  c.getContext('2d').drawImage(src, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', 0.9);
}
function paintFormShots(){
  const list = photoData ? [photoData].concat(photoExtras || []) : [];
  document.getElementById('formShots').innerHTML = list.map((u, i) =>
    `<div class="shot good"><img src="${u}" alt="نمونه ${faNum(i + 1)}">` +
    `<span>${i === 0 ? 'عکس پروفایل' : `بردار ${faNum(i + 1)}`}</span></div>`).join('');
}
function useImageFile(f){
  if (!f || !/^image\\//.test(f.type || '')) { toast('فایل انتخابی تصویر نیست', true); return; }
  const url = URL.createObjectURL(f);
  const img = new Image();
  img.onload = () => {
    photoData = scaleToCanvas(img, 720);
    photoExtras = [];
    URL.revokeObjectURL(url);
    paintPreview(null);
    paintFormShots();
    checkFace(photoData, 'fstat');
  };
  img.onerror = () => { URL.revokeObjectURL(url); toast('این فایل تصویر خوانده نشد؛ JPEG یا PNG بفرستید', true); };
  img.src = url;
}
function waitEvent(el, ev, ms){
  return new Promise((res, rej) => {
    const to = setTimeout(() => { el.removeEventListener(ev, done); rej(new Error('timeout')); }, ms || 6000);
    function done(){ clearTimeout(to); el.removeEventListener(ev, done); res(); }
    el.addEventListener(ev, done, { once: true });
  });
}
async function readVideoFile(f, target){
  const box = target === 'test' ? 'tStat' : 'fstat';
  const url = URL.createObjectURL(f);
  const vid = document.createElement('video');
  vid.muted = true; vid.playsInline = true; vid.preload = 'auto';
  setFStat(box, 'busy', 'در حال خواندن ویدیو…');
  vid.src = url;
  try { await waitEvent(vid, 'loadedmetadata', 8000); }
  catch (err) {
    URL.revokeObjectURL(url);
    setFStat(box, 'bad', 'این ویدیو خوانده نشد؛ فایل MP4 یا WebM امتحان کنید.');
    return;
  }
  const dur = isFinite(vid.duration) && vid.duration > 0 ? vid.duration : 0;
  const marks = dur ? [0.04, 0.2, 0.4, 0.6, 0.8, 0.96] : [0];
  const frames = [];
  for (const m of marks){
    if (dur){
      try { vid.currentTime = Math.max(0.01, Math.min(dur - 0.01, dur * m)); await waitEvent(vid, 'seeked', 4000); }
      catch (err) { break; }
    }
    if (!vid.videoWidth) continue;
    const data = scaleToCanvas(vid, 720);
    if (data && frames.indexOf(data) < 0) frames.push(data);
    if (frames.length >= 6) break;
  }
  URL.revokeObjectURL(url);
  vid.removeAttribute('src'); vid.load();
  if (!frames.length){ setFStat(box, 'bad', 'از این ویدیو فریمی ساخته نشد.'); return; }
  await validateFrames(frames, target);
}
async function validateFrames(frames, target){
  const box = target === 'test' ? 'tStat' : 'fstat';
  const good = [];
  let lastReason = null;
  for (let i = 0; i < frames.length; i++){
    setFStat(box, 'busy', `بررسی فریم ${faNum(i + 1)} از ${faNum(frames.length)} ویدیو…`);
    const d = await probeFace(frames[i]);
    if (d.found) good.push({ url: frames[i], score: d.score });
    else lastReason = d.reason;
  }
  good.sort((a, b) => b.score - a.score);
  if (target === 'test'){
    testData = good.length ? good[0].url : frames[0];
    paintTestPreview();
    runTest();
    return;
  }
  if (!good.length){
    photoData = frames[0]; photoExtras = [];
    paintPreview(null); paintFormShots();
    setFStat(box, 'bad', `${faNum(frames.length)} فریم از ویدیو بررسی شد و هیچ چهره قابل استفاده‌ای نداشت. ` +
      (FSTAT_MSG[lastReason] || FSTAT_MSG.noface));
    return;
  }
  photoData = good[0].url;
  photoExtras = good.slice(1).map(s => s.url);
  photoRemove = false;
  paintPreview(null);
  paintFormShots();
  setFStat(box, 'ok', `${faNum(good.length)} فریم معتبر از ${faNum(frames.length)} فریم ویدیو پیدا شد — ` +
    `با «ذخیره» هر ${faNum(good.length)} بردار به گالری اضافه می‌شود و واضح‌ترین فریم عکس پروفایل می‌شود.`);
}
function useMediaFile(f, target){
  if (!f) return;
  const type = f.type || '';
  if (/^video\\//.test(type)) return readVideoFile(f, target);
  if (/^image\\//.test(type)) return target === 'test' ? pickTestFile(f) : useImageFile(f);
  toast('فایل انتخابی تصویر یا ویدیو نیست', true);
}
function pickFile(input){ useMediaFile(input.files && input.files[0], 'form'); }
function clearPhoto(){
  photoData = null; photoExtras = [];
  document.getElementById('fFile').value = '';
  paintFormShots();
  if (existingPhoto) photoRemove = true;
  paintPreview(null);
  setFStat('fstat', null);
  toast(existingPhoto ? 'عکس حذف شد — بعد از «ذخیره» پاک می‌شود' : 'انتخاب عکس لغو شد');
}
/* ---------- ضبط زنده چهره با وب‌کم: راهنمای مرحله‌به‌مرحله مثل احراز هویت ---------- */
let camStream = null;
let camTimer = null;
let camBusy = false;
let camStreak = 0;
let camLast = null;
let camBase = null;
let camTurnSign = 0;
let camSeq = 0;
let camIdx = 0;
let camStepStart = 0;
let camShots = [];
let camPoses = [];
const CAM_YAW_GATE = 0.12;
const CAM_PITCH_GATE = 0.15;
const CAM_STEP_GRACE = 9000;
const CAM_POSES = [
  { label: 'رو به دوربین', say: 'رو به دوربین، چند لحظه ثابت بمانید', kind: 'steady' },
  { label: 'چرخش به چپ', say: 'الان سر را کمی به چپ بچرخانید', kind: 'turn' },
  { label: 'چرخش به راست', say: 'الان سر را کمی به راست بچرخانید', kind: 'turn' },
  { label: 'نگاه به بالا', say: 'الان کمی به بالا نگاه کنید', kind: 'tilt' },
];
const camAutoOn = () => { const c = document.getElementById('camAuto'); return !c || c.checked; };
const camOpen = () => document.getElementById('camBackdrop').classList.contains('on');
const camPose = () => camPoses[Math.min(camIdx, camPoses.length - 1)];
function paintCamUI(){
  const p = camPose();
  document.getElementById('camStep').innerHTML = camTarget === 'test'
    ? '<b>تست زنده</b> — چهره داخل بیضی باشد.'
    : `<b>مرحله ${faNum(camIdx + 1)} از ${faNum(camPoses.length)}</b> · ${esc(p.label)} · نمونه‌ها: ${faNum(camShots.length)}`;
  document.getElementById('camDots').innerHTML = camPoses.map((s, i) =>
    `<b class="${i < camIdx ? 'done' : (i === camIdx ? 'cur' : '')}"><i></i><span>${esc(s.label)}</span></b>`).join('');
  document.getElementById('camPose').textContent = camTarget === 'test'
    ? 'چهره را داخل بیضی نگه دارید' : p.say;
  document.getElementById('camShots').innerHTML = camShots.map(s =>
    `<div class="shot ${s.ok ? 'good' : 'bad'}"><img src="${s.url}" alt="${esc(s.label)}">` +
    `<span>${esc(s.label)}</span></div>`).join('');
  document.getElementById('camDoneBtn').disabled = !camShots.length;
}
async function openCam(target){
  camSeq++;
  camTarget = target || 'form';
  camPoses = camTarget === 'test' ? CAM_POSES.slice(0, 1) : CAM_POSES.slice();
  camIdx = 0; camShots = []; camBase = null; camTurnSign = 0; camStreak = 0; camLast = null;
  document.getElementById('camTitle').textContent =
    camTarget === 'test' ? 'تست زنده چهره با وب‌کم' : 'ضبط چهره با وب‌کم (۴ حالت)';
  document.getElementById('camHint').textContent = 'در حال راه‌اندازی دوربین…';
  document.getElementById('camShotBtn').disabled = true;
  document.getElementById('camSkipBtn').disabled = true;
  setFStat('camStat', null);
  document.getElementById('camBackdrop').classList.add('on');
  paintCamUI();
  if (camStream) return readyCam();
  const v = document.getElementById('camVideo');
  try {
    camStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }, audio: false });
    v.srcObject = camStream;
    await v.play();
    readyCam();
  } catch (err) {
    const name = err && err.name ? err.name : 'خطا';
    const why = name === 'NotAllowedError'
      ? 'دسترسی دوربین رد شد. در Windows Settings › Privacy &amp; security › Camera اجازه «دسترسی برنامه‌های دسکتاپ» را روشن کنید و از مرورگر نوار آدرس برای این صفحه دسترسی دوربین را Permit کنید.'
      : name === 'NotFoundError'
        ? 'وب‌کمی پیدا نشد. اگر عکس یا ویدیو آماده دارید با «انتخاب فایل» آن را بفرستید.'
        : `دوربین باز نشد (${name}). ممکن است برنامه دیگری آن را نگه داشته باشد — همان را ببندید و دوباره تلاش کنید.`;
    document.getElementById('camHint').innerHTML = why;
    setFStat('camStat', 'warn', why);
  }
}
function readyCam(){
  camSeq++;
  camStepStart = Date.now();
  camStreak = 0; camLast = null;
  document.getElementById('camShotBtn').disabled = false;
  document.getElementById('camSkipBtn').disabled = false;
  document.getElementById('camHint').textContent = camTarget === 'test'
    ? 'با «ثبت همین حالا» همان لحظه را تست کنید؛ اگر صبر کنید، به‌محض واضح شدن چهره خودکار ثبت می‌شود.'
    : 'دستور هر مرحله روی تصویر نوشته می‌شود. به‌محض اینکه چهره در همان حالت واضح و ثابت شود خودکار ثبت می‌شود و مرحله بعد شروع می‌شود. می‌توانید «رد کردن این مرحله» را هم بزنید.';
  paintCamUI();
  startPoll();
}
function startPoll(){
  stopPoll();
  if (!camAutoOn() || !camStream) return;
  document.getElementById('camLiveBadge').style.display = '';
  camTimer = setInterval(camTick, 520);
}
function stopPoll(){
  if (camTimer){ clearInterval(camTimer); camTimer = null; }
  const b = document.getElementById('camLiveBadge');
  if (b) b.style.display = 'none';
}
function toggleAuto(){
  if (!camOpen()) return;
  camStreak = 0; camLast = null;
  if (camAutoOn()){ startPoll(); return; }
  stopPoll();
  setFStat('camStat', 'busy', 'ثبت خودکار خاموش است؛ در هر مرحله «ثبت همین حالا» را بزنید.');
}
function grabCamFrame(maxW){
  const v = document.getElementById('camVideo'), c = document.getElementById('upCanvas');
  const w0 = v.videoWidth || 640, h0 = v.videoHeight || 480;
  const k = Math.min(1, maxW / w0);
  c.width = Math.round(w0 * k); c.height = Math.round(h0 * k);
  const ctx = c.getContext('2d');
  ctx.translate(c.width, 0); ctx.scale(-1, 1);   // آینه‌ای، همان چیزی که کاربر می‌بیند
  ctx.drawImage(v, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', 0.9);
}
function judge(p, d){
  if (!d.found) return { ok: false, why: d.reason, msg: d.message || FSTAT_MSG[d.reason] || FSTAT_MSG.noface };
  if (!camBase) return { ok: true, base: d };
  if (p.kind === 'steady') return { ok: true };
  if (p.kind === 'turn'){
    const dyaw = d.yaw - camBase.yaw;
    const fill = Math.min(100, Math.round(Math.abs(dyaw) / CAM_YAW_GATE * 100));
    if (Math.abs(dyaw) < CAM_YAW_GATE)
      return { ok: false, why: 'turn', msg: `چرخش سر ${faNum(fill)}٪ لازم است — کمی بیشتر همان طرف بچرخانید.` };
    if (camTurnSign && Math.sign(dyaw) === camTurnSign)
      return { ok: false, why: 'other', msg: 'این طرف قبلاً ثبت شد؛ حالا سر را به طرف دیگر بچرخانید.' };
    return { ok: true, sign: Math.sign(dyaw) };
  }
  const dp = d.pitch - camBase.pitch;
  const fill = Math.min(100, Math.round(Math.abs(dp) / CAM_PITCH_GATE * 100));
  if (Math.abs(dp) < CAM_PITCH_GATE)
    return { ok: false, why: 'tilt', msg: `شیب سر ${faNum(fill)}٪ لازم است — کمی بیشتر به بالا نگاه کنید.` };
  return { ok: true };
}
async function camTick(){
  if (camBusy || !camStream || !camOpen() || !camPoses.length) return;
  const seq = camSeq;
  camBusy = true;
  try {
    const url = grabCamFrame(640);
    const d = await probeFace(url);
    if (seq !== camSeq || !camOpen()) return;
    const p = camPose();
    const r = judge(p, d);
    if (!r.ok){
      camStreak = 0; camLast = d;
      const slow = Date.now() - camStepStart > CAM_STEP_GRACE && r.why !== 'noface';
      setFStat('camStat', r.why === 'noface' ? 'bad' : 'warn',
        slow ? r.msg + ' اگر زاویه اندازه‌گیری نشد، «ثبت همین حالا» را بزنید — همان فریم ثبت می‌شود.' : r.msg);
      return;
    }
    if (p.kind === 'steady' && !camBase && camStreak < 1){
      camStreak++; camLast = d;
      setFStat('camStat', 'busy', 'چهره پیدا شد — یک لحظه دیگر ثابت بمانید…');
      return;
    }
    lockShot(url, r);
  } catch (err) {
    setFStat('camStat', 'warn', FSTAT_MSG.error);
  } finally { camBusy = false; }
}
function lockShot(url, r){
  const p = camPose();
  stopPoll();                       // تا زمان رفتن به مرحله بعد، فریم جدیدی بررسی نشود
  camShots.push({ url, label: p.label, ok: true });
  if (r.base) camBase = { yaw: r.base.yaw, pitch: r.base.pitch };
  if (r.sign) camTurnSign = r.sign;
  camStreak = 0; camLast = null;
  flashShot(url);
  paintCamUI();
  setFStat('camStat', 'busy', `حالت «${p.label}» ثبت شد ✓`);
  const seq = camSeq;
  setTimeout(() => { if (seq === camSeq) (camTarget === 'test' ? finishCam() : nextStep()); }, 800);
}
function flashShot(url){
  document.getElementById('camShotImg').src = url;
  const stage = document.getElementById('camStage');
  stage.classList.add('on-shot');
  setTimeout(() => stage.classList.remove('on-shot'), 420);
}
function nextStep(){
  camIdx++;
  camStreak = 0; camLast = null;
  camSeq++; camStepStart = Date.now();
  stopPoll();
  if (camIdx >= camPoses.length){ finishCam(); return; }
  setFStat('camStat', null);
  paintCamUI();
  if (camOpen() && camAutoOn()) startPoll();
}
function skipStep(){
  if (camTarget === 'test') return;
  stopPoll();
  setFStat('camStat', 'busy', 'این مرحله رد شد.');
  nextStep();
  if (camOpen() && camAutoOn()) startPoll();
}
async function captureManual(){
  if (!camStream || !camPoses.length){ toast('دوربین آماده نیست', true); return; }
  const seq = camSeq;
  stopPoll();
  camBusy = true;
  setFStat('camStat', 'busy', 'در حال بررسی همین لحظه…');
  try {
    const url = grabCamFrame(720);
    const d = await probeFace(url);
    if (seq !== camSeq || !camOpen()) return;
    const p = camPose();
    if (!d.found && camTarget !== 'test'){
      camStreak = 0;
      setFStat('camStat', 'bad', d.message || FSTAT_MSG[d.reason] || FSTAT_MSG.noface);
      if (camAutoOn()) startPoll();
      return;
    }
    camShots.push({ url, label: p.label, ok: !!d.found });
    if (d.found){
      if (!camBase) camBase = { yaw: d.yaw, pitch: d.pitch };
      else if (p.kind === 'turn' && !camTurnSign && Math.abs(d.yaw - camBase.yaw) >= CAM_YAW_GATE)
        camTurnSign = Math.sign(d.yaw - camBase.yaw);
    }
    camStreak = 0; camLast = null;
    flashShot(url);
    paintCamUI();
    setFStat('camStat', d.found ? 'busy' : 'warn', d.found
      ? `حالت «${p.label}» ثبت شد ✓`
      : 'چهره در این فریم واضح نبود؛ این نمونه به گالری اضافه نمی‌شود.');
    setTimeout(() => { if (seq === camSeq) (camTarget === 'test' ? finishCam() : nextStep()); }, 700);
  } finally { camBusy = false; }
}
function finishCam(){
  camSeq++;
  stopPoll(); stopCam();
  document.getElementById('camBackdrop').classList.remove('on');
  const shots = camShots.slice();
  camShots = []; camIdx = 0; camBase = null; camTurnSign = 0;
  const good = shots.filter(s => s.ok);
  if (camTarget === 'test'){
    const pick = good[good.length - 1] || shots[shots.length - 1];
    if (!pick) return;
    testData = pick.url;
    paintTestPreview();
    runTest();
    return;
  }
  if (!good.length){
    toast(shots.length ? 'هیچ نمونه‌ای کیفیت کافی نداشت؛ دوباره با نور بهتر تلاش کنید' : 'هیچ نمونه‌ای ثبت نشد', true);
    return;
  }
  photoData = good[0].url;
  photoExtras = good.slice(1).map(s => s.url);
  photoRemove = false;
  paintPreview(null);
  paintFormShots();
  setFStat('fstat', 'ok', `${faNum(good.length)} حالت چهره آماده است — با «ذخیره» هر ${faNum(good.length)} بردار به گالری اضافه می‌شود.`);
  if (shots.length > good.length) toast(`${faNum(shots.length - good.length)} نمونه بی‌کیفیت کنار گذاشته شد`, true);
}
function stopCam(){
  if (camStream){ camStream.getTracks().forEach(t => t.stop()); camStream = null; }
  const v = document.getElementById('camVideo');
  v.srcObject = null;
}
function closeCam(){
  camSeq++;
  stopPoll(); stopCam();
  camShots = []; camIdx = 0; camBase = null; camTurnSign = 0; camStreak = 0; camLast = null;
  document.getElementById('camBackdrop').classList.remove('on');
}
/* ---------- تست تشخیص چهره + اعتبارسنجی گالری ---------- */
let testData = null;
let camTarget = 'form';
function paintTestPreview(){
  const box = document.getElementById('testPreview');
  box.innerHTML = testData ? `<img src="${testData}" alt="عکس تست">` : 'بدون عکس';
}
function pickTestFile(f){
  if (!f || !/^image\\//.test(f.type || '')) { toast('فایل انتخابی تصویر نیست', true); return; }
  const url = URL.createObjectURL(f);
  const img = new Image();
  img.onload = () => {
    testData = scaleToCanvas(img, 720);
    URL.revokeObjectURL(url);
    paintTestPreview();
    runTest();
  };
  img.onerror = () => { URL.revokeObjectURL(url); toast('این فایل تصویر خوانده نشد', true); };
  img.src = url;
}
function pickTest(input){ pickTestFile(input.files && input.files[0]); }
const pct = v => Math.round(v * 100);
async function runTest(){
  if (!testData){ toast('اول یک عکس انتخاب کنید یا با وب‌کم بگیرید', true); return; }
  const btn = document.getElementById('tRun'); btn.disabled = true;
  setFStat('tStat', 'busy', 'در حال پیدا کردن چهره و تطبیق با گالری…');
  try {
    const d = await req('/api/identify', 'POST',
      { photo_data: testData, threshold: parseFloat(document.getElementById('tThr').value) || 0.4 });
    const g = `چهره در گالری: ${d.vectors} بردار · ${d.students} دانشجو · آستانه ${d.threshold}`;
    if (d.reason !== 'ok' && !d.matched){
      setFStat('tStat', 'bad',
        `${FSTAT_MSG[d.reason] || 'چهره قابل استفاده نیست.'} ${g}`);
    } else if (d.matched){
      setFStat('tStat', 'ok',
        `شناسایی شد: ${d.matched.name} (${d.matched.code}) — شباهت ${pct(d.best_sim)}٪ · ` +
        `${d.matched.samples} نمونه چهره در گالری${d.matched.photo ? ' · عکس هم دارد' : ''}. ${g}`);
    } else {
      setFStat('tStat', 'warn',
        `هیچ دانشجویی با آستانه ${d.threshold} شناخته نشد — نزدیک‌ترین: ` +
        (d.best ? `${d.best.name} (${d.best.code}) با ${pct(d.best_sim)}٪` : 'هیچ') +
        `. اگر واقعاً همان نفر است، آستانه را پایین بیاورید (مثلاً ۰.۳۵) یا با «ویرایش» همان عکس را برای «${d.best ? d.best.name : 'دانشجو'}» ثبت کنید. ${g}`);
    }
  } catch (err) {
    setFStat('tStat', 'bad', err.message);
  } finally { btn.disabled = false; }
}
async function checkGallery(){
  const box = document.getElementById('galleryCheck');
  box.innerHTML = '<p class="pnote">در حال بررسی…</p>';
  let d;
  try { d = await j('/api/gallerycheck'); }
  catch (err) { box.innerHTML = `<p class="pnote">${esc(err.message || 'خطا')}</p>`; return; }
  const bad = d.rows.filter(r => !r.samples).length;
  box.innerHTML = `<table><thead><tr><th>دانشجو</th><th>شماره</th><th>نمونه چهره</th><th>عکس</th><th>وضعیت</th></tr></thead><tbody>` +
    d.rows.map(r => `<tr class="${r.samples ? '' : 'susp'}"><td>${esc(r.name)}</td><td style="direction:ltr;text-align:left">${esc(r.code)}</td>` +
      `<td>${faNum(r.samples)}</td><td style="direction:ltr">${r.photo ? chip('دارد', 'in') : chip('ندارد', 'absent')}</td>` +
      `<td>${r.samples ? chip('قابل شناسایی', 'in') : chip('در گالری نیست — enroll.py یا عکس رو‌به‌دوربین لازم دارد', 'susp')}</td></tr>`).join('') +
    `</tbody></table><p class="pnote">${faNum(d.vectors)} بردار چهره برای ${faNum(d.students)} دانشجو — ` +
    (bad ? `${faNum(bad)} نفر هیچ بردار چهره ندارند و با دوربین شناسایی نمی‌شوند.` : 'همه حداقل یک بردار چهره دارند.') + `</p>`;
}
async function saveStudent(e){
  e.preventDefault();
  const id = document.getElementById('fId').value;
  const body = {
    full_name: document.getElementById('fName').value.trim(),
    student_no: document.getElementById('fNo').value.trim(),
    major: document.getElementById('fMajor').value.trim(),
    email: document.getElementById('fEmail').value.trim(),
    phone: document.getElementById('fPhone').value.trim(),
  };
  if (photoData) body.photo_data = photoData;
  if (photoExtras && photoExtras.length) body.photo_data_list = [photoData].concat(photoExtras);
  if (photoRemove) body.photo_remove = true;
  const shots = photoData ? 1 + photoExtras.length : 0;
  const btn = document.getElementById('mSave'); const oldLabel = btn.textContent;
  btn.disabled = true; btn.textContent = 'در حال ذخیره…';
  const note = document.getElementById('pNote');
  const original = note.textContent;
  try {
    if (photoData) {
      note.textContent = `در حال ثبت ${faNum(shots)} حالت چهره در گالری تشخیص… (چند ثانیه)`;
      setFStat('fstat', 'busy', 'در حال ثبت چهره در گالری…');
    }
    const d = await req(id ? `/api/students/${id}` : '/api/students', id ? 'PUT' : 'POST', body);
    closeModal();
    let msg = id ? 'اطلاعات به‌روزرسانی شد' : 'دانشجو اضافه شد';
    if (d.photo_removed) msg += ' — عکس حذف شد';
    else if (d.face_added) msg += ` — ${faNum(d.face_added)} حالت چهره به گالری اضافه شد`;
    toast(msg);
    if (d.photo_warning) setTimeout(() => toast(d.photo_warning, true), 900);
    await refresh();
  } catch (err) {
    toast(err.message, true);
    if (photoData) setFStat('fstat', 'bad', `ذخیره نشد: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = oldLabel;
    note.textContent = original;
  }
  return false;
}
async function delStudent(id){
  const p = STUDENTS.find(x => x.id === id);
  if (!p || !confirm(`حذف «${p.full_name}» به همراه همه رکوردهای حضور و غیاب و نمونه‌های چهره؟`)) return;
  try {
    const d = await req(`/api/students/${id}`, 'DELETE');
    toast(`حذف شد — ${d.removed_samples} نمونه چهره هم پاک شد`);
    await refresh();
  } catch (err) { toast(err.message, true); }
}
function paintHoursState(s){
  document.getElementById('hoursState').textContent = s.hours_enabled === '1'
    ? `فعال · ورود ${s.in_start} تا ${s.in_end} · خروج ${s.out_start} تا ${s.out_end}`
    : 'غیرفعال — همه ساعت‌ها مجاز';
}
async function loadHours(){
  try {
    const s = await j('/api/settings');
    document.getElementById('hEnabled').checked = s.hours_enabled === '1';
    document.getElementById('hInStart').value = s.in_start;
    document.getElementById('hInEnd').value = s.in_end;
    document.getElementById('hOutStart').value = s.out_start;
    document.getElementById('hOutEnd').value = s.out_end;
    paintHoursState(s);
  } catch {}
}
async function saveHours(){
  const val = id => document.getElementById(id).value;
  const body = {
    hours_enabled: document.getElementById('hEnabled').checked,
    in_start: val('hInStart'), in_end: val('hInEnd'),
    out_start: val('hOutStart'), out_end: val('hOutEnd'),
  };
  try {
    const s = await req('/api/settings', 'POST', body);
    paintHoursState(s);
    toast('ساعت‌های مجاز ذخیره شد');
    await refresh();
  } catch (err) { toast(err.message, true); }
}
/* ---------- گزارش اکسل آخر شب ---------- */
function paintEodState(s){
  document.getElementById('eodState').textContent = s.eod_enabled === '1'
    ? `خودکار هر روز ساعت ${s.eod_time}` + (s.eod_last_date ? ` · آخرین فایل: ${s.eod_last_date}` : ' · هنوز خودکار ساخته نشده')
    : 'ساخت خودکار غیرفعال';
}
async function loadEod(){
  try {
    const s = await j('/api/settings');
    document.getElementById('eodEnabled').checked = s.eod_enabled === '1';
    document.getElementById('eodTime').value = s.eod_time;
    paintEodState(s);
  } catch {}
}
async function saveEod(){
  const body = {
    eod_enabled: document.getElementById('eodEnabled').checked,
    eod_time: document.getElementById('eodTime').value,
  };
  try {
    const s = await req('/api/settings', 'POST', body);
    paintEodState(s);
    toast('زمان‌بندی گزارش اکسل ذخیره شد');
  } catch (err) { toast(err.message, true); }
}
async function makeNow(e){
  const btn = e.target;
  btn.disabled = true;
  const txt = btn.textContent;
  btn.textContent = 'در حال ساخت…';
  try {
    const d = await req('/api/export', 'POST', { date: document.getElementById('day').value });
    toast(`فایل ${d.file} ساخته شد`);
    await loadReports();
    loadEod();
    window.open(d.url, '_blank');
  } catch (err) { toast(err.message, true); }
  finally { btn.disabled = false; btn.textContent = txt; }
}
async function loadReports(){
  let files = [];
  try { files = await j('/api/reports'); } catch { return; }
  document.getElementById('reports').innerHTML = files.length
    ? files.map(f => `<a href="${f.url}" download title="ویرایش: ${f.modified}">${f.date} · ${f.size_kb} KB</a>`).join('')
    : '<span class="none">هنوز فایلی در پوشه reports ساخته نشده است</span>';
}
/* ---------- انتخاب‌گر تاریخ شمسی ---------- */
const pad = n => String(n).padStart(2, '0');
const utcDay = (y, m, d) => new Date(Date.UTC(y, m - 1, d, 12));
const isoOf = g => g.toISOString().slice(0, 10);
const faNum = n => new Intl.NumberFormat('fa-IR', { useGrouping: false }).format(n);
const jalParts = new Intl.DateTimeFormat('en-US-u-ca-persian',
  { timeZone:'UTC', day:'numeric', month:'numeric', year:'numeric', numberingSystem:'latn' });
const faMonth = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { timeZone:'UTC', month:'long' });
const faWeekday = new Intl.DateTimeFormat('fa-IR-u-ca-persian', { timeZone:'UTC', weekday:'long' });
function toJal(g){
  const p = jalParts.formatToParts(g);
  const v = t => +p.find(x => x.type === t).value;
  return { jy: v('year'), jm: v('month'), jd: v('day') };
}
function fromJal(jy, jm, jd){
  let g = utcDay(jy + 621, 3, 21);
  g = new Date(g.getTime() + ((jm - 1) * 31 + (jd - 1)) * 864e5);
  for (let i = 0; i < 5; i++){
    const j = toJal(g);
    const diff = ((jy - j.jy) * 12 + (jm - j.jm)) * 32 + (jd - j.jd);
    if (!diff) break;
    g = new Date(g.getTime() + diff * 864e5);
  }
  return g;
}
function jalLabel(g, withWeekday){
  const j = toJal(g);
  return (withWeekday ? faWeekday.format(g) + ' ' : '') + faNum(j.jd) + ' ' + faMonth.format(g) + ' ' + faNum(j.jy);
}
const dayVal = () => utcDay(...document.getElementById('day').value.split('-').map(Number));
const selJal = () => toJal(dayVal());
const localToday = () => { const n = new Date(); return utcDay(n.getFullYear(), n.getMonth() + 1, n.getDate()); };
const WEEK = ['ش', 'ی', 'د', 'س', 'چ', 'پ', 'ج'];
let view = { jy: 0, jm: 0 };
function paintDayBtn(){ document.getElementById('dayBtn').textContent = jalLabel(dayVal(), true); }
function renderCal(){
  const sel = selJal(), today = toJal(localToday());
  const first = fromJal(view.jy, view.jm, 1);
  const next = fromJal(view.jy + (view.jm === 12 ? 1 : 0), view.jm === 12 ? 1 : view.jm + 1, 1);
  const daysIn = Math.round((next - first) / 864e5);
  const lead = (first.getUTCDay() + 1) % 7;           // شنبه = ستون اول
  let html = `<div class="cal-head">
      <button type="button" title="ماه قبل" onclick="moveMonth(-1)">›</button>
      <span>${faMonth.format(first)} ${faNum(view.jy)}</span>
      <button type="button" title="ماه بعد" onclick="moveMonth(1)">‹</button>
    </div><div class="cal-grid">` + WEEK.map(w => `<span class="wd">${w}</span>`).join('');
  for (let i = 0; i < lead; i++) html += '<span></span>';
  for (let d = 1; d <= daysIn; d++){
    const isSel = view.jy === sel.jy && view.jm === sel.jm && d === sel.jd;
    const isToday = !isSel && view.jy === today.jy && view.jm === today.jm && d === today.jd;
    html += `<button type="button" class="${isSel ? 'sel' : ''}${isToday ? ' today' : ''}" onclick="pickDay(${d})">${faNum(d)}</button>`;
  }
  html += `</div><div class="cal-foot"><button type="button" onclick="pickToday()">امروز</button></div>`;
  document.getElementById('cal').innerHTML = html;
}
function moveMonth(step){
  let m = view.jm + step, y = view.jy;
  if (m < 1){ m = 12; y--; } else if (m > 12){ m = 1; y++; }
  view = { jy: y, jm: m };
  renderCal();
}
function setDay(g){
  document.getElementById('day').value = isoOf(g);
  const j = toJal(g);
  view = { jy: j.jy, jm: j.jm };
  paintDayBtn();
  refresh();
}
function pickDay(d){ setDay(fromJal(view.jy, view.jm, d)); closeCal(); }
function pickToday(){ setDay(localToday()); closeCal(); }
function toggleCal(e){
  e.stopPropagation();
  const c = document.getElementById('cal');
  const open = !c.classList.contains('on');
  c.classList.toggle('on', open);
  if (open){ const j = selJal(); view = { jy: j.jy, jm: j.jm }; renderCal(); }
}
function closeCal(){ document.getElementById('cal').classList.remove('on'); }
document.addEventListener('click', closeCal);
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  closeCal();
  if (document.getElementById('camBackdrop').classList.contains('on')) closeCam();
  else if (document.getElementById('backdrop').classList.contains('on')) closeModal();
});
function wireDrop(el, onFile){
  el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('over'); });
  el.addEventListener('dragleave', () => el.classList.remove('over'));
  el.addEventListener('drop', e => {
    e.preventDefault();
    el.classList.remove('over');
    const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) onFile(f);
  });
}
wireDrop(document.getElementById('drop'), useImageFile);
wireDrop(document.getElementById('testDrop'), pickTestFile);
document.getElementById('day').value = isoOf(localToday());
const j0 = selJal(); view = { jy: j0.jy, jm: j0.jm };
paintDayBtn();
tick(); setInterval(tick, 1000);
refresh(); setInterval(refresh, 5000);
loadHours(); loadEod(); loadReports();
</script>
</body>
</html>"""


def _rows(day):
    return [dict(r) for r in db.daily_report(day)]


def _with_status(rows):
    """افزودن وضعیت 'ok'/'suspicious' به هر رویداد بر اساس ساعت مجاز."""
    settings = db.get_settings()
    for r in rows:
        r["status"] = db.classify_event(r["event"], r["logged_at"], settings)
    return rows


@app.get("/")
def index():
    resp = make_response(PAGE)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/events")
def api_events():
    day = _date_arg()
    return jsonify(_with_status(_rows(day)))


@app.get("/api/summary")
def api_summary():
    day = _date_arg()
    rows = _with_status(_rows(day))
    students = db.list_students()
    inside = {}
    for r in rows:  # chronological; last event per student wins
        inside[r["student_id"]] = r
    open_now = [
        {"name": s["full_name"], "code": s["student_no"], "last_in": inside[s["id"]]["logged_at"][11:]}
        for s in students
        if s["id"] in inside and inside[s["id"]]["event"] == "IN"
    ]
    return jsonify({
        "date": day.isoformat(),
        "students": len(students),
        "ins": sum(1 for r in rows if r["event"] == "IN"),
        "outs": sum(1 for r in rows if r["event"] == "OUT"),
        "suspicious": sum(1 for r in rows if r["status"] == "suspicious"),
        "inside": open_now,
    })


@app.get("/api/students")
def api_students():
    day = _date_arg()
    rows = _rows(day)
    last = {}
    for r in rows:
        last[r["student_id"]] = r
    emb, ids = engine.load_gallery()
    counts = {}
    if emb.size:
        for i in ids:
            counts[int(i)] = counts.get(int(i), 0) + 1
    out = []
    for s in db.list_students():
        photo = _photo_file(s)
        out.append({
            "id": s["id"],
            "full_name": s["full_name"],
            "student_no": s["student_no"],
            "major": s["major"],
            "email": s["email"],
            "phone": s["phone"],
            "samples": counts.get(s["id"], 0),
            "inside": s["id"] in last and last[s["id"]]["event"] == "IN",
            "photo": bool(photo),
            "photo_v": int(photo.stat().st_mtime) if photo else 0,
        })
    return jsonify(out)


@app.post("/api/facecheck")
def api_facecheck():
    """پیش‌بررسی عکس: آیا چهره قابل استفاده است، کیفیت و زاویه سر چقدر است."""
    body = request.get_json(silent=True) or {}
    data_url = body.get("photo_data")
    if not isinstance(data_url, str) or not data_url.strip():
        return jsonify({"error": "عکسی ارسال نشد"}), 400
    frame, err = _decode_photo(data_url)
    if frame is None:
        return jsonify({"found": False, "reason": err, "score": 0.0, "yaw": 0.0, "pitch": 0.0,
                        "message": FACE_CHECK_MSG[err]})
    info = engine.analyze(frame)
    reason = info["reason"]
    return jsonify({"found": reason == "ok", "reason": reason, "score": info["det"],
                    "yaw": info["yaw"], "pitch": info["pitch"],
                    "message": None if reason == "ok" else FACE_CHECK_MSG[reason]})


DEFAULT_THRESHOLD = 0.40


def _gallery_counts() -> dict:
    _emb, ids = engine.load_gallery()
    counts: dict = {}
    for i in ids:
        counts[int(i)] = counts.get(int(i), 0) + 1
    return counts


@app.post("/api/identify")
def api_identify():
    """تست تشخیص: این عکس به کدام دانشجوی گالری تعلق دارد؟"""
    body = request.get_json(silent=True) or {}
    data_url = body.get("photo_data")
    if not isinstance(data_url, str) or not data_url.strip():
        return jsonify({"error": "عکسی ارسال نشد"}), 400
    frame, err = _decode_photo(data_url)
    if frame is None:
        return jsonify({"error": FACE_CHECK_MSG[err]}), 400
    try:
        thr = float(body.get("threshold"))
    except (TypeError, ValueError):
        thr = DEFAULT_THRESHOLD
    thr = min(max(thr, 0.05), 0.95)
    res = engine.identify(frame, thr)
    by_id = {s["id"]: s for s in db.list_students()}
    counts = _gallery_counts()

    def who(sid):
        s = by_id.get(sid)
        if not s:
            return None
        return {"id": sid, "name": s["full_name"], "code": s["student_no"],
                "samples": counts.get(sid, 0), "photo": bool(_photo_file(s))}

    return jsonify({
        "reason": res["reason"], "det": res["det"], "threshold": thr,
        "vectors": sum(counts.values()), "students": len(by_id),
        "best_sim": res["best_sim"], "matched": who(res["student_id"]),
        "best": who(res["best_id"]),
    })


@app.get("/api/gallerycheck")
def api_gallerycheck():
    """وضعیت اعتبارسنجی گالری: هر دانشجو چند نمونه چهره و عکس دارد."""
    counts = _gallery_counts()
    rows = []
    for s in db.list_students():
        n = counts.get(s["id"], 0)
        photo = _photo_file(s)
        rows.append({
            "id": s["id"], "name": s["full_name"], "code": s["student_no"],
            "samples": n, "photo": bool(photo),
            "state": "ok" if n else "noface",
            "warning": None if n else "هیچ بردار چهره‌ای ندارد؛ با دوربین هرگز شناسایی نمی‌شود",
        })
    return jsonify({"vectors": sum(counts.values()), "students": len(rows), "rows": rows})


def _photo_file(row):
    """مسیر فایل عکس دانشجو؛ None اگر وجود ندارد."""
    name = (row["photo"] or "") if "photo" in row.keys() else ""
    if not name:
        return None
    path = PHOTOS_DIR / name
    return path if path.exists() else None


FACE_REASONS = {
    "noface": "چهره‌ای در این تصویر پیدا نشد؛ عکس ذخیره شد ولی دانشجو هنوز با دوربین شناسایی نمی‌شود.",
    "small": "چهره در عکس خیلی کوچک است؛ عکس کلوزآپ‌تر از صورت بفرستید. عکس ذخیره شد ولی چهره به گالری اضافه نشد.",
    "weak": "چهره تار یا نیمه‌رو است؛ تمام‌رخ و با نور مناسب عکس بگیرید. عکس ذخیره شد ولی چهره به گالری اضافه نشد.",
    "bad_image": "فایل تصویر خوانده نشد؛ JPEG یا PNG بفرستید.",
    "bad_data": "داده عکس معتبر نیست.",
}

# پیام‌های پیش‌بررسی (قبل از ذخیره): فقط راهنما، بدون اشاره به ذخیره شدن
FACE_CHECK_MSG = {
    "noface": "چهره‌ای در این تصویر پیدا نشد. عکس دیگری بفرستید یا با وب‌کم بگیرید.",
    "small": "چهره در عکس خیلی کوچک است. صورت باید حداقل یک‌سوم عرض کادر را پر کند.",
    "weak": "چهره تار، نیمه‌رو یا در نور ضعیف است. تمام‌رخ و رو به دوربین عکس بگیرید.",
    "bad_image": "این فایل تصویر خوانده نشد؛ JPEG یا PNG بفرستید.",
    "bad_data": "داده عکس معتبر نیست.",
}


def _decode_photo(data_url: str):
    """data URL / base64 خالص -> numpy frame. خطا را با کلید FACE_REASONS برمی‌گرداند."""
    payload = data_url.split("base64,", 1)[-1] if "base64," in data_url else data_url
    try:
        raw = base64.b64decode(payload)
    except Exception:
        return None, "bad_data"
    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return None, "bad_image"
    return frame, None


def _store_photo(student_id: int, data_urls: list[str]) -> tuple[str | None, int, str | None]:
    """چند حالت چهره را ذخیره می‌کند. برمی‌گرداند (فایل, تعداد بردار, هشدار).

    اولین عکس به‌عنوان عکس پروفایل روی دیسک می‌نشیند و بردار هر عکسی که از
    دروازه کیفیت رد شود به گالری اضافه می‌شود؛ زوایای مختلف بردارهای مقاوم‌تری
    می‌سازند و تشخیص با دوربین دقیق‌تر می‌شود.
    """
    frames = []
    err_key = None
    for url in data_urls:
        frame, err = _decode_photo(url)
        if frame is None:
            err_key = err
            continue
        frames.append(frame)
    if not frames:
        return None, 0, FACE_REASONS[err_key or "bad_data"]
    PHOTOS_DIR.mkdir(exist_ok=True)
    filename = f"student_{student_id}.jpg"
    ok, buf = cv2.imencode(".jpg", frames[0], [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        return None, 0, "ذخیره عکس ناموفق بود"
    (PHOTOS_DIR / filename).write_bytes(buf.tobytes())

    embeddings, rejected = [], 0
    for frame in frames:
        face = engine.capture_frame_for_enroll(frame)
        if face is None:
            rejected += 1
        else:
            embeddings.append(face.embedding)
    if not embeddings:
        quality, _ = engine.face_quality(frames[0])
        return filename, 0, FACE_REASONS[quality if quality != "ok" else "noface"]
    engine.add_embeddings(student_id, embeddings)
    warning = (f"چهره ثبت شد، ولی {rejected} از {len(frames)} حالت "
               "به دلیل کیفیت پایین به گالری اضافه نشد.") if rejected else None
    return filename, len(embeddings), warning


def _drop_photo(student_id: int) -> None:
    row = db.get_student_by_id(student_id)
    name = (row["photo"] or "") if row and "photo" in row.keys() else ""
    if name:
        path = PHOTOS_DIR / name
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _apply_photo(student_id: int, body: dict) -> dict:
    """photo_data (base64) یا photo_remove را اعمال می‌کند و نتیجه را برمی‌گرداند."""
    result: dict = {}
    if body.get("photo_remove"):
        _drop_photo(student_id)
        db.set_student_photo(student_id, None)
        result["photo_removed"] = True
    data_urls: list[str] = []
    if isinstance(body.get("photo_data_list"), list):
        data_urls = [u for u in body["photo_data_list"] if isinstance(u, str) and u.strip()]
    data_url = body.get("photo_data")
    if not data_urls and isinstance(data_url, str) and data_url.strip():
        data_urls = [data_url]
    if data_urls:
        filename, added, warning = _store_photo(student_id, data_urls)
        if filename:
            db.set_student_photo(student_id, filename)
        result.update({"face_added": added, "photo_warning": warning})
    return result


def _clean_student_body():
    body = request.get_json(silent=True) or {}
    fields = {k: (str(body.get(k) or "").strip() or None) for k in db.STUDENT_FIELDS}
    return fields, body


@app.post("/api/students")
def api_create_student():
    f, body = _clean_student_body()
    if not f["full_name"] or not f["student_no"]:
        return jsonify({"error": "نام و شماره دانشجویی الزامی است"}), 400
    if db.student_no_taken(f["student_no"]):
        return jsonify({"error": f"شماره دانشجویی {f['student_no']} قبلاً ثبت شده است"}), 409
    student_id = db.add_student(f["full_name"], f["student_no"], f["major"], f["email"], f["phone"])
    out = _apply_photo(student_id, body)
    out.update(dict(db.get_student_by_id(student_id)))
    return jsonify(out), 201


@app.put("/api/students/<int:student_id>")
def api_update_student(student_id: int):
    if not db.get_student_by_id(student_id):
        return jsonify({"error": "دانشجو یافت نشد"}), 404
    f, body = _clean_student_body()
    if not f["full_name"] or not f["student_no"]:
        return jsonify({"error": "نام و شماره دانشجویی الزامی است"}), 400
    if db.student_no_taken(f["student_no"], exclude_id=student_id):
        return jsonify({"error": f"شماره دانشجویی {f['student_no']} متعلق به دانشجوی دیگری است"}), 409
    db.update_student(student_id, f)
    out = _apply_photo(student_id, body)
    out.update(dict(db.get_student_by_id(student_id)))
    return jsonify(out)


@app.delete("/api/students/<int:student_id>")
def api_delete_student(student_id: int):
    if not db.get_student_by_id(student_id):
        return jsonify({"error": "دانشجو یافت نشد"}), 404
    removed_samples = engine.remove_student(student_id)
    _drop_photo(student_id)
    db.delete_student(student_id)
    return jsonify({"deleted": student_id, "removed_samples": removed_samples})


@app.get("/photo/<int:student_id>")
def student_photo(student_id: int):
    row = db.get_student_by_id(student_id)
    photo = _photo_file(row) if row else None
    if not photo:
        return jsonify({"error": "عکسی برای این دانشجو ثبت نشده"}), 404
    return send_from_directory(PHOTOS_DIR, photo.name, mimetype="image/jpeg")


HOUR_LABELS = {
    "in_start": "شروع بازه ورود",
    "in_end": "پایان بازه ورود",
    "out_start": "شروع بازه خروج",
    "out_end": "پایان بازه خروج",
    "eod_time": "ساعت ساخت گزارش اکسل",
}
BOOL_KEYS = ("hours_enabled", "eod_enabled")


@app.get("/api/settings")
def api_get_settings():
    return jsonify(db.get_settings())


@app.post("/api/settings")
def api_save_settings():
    body = request.get_json(silent=True) or {}
    clean: dict = {}
    for key in BOOL_KEYS:
        if key in body:
            clean[key] = "1" if str(body[key]).lower() in ("1", "true", "on") else "0"
    for key, label in HOUR_LABELS.items():
        if key in body:
            val = str(body[key] or "").strip()
            if not db.is_hhmm(val):
                return jsonify({"error": f"«{label}» معتبر نیست؛ قالب HH:MM"}), 400
            clean[key] = val
    if not clean:
        return jsonify({"error": "هیچ تنظیمی ارسال نشد"}), 400
    return jsonify(db.save_settings(clean))


@app.get("/api/reports")
def api_reports():
    if not REPORTS_DIR.exists():
        return jsonify([])
    files = sorted(REPORTS_DIR.glob("attendance_*.xlsx"), reverse=True)
    return jsonify([
        {
            "name": f.name,
            "date": f.stem.replace("attendance_", ""),
            "size_kb": round(f.stat().st_size / 1024, 1),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            "url": f"/report-file/{f.name}",
        }
        for f in files[:30]
    ])


@app.get("/report-file/<path:name>")
def report_file(name: str):
    if not name.endswith(".xlsx") or "/" in name or "\\" in name:
        return jsonify({"error": "فایل نامعتبر"}), 400
    return send_from_directory(REPORTS_DIR, name, as_attachment=True)


@app.post("/api/export")
def api_export():
    body = request.get_json(silent=True) or {}
    raw = str(body.get("date") or "").strip()
    try:
        day = datetime.strptime(raw, "%Y-%m-%d").date() if raw else date.today()
    except ValueError:
        return jsonify({"error": "تاریخ معتبر نیست"}), 400
    path = export.build(day)
    last = db.get_settings().get("eod_last_date") or ""
    if day.isoformat() > last:
        db.save_settings({"eod_last_date": day.isoformat()})
    return jsonify({"file": path.name, "url": f"/report-file/{path.name}", "date": day.isoformat()})


def run_scheduler_once() -> None:
    """یک بار بررسی می‌کند که فایل اکسل امروز/دیروز باید ساخته شود (با جبران صبح)."""
    s = db.get_settings()
    if s.get("eod_enabled") != "1":
        return
    now = datetime.now()
    try:
        hh, mm = map(int, s["eod_time"].split(":"))
    except ValueError:
        return
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    due = now.date() if now >= target else now.date() - timedelta(days=1)
    last = s.get("eod_last_date") or ""
    if last >= due.isoformat():
        return
    if last:
        try:
            first = date.fromisoformat(last) + timedelta(days=1)
        except ValueError:
            first = due
    else:
        first = due
    if (due - first).days > 6:            # جبران حداکثر ۷ روز عقب‌افتادگی
        first = due - timedelta(days=6)
    day = first
    while day <= due:
        path = export.build(day)
        db.save_settings({"eod_last_date": day.isoformat()})
        print(f"📊 گزارش اکسل خودکار ساخته شد: {path.name}")
        day += timedelta(days=1)


def _scheduler_loop() -> None:
    while True:
        try:
            run_scheduler_once()
        except Exception as err:  # گزارش شبانه هرگز نباید داشبورد را بخواباند
            print("خطای زمان‌بندی گزارش:", err)
        time.sleep(30)


def _date_arg():
    raw = request.args.get("date")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()


def _warm_up_engine() -> None:
    """مدل InsightFace را هنگام بالا آمدن لود می‌کند تا اولین بررسی چهره چند ثانیه معطل نشود."""
    try:
        engine.get_face_app()
        print("مدل چهره آماده است.")
    except Exception as err:
        print(f"هشدار: مدل چهره لود نشد ({err}) — با اولین استفاده دوباره تلاش می‌شود.")


if __name__ == "__main__":
    db.init_db()
    threading.Thread(target=_warm_up_engine, name="face-warmup", daemon=True).start()
    threading.Thread(target=_scheduler_loop, name="eod-report", daemon=True).start()
    print("داشبورد: http://127.0.0.1:8050")
    app.run(host="127.0.0.1", port=8050, debug=False, threaded=True)
