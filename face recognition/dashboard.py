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
from flask import Flask, jsonify, request, send_from_directory

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
    display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;position:sticky;top:0;z-index:5;
    transition:box-shadow .2s ease}
  header.scrolled{box-shadow:0 6px 16px rgba(16,24,40,.07)}
  .brand{display:flex;align-items:center;gap:10px}
  .brand .dot{width:10px;height:10px;border-radius:50%;background:var(--green-dot);
    box-shadow:0 0 0 4px var(--green)}
  .brand h1{font-size:16px;font-weight:800;margin:0}
  .brand span{color:var(--muted);font-size:12px}
  .hgroup{display:flex;gap:12px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
  .hmeta{display:flex;flex-direction:column;align-items:flex-start;gap:2px}
  #clock{color:var(--muted);font-size:12.5px;direction:ltr}
  input[type=date]{font:inherit;font-size:13px;padding:7px 12px;border:1px solid var(--line);
    border-radius:10px;background:var(--card);color:var(--ink);box-shadow:var(--shadow)}
  main{max-width:1120px;margin:0 auto;padding:26px 20px;display:grid;gap:18px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
    padding:16px 18px;box-shadow:var(--shadow);display:flex;justify-content:space-between;align-items:center;
    transition:transform .18s ease,box-shadow .18s ease}
  .card:hover{transform:translateY(-2px);box-shadow:0 2px 4px rgba(16,24,40,.06),0 10px 24px rgba(16,24,40,.08)}
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
  .panel h2 .ic{width:28px;height:28px;border-radius:9px}
  .panel h2 .ic svg{width:15px;height:15px}
  .panel h2 .count{background:var(--soft);border:1px solid var(--line);color:var(--muted);
    border-radius:999px;font-size:11.5px;padding:1px 9px;font-weight:600}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{padding:9px 10px;text-align:right;border-bottom:1px solid var(--soft)}
  tr:last-child td{border-bottom:none}
  th{color:var(--muted);font-weight:600;font-size:11.5px;background:var(--card);
    position:sticky;top:70px;z-index:2;border-bottom:1px solid var(--line)}
  tbody tr:nth-child(even){background:#fafcfe}
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
    color:var(--ink);border-radius:10px;padding:8px 16px;cursor:pointer;box-shadow:var(--shadow);
    white-space:nowrap;transition:transform .12s ease,border-color .15s ease,background .15s ease}
  .btn:hover{border-color:#cfd8e3}
  .btn:active{transform:translateY(1px)}
  .btn.primary{background:linear-gradient(180deg,#358a59,#2f7d51);border-color:var(--green-ink);color:#fff}
  .btn.primary:hover{background:linear-gradient(180deg,#2f7d51,#276b45)}
  .btn.tiny{padding:4px 11px;font-size:12px;border-radius:8px;box-shadow:none}
  .btn.danger{color:var(--red-ink);background:var(--red);border-color:#f2d9d9}
  td.act{white-space:nowrap}
  td.act .btn{margin-left:6px}
  .backdrop{position:fixed;inset:0;background:rgba(15,23,42,.45);display:none;place-items:center;z-index:20;padding:20px}
  .backdrop.on{display:grid}
  .modal{background:var(--card);border-radius:var(--radius);box-shadow:0 20px 50px rgba(16,24,40,.25);
    width:min(460px,100%);padding:22px 24px}
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
  .photobox{display:flex;gap:14px;align-items:center}
  .preview{width:86px;height:86px;border-radius:14px;border:1px dashed #cfd8e3;background:var(--soft);
    display:grid;place-items:center;overflow:hidden;flex-shrink:0;color:var(--muted);font-size:11px;text-align:center;padding:4px}
  .preview img{width:100%;height:100%;object-fit:cover;display:block}
  .pbtns{display:flex;flex-wrap:wrap;gap:7px}
  .pnote{color:var(--muted);font-size:11.5px;margin:8px 0 0;line-height:1.8}
  .thumb{width:32px;height:32px;border-radius:9px;object-fit:cover;display:block;background:var(--soft)}
  td.pic{width:44px}
  .cammodal{width:min(560px,100%)}
  #camVideo{width:100%;max-height:56vh;background:#0f172a;border-radius:12px;display:block;
    aspect-ratio:4/3;object-fit:cover}
  .camhint{margin:0 0 10px;color:var(--muted);font-size:12px;line-height:1.8;min-height:20px}
  .files{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
  .files a{font-size:12px;font-weight:600;color:var(--blue-ink);background:var(--blue);
    border:1px solid #d7e5f3;border-radius:9px;padding:5px 11px;text-decoration:none;direction:ltr}
  .files a:hover{background:#dceaf7}
  .files .none{color:var(--muted);font-size:12px;font-weight:400}
  .switch input{width:15px;height:15px}
  button:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--green-dot);
    outline-offset:2px;border-radius:8px}
  .upd{color:var(--muted);font-size:11.5px;display:flex;align-items:center;gap:6px}
  .upd::before{content:'';width:6px;height:6px;border-radius:50%;background:var(--green-dot)}
  .upd.stale::before{background:var(--red-ink)}
  .col b{font-size:10.5px;color:var(--muted);font-weight:600}
  @media (prefers-reduced-motion: reduce){
    *,*::before,*::after{animation-duration:.01ms !important;animation-iteration-count:1 !important;
      transition-duration:.01ms !important}
  }
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
    <div class="hmeta">
      <span id="clock"></span>
      <span class="sub-fa" id="updated" title="آخرین بار داده‌ها چه زمانی تازه شد"></span>
    </div>
  </div>
</header>
<main>
  <div class="offline" id="offline" role="alert">اتصال به سرور قطع است — با `.venv\\Scripts\\python dashboard.py` دوباره اجرا کنید</div>
  <section class="cards" id="cards"></section>
  <section class="grid2">
    <div class="panel">
      <h2><span class="ic green"><svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12l9-9 9 9M5 10v10a1 1 0 0 0 1 1h3v-6h6v6h3a1 1 0 0 0 1-1V10"/></svg></span>الان داخل هستند <span class="count" id="insideCount">—</span></h2>
      <div id="inside"></div>
    </div>
    <div class="panel">
      <h2><span class="ic blue"><svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 20V10m8 10V4m8 16v-8"/></svg></span>نمای ساعتی ورود</h2>
      <div class="chart" id="chart"></div>
      <div class="legend"><span><i style="background:var(--green)"></i>بیشترین تردد</span>
        <span><i style="background:var(--blue)"></i>سایر ساعت‌ها</span></div>
    </div>
  </section>
  <section class="panel">
    <h2><span class="ic amber"><svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/></svg></span>ساعت مجاز ورود و خروج <span class="sub-fa" id="hoursState">—</span></h2>
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
    <h2><span class="ic blue"><svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/></svg></span>رویدادهای روز <span class="sub-fa" id="evtDay"></span><span class="count" id="evtCount">—</span></h2>
    <div id="events"></div>
  </section>
  <section class="panel">
    <h2><span class="ic green"><svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4v11m0 0l-4-4m4 4l4-4M4 20h16"/></svg></span>گزارش اکسل آخر شب <span class="sub-fa" id="eodState">—</span></h2>
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
    <h2><span class="ic blue"><svg fill="none" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-1a4 4 0 0 0-4-4h-4a4 4 0 0 0-4 4v1M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8m8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6M3 20v-1a4 4 0 0 1 4-4h2"/></svg></span>گالری چهره‌ها و اطلاعات دانشجویان <span class="count" id="stCount">—</span></h2>
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
        <label>عکس دانشجو</label>
        <div class="photobox">
          <div class="preview" id="preview">بدون عکس</div>
          <div class="pbtns">
            <button type="button" class="btn tiny" onclick="document.getElementById('fFile').click()">آپلود فایل عکس</button>
            <button type="button" class="btn tiny" onclick="openCam()">عکس با دوربین</button>
            <button type="button" class="btn tiny danger" onclick="clearPhoto()">حذف عکس</button>
            <input type="file" id="fFile" accept="image/*" hidden onchange="pickFile(this)">
          </div>
        </div>
        <p class="pnote" id="pNote">اگر عکس آماده دارید فایلش را بدهید، اگر نه با «عکس با دوربین» همین‌جا بگیرید. عکس ذخیره می‌شود و چهره‌اش خودکار به گالری تشخیص افزوده می‌شود تا دانشجو بدون enroll.py هم شناسایی شود.</p>
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
    <h3>عکس با دوربین</h3>
    <p class="camhint" id="camHint">در حال راه‌اندازی دوربین…</p>
    <video id="camVideo" playsinline muted></video>
    <div class="row">
      <button type="button" class="btn primary" id="camShot" onclick="captureCam()" disabled>ثبت عکس</button>
      <button type="button" class="btn" onclick="closeCam()">بستن</button>
    </div>
  </div>
</div>
<canvas id="upCanvas" hidden></canvas>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
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
    <div class="col ${buckets[h] === max ? 'hot' : ''}" title="${buckets[h]} ورود در ساعت ${h}">
      <div class="bar" style="height:${18 + 82 * buckets[h] / max}%"></div>
      <b>${fmt(buckets[h])}</b>
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
    const u = document.getElementById('updated');
    u.textContent = 'تازه‌سازی ' + new Date().toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    u.classList.remove('stale');
  } catch {
    document.getElementById('offline').classList.add('on');
    document.getElementById('updated').classList.add('stale');
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
        <td class="num">${fmt(p.samples)}</td>
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
  photoData = null; photoRemove = false; existingPhoto = !!(p && p.photo);
  paintPreview(p ? { id: p.id, v: p.photo_v } : null);
  document.getElementById('backdrop').classList.add('on');
  document.getElementById('fName').focus();
}
function closeModal(){
  document.getElementById('backdrop').classList.remove('on');
  document.getElementById('fFile').value = '';
  photoData = null;
}
/* ---------- عکس دانشجو: آپلود فایل یا گرفتن با دوربین ---------- */
let photoData = null;        // data URL عکس انتخاب‌شده (هنوز ذخیره نشده)
let photoRemove = false;     // درخواست حذف عکس ذخیره‌شده
let existingPhoto = false;
function paintPreview(saved){
  const box = document.getElementById('preview');
  if (photoData){ box.innerHTML = `<img src="${photoData}" alt="پیش‌نمایش عکس">`; return; }
  if (saved && existingPhoto && !photoRemove){
    box.innerHTML = `<img src="/photo/${saved.id}?v=${saved.v}" alt="عکس فعلی">`; return;
  }
  box.textContent = 'بدون عکس';
}
function scaleToCanvas(img, maxW){
  const c = document.getElementById('upCanvas');
  const k = Math.min(1, maxW / (img.width || maxW));
  c.width = Math.round((img.width || maxW) * k);
  c.height = Math.round((img.height || maxW) * k);
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  return c.toDataURL('image/jpeg', 0.9);
}
function pickFile(input){
  const f = input.files && input.files[0];
  if (!f) return;
  const url = URL.createObjectURL(f);
  const img = new Image();
  img.onload = () => {
    photoData = scaleToCanvas(img, 720);
    URL.revokeObjectURL(url);
    paintPreview(null);
    toast('عکس انتخاب شد — «ذخیره» را بزنید');
  };
  img.onerror = () => { URL.revokeObjectURL(url); toast('این فایل تصویر خوانده نشد', true); };
  img.src = url;
}
function clearPhoto(){
  photoData = null;
  document.getElementById('fFile').value = '';
  if (existingPhoto) photoRemove = true;
  paintPreview(null);
}
let camStream = null;
async function openCam(){
  document.getElementById('camBackdrop').classList.add('on');
  document.getElementById('camHint').textContent = 'در حال راه‌اندازی دوربین…';
  document.getElementById('camShot').disabled = true;
  const v = document.getElementById('camVideo');
  try {
    camStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }, audio: false });
    v.srcObject = camStream;
    await v.play();
    document.getElementById('camHint').textContent =
      'صورت را رو به دوربین و کامل در کادر نگه دارید (نور مناسب مهم است)، سپس «ثبت عکس».';
    document.getElementById('camShot').disabled = false;
  } catch (err) {
    document.getElementById('camHint').textContent =
      `دوربین باز نشد (${err && err.name ? err.name : 'خطا'}) — اگر وب‌کم دارید در Windows Settings › Privacy › Camera دسترسی برنامه‌های دسکتاپ را فعال کنید، یا از «آپلود فایل عکس» استفاده کنید.`;
  }
}
function stopCam(){
  if (camStream){ camStream.getTracks().forEach(t => t.stop()); camStream = null; }
  const v = document.getElementById('camVideo');
  v.srcObject = null;
}
function closeCam(){ stopCam(); document.getElementById('camBackdrop').classList.remove('on'); }
function captureCam(){
  const v = document.getElementById('camVideo'), c = document.getElementById('upCanvas');
  c.width = v.videoWidth || 640; c.height = v.videoHeight || 480;
  const k = Math.min(1, 720 / c.width);
  c.width = Math.round(c.width * k); c.height = Math.round(c.height * k);
  c.getContext('2d').drawImage(v, 0, 0, c.width, c.height);
  photoData = c.toDataURL('image/jpeg', 0.92);
  photoRemove = false;
  closeCam();
  paintPreview(null);
  toast('عکس گرفته شد — «ذخیره» را بزنید');
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
  if (photoRemove) body.photo_remove = true;
  const btn = document.getElementById('mSave'); btn.disabled = true;
  const note = document.getElementById('pNote');
  const original = note.textContent;
  try {
    if (photoData) note.textContent = 'در حال بررسی چهره عکس… (اولین بار چند ثانیه طول می‌کشد)';
    const d = await req(id ? `/api/students/${id}` : '/api/students', id ? 'PUT' : 'POST', body);
    closeModal();
    let msg = id ? 'اطلاعات به‌روزرسانی شد' : 'دانشجو اضافه شد';
    if (d.face_added) msg += ` — چهره از عکس ثبت شد (${d.face_added} نمونه به گالری اضافه شد)`;
    toast(msg);
    if (d.photo_warning) toast(d.photo_warning, true);
    await refresh();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
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
  closeModal(); closeCal();
  if (document.getElementById('camBackdrop').classList.contains('on')) closeCam();
});
document.getElementById('day').value = isoOf(localToday());
const j0 = selJal(); view = { jy: j0.jy, jm: j0.jm };
paintDayBtn();
tick(); setInterval(tick, 1000);
addEventListener('scroll', () => document.querySelector('header').classList.toggle('scrolled', scrollY > 4), { passive: true });
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
    return PAGE


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


def _photo_file(row):
    """مسیر فایل عکس دانشجو؛ None اگر وجود ندارد."""
    name = (row["photo"] or "") if "photo" in row.keys() else ""
    if not name:
        return None
    path = PHOTOS_DIR / name
    return path if path.exists() else None


def _store_photo(student_id: int, data_url: str) -> tuple[str | None, int, str | None]:
    """ذخیره عکس و افزودن بردار چهره‌اش به گالری. برمی‌گرداند (فایل, تعداد بردار, هشدار)."""
    payload = data_url.split("base64,", 1)[-1] if "base64," in data_url else data_url
    try:
        raw = base64.b64decode(payload)
    except Exception:
        return None, 0, "داده عکس معتبر نیست"
    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return None, 0, "فایل تصویر خوانده نشد؛ JPEG یا PNG بفرستید"
    PHOTOS_DIR.mkdir(exist_ok=True)
    filename = f"student_{student_id}.jpg"
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not ok:
        return None, 0, "ذخیره عکس ناموفق بود"
    (PHOTOS_DIR / filename).write_bytes(buf.tobytes())
    face = engine.capture_frame_for_enroll(frame)
    if face is None:
        return filename, 0, "چهره واضح در عکس پیدا نشد؛ عکس ذخیره شد ولی دانشجو هنوز با دوربین شناسایی نمی‌شود"
    engine.add_embeddings(student_id, [face.embedding])
    return filename, 1, None


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
    data_url = body.get("photo_data")
    if isinstance(data_url, str) and data_url.strip():
        filename, added, warning = _store_photo(student_id, data_url)
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


if __name__ == "__main__":
    db.init_db()
    threading.Thread(target=_scheduler_loop, name="eod-report", daemon=True).start()
    print("داشبورد: http://127.0.0.1:8050")
    app.run(host="127.0.0.1", port=8050, debug=False)
