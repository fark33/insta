# -*- coding: utf-8 -*-
"""
🎲 بازی آنلاین «منچ» (Ludo) - دو نفره و چهار نفره
====================================================
یک فایل کامل شامل سرور (Flask + Socket.IO) + رابط کاربری (HTML/CSS/JS).

نحوه اجرا روی Google Colab:
----------------------------
یک سلول جدید در بالای این فایل اجرا کنید:

    !pip install flask flask-socketio eventlet pyngrok -q

سپس (اختیاری ولی توصیه‌شده) توکن رایگان ngrok را ثبت کنید تا لینک عمومی بگیرید:
    از https://dashboard.ngrok.com/get-started/your-authtoken توکن را کپی کنید

بعد این فایل را اجرا کنید:
    !python ludo_online.py

یا داخل Colab مستقیم با:
    import ludo_online
    ludo_online.run(ngrok_token="TOKEN_شما")

با اجرای فایل، یک لینک عمومی چاپ می‌شود. آن را باز کنید، بازی بسازید،
لینک دعوت را برای بقیه بفرستید تا خودکار به بازی اضافه شوند.
"""

import os
import random
import string
import time
import threading

from flask import Flask, request, render_template_string, redirect, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room

# ============================================================
#  تنظیمات بازی و منطق هسته‌ی منچ
# ============================================================

COLORS_4 = ["red", "green", "yellow", "blue"]
COLORS_2 = ["red", "yellow"]  # دو رنگ روبه‌رو برای بازی دو نفره

COLOR_LABELS = {
    "red": "قرمز",
    "green": "سبز",
    "yellow": "زرد",
    "blue": "آبی",
}

# آفست شروع هر رنگ روی مسیر ۵۲ خانه‌ای مشترک
START_OFFSET = {"red": 0, "green": 13, "yellow": 26, "blue": 39}

# خانه‌های امن (ستاره) روی مسیر مشترک (اندیس مطلق ۰..۵۱)
SAFE_ABS = {0, 8, 13, 21, 26, 34, 39, 47}

HOME_ENTRY_STEP = 51   # بعد از این تعداد قدم روی مسیر مشترک، وارد راهروی خانه می‌شود
HOME_COL_LEN = 6       # طول راهروی خانه‌ی هر رنگ
FINISH_STEP = HOME_ENTRY_STEP + HOME_COL_LEN  # = 57 -> رسیدن کامل به خانه

rooms = {}          # room_id -> room dict
rooms_lock = threading.Lock()


def new_room_id():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def make_room(max_players, host_sid, host_name):
    rid = new_room_id()
    while rid in rooms:
        rid = new_room_id()
    colors = COLORS_2 if max_players == 2 else COLORS_4
    room = {
        "id": rid,
        "max_players": max_players,
        "colors": colors,
        "players": [],   # list of dicts
        "turn": 0,
        "dice": None,
        "movable": [],
        "state": "waiting",   # waiting | playing | finished
        "winner": None,
        "consecutive_sixes": 0,
        "log": [],
        "created": time.time(),
    }
    rooms[rid] = room
    add_player(room, host_sid, host_name)
    return room


def add_player(room, sid, name):
    used = {p["color"] for p in room["players"]}
    color = next(c for c in room["colors"] if c not in used)
    player = {
        "sid": sid,
        "name": name or COLOR_LABELS[color],
        "color": color,
        "tokens": [0, 0, 0, 0],   # 0 = خونه/یارد , 1..57 مسیر
        "connected": True,
        "finished_tokens": 0,
    }
    room["players"].append(player)
    return player


def public_state(room):
    """داده‌ای که برای همه‌ی کلاینت‌ها فرستاده می‌شود."""
    return {
        "id": room["id"],
        "max_players": room["max_players"],
        "state": room["state"],
        "players": [
            {
                "name": p["name"],
                "color": p["color"],
                "tokens": p["tokens"],
                "connected": p["connected"],
            }
            for p in room["players"]
        ],
        "turn": room["turn"],
        "dice": room["dice"],
        "movable": room["movable"],
        "winner": room["winner"],
        "log": room["log"][-8:],
    }


def add_log(room, text):
    room["log"].append(text)
    room["log"] = room["log"][-30:]


def current_player(room):
    return room["players"][room["turn"]]


def abs_pos(color, step):
    """اندیس مطلق خانه روی مسیر مشترک برای یک رنگ و تعداد قدم (۱..۵۱)."""
    return (START_OFFSET[color] + (step - 1)) % 52


def movable_tokens_for(room, player, dice):
    """اندیس مهره‌هایی که با این عدد تاس می‌توانند حرکت کنند."""
    movable = []
    for i, s in enumerate(player["tokens"]):
        if s == FINISH_STEP:
            continue  # قبلا رسیده خونه
        if s == 0:
            if dice == 6:
                movable.append(i)
        else:
            if s + dice <= FINISH_STEP:
                movable.append(i)
    return movable


def do_move(room, player, token_idx, dice):
    """اجرای حرکت یک مهره؛ خروجی: پیام لاگ و اینکه آیا نوبت اضافه لازم است."""
    extra_turn = False
    s = player["tokens"][token_idx]
    if s == 0 and dice == 6:
        new_s = 1
    else:
        new_s = s + dice

    player["tokens"][token_idx] = new_s
    add_log(room, f"{COLOR_LABELS[player['color']]} مهره {token_idx+1} را حرکت داد.")

    if new_s == FINISH_STEP:
        player["finished_tokens"] += 1
        add_log(room, f"🏠 {COLOR_LABELS[player['color']]} یک مهره را به خانه رساند!")
        extra_turn = True
    elif new_s <= HOME_ENTRY_STEP:
        # روی مسیر مشترک -> بررسی گرفتن حریف
        landing_abs = abs_pos(player["color"], new_s)
        if landing_abs not in SAFE_ABS:
            for other in room["players"]:
                if other is player:
                    continue
                for j, os_ in enumerate(other["tokens"]):
                    if 1 <= os_ <= HOME_ENTRY_STEP and abs_pos(other["color"], os_) == landing_abs:
                        other["tokens"][j] = 0
                        add_log(
                            room,
                            f"💥 {COLOR_LABELS[player['color']]} مهره‌ی {COLOR_LABELS[other['color']]} را گرفت!",
                        )
                        extra_turn = True

    if dice == 6:
        extra_turn = True

    if player["finished_tokens"] == 4:
        room["state"] = "finished"
        room["winner"] = player["color"]
        add_log(room, f"🏆 {COLOR_LABELS[player['color']]} برنده‌ی بازی شد!")

    return extra_turn


def advance_turn(room):
    n = len(room["players"])
    room["turn"] = (room["turn"] + 1) % n
    room["dice"] = None
    room["movable"] = []
    room["consecutive_sixes"] = 0


# ============================================================
#  Flask + Socket.IO
# ============================================================

app = Flask(__name__)
app.config["SECRET_KEY"] = "ludo-secret-" + new_room_id()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

sid_room_map = {}  # sid -> room_id (برای مدیریت قطع ارتباط)


# ---------------------------------------------------------------------------
#  قالب HTML / CSS / JS  (تک فایلی)
# ---------------------------------------------------------------------------
PAGE_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🎲 منچ آنلاین</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root{
    --bg1:#1e0a3c; --bg2:#3a0f5e; --gold:#ffd166; --card:#241546cc;
    --red:#e63946; --green:#2a9d8f; --yellow:#f4c542; --blue:#3d6bff;
    --txt:#f4f1ff;
  }
  *{box-sizing:border-box;}
  body{
    margin:0; min-height:100vh; font-family:'Vazirmatn',Tahoma,sans-serif;
    background:radial-gradient(circle at 30% 20%, var(--bg2), var(--bg1) 70%);
    color:var(--txt); display:flex; flex-direction:column; align-items:center;
    padding:18px;
  }
  h1{ font-size:1.9rem; margin:8px 0 2px; text-shadow:0 2px 12px #000a;}
  .sub{opacity:.75; margin-bottom:14px; font-size:.9rem;}
  .card{
    background:var(--card); border:1px solid #ffffff22; border-radius:18px;
    padding:22px 26px; max-width:460px; width:100%; box-shadow:0 10px 30px #0006;
    backdrop-filter: blur(6px);
  }
  .btn{
    display:inline-block; border:none; border-radius:12px; padding:12px 18px;
    font-size:1rem; font-weight:700; cursor:pointer; margin:6px 4px;
    background:linear-gradient(135deg,var(--gold),#ff9f1c); color:#3a1c00;
    transition:.15s transform;
  }
  .btn:hover{ transform:translateY(-2px) scale(1.02); }
  .btn.secondary{ background:#ffffff22; color:var(--txt); }
  .btn.small{ padding:8px 12px; font-size:.85rem; }
  input[type=text]{
    width:100%; padding:11px 14px; border-radius:10px; border:1px solid #ffffff33;
    background:#ffffff10; color:var(--txt); font-size:1rem; margin:6px 0 14px;
  }
  input::placeholder{color:#ffffff88;}
  label{font-size:.85rem; opacity:.85;}
  .row{display:flex; gap:10px; justify-content:center; flex-wrap:wrap;}
  .hidden{display:none !important;}
  .invite-box{
    background:#00000033; border:1px dashed var(--gold); border-radius:12px;
    padding:12px; margin-top:10px; word-break:break-all; font-size:.85rem;
  }
  #boardWrap{ display:flex; gap:22px; flex-wrap:wrap; justify-content:center; align-items:flex-start; margin-top:10px;}
  #board{
    display:grid; grid-template-columns:repeat(15,minmax(20px,32px));
    grid-template-rows:repeat(15,minmax(20px,32px));
    background:#120826; border:4px solid #00000055; border-radius:10px;
    box-shadow:0 12px 30px #0007; position:relative;
  }
  .cell{ border:1px solid #ffffff0f; position:relative; }
  .yard-red{background:#e6394633;} .yard-green{background:#2a9d8f33;}
  .yard-yellow{background:#f4c54233;} .yard-blue{background:#3d6bff33;}
  .track{background:#ffffff10;}
  .safe{background:#ffd16655 !important;}
  .path-red{background:#e6394655;} .path-green{background:#2a9d8f55;}
  .path-yellow{background:#f4c54255;} .path-blue{background:#3d6bff55;}
  .center{background:linear-gradient(135deg,#e63946,#2a9d8f,#f4c542,#3d6bff);}
  .token{
    width:70%; height:70%; border-radius:50%; position:absolute; top:15%; left:15%;
    border:2px solid #00000066; box-shadow:0 2px 6px #0008; cursor:pointer;
    display:flex; align-items:center; justify-content:center; font-size:.65rem;
    font-weight:800; color:#fff; transition:.25s all;
  }
  .token.red{background:var(--red);} .token.green{background:var(--green);}
  .token.yellow{background:var(--yellow); color:#3a1c00;} .token.blue{background:var(--blue);}
  .token.movable{ outline:3px solid #fff; animation:pulse 1s infinite; z-index:5;}
  @keyframes pulse{ 0%{transform:scale(1);} 50%{transform:scale(1.18);} 100%{transform:scale(1);} }
  #sidePanel{ width:260px; }
  .player-chip{
    display:flex; align-items:center; gap:8px; padding:8px 10px; border-radius:10px;
    margin-bottom:6px; background:#ffffff10; font-size:.9rem;
  }
  .player-chip.active{ box-shadow:0 0 0 2px var(--gold) inset; background:#ffd16622;}
  .dot{width:14px; height:14px; border-radius:50%; flex-shrink:0;}
  .dot.red{background:var(--red);} .dot.green{background:var(--green);}
  .dot.yellow{background:var(--yellow);} .dot.blue{background:var(--blue);}
  #dice{
    width:64px; height:64px; border-radius:14px; background:#fff; color:#111;
    font-size:1.8rem; font-weight:900; display:flex; align-items:center; justify-content:center;
    margin:12px auto; cursor:pointer; box-shadow:0 6px 14px #0008; user-select:none;
    transition:.15s transform;
  }
  #dice:hover{transform:scale(1.05);}
  #dice.disabled{opacity:.4; cursor:not-allowed;}
  #turnBanner{ text-align:center; font-weight:700; margin-bottom:6px; min-height:24px;}
  #log{
    background:#00000033; border-radius:10px; padding:8px 10px; font-size:.78rem;
    max-height:160px; overflow-y:auto; line-height:1.6;
  }
  #winBanner{
    position:fixed; inset:0; background:#000000cc; display:flex; align-items:center;
    justify-content:center; z-index:50; text-align:center; flex-direction:column;
  }
  #winBanner h2{font-size:2.2rem; color:var(--gold);}
  @media (max-width:720px){
    #board{grid-template-columns:repeat(15,minmax(16px,22px)); grid-template-rows:repeat(15,minmax(16px,22px));}
    #sidePanel{width:100%; max-width:420px;}
  }
</style>
</head>
<body>

<h1>🎲 منچ آنلاین</h1>
<div class="sub">دو نفره یا چهار نفره &middot; دعوت با لینک &middot; بی‌درنگ</div>

<!-- ===================== لابی ===================== -->
<div id="lobby" class="card">
  <div id="lobbyHome">
    <label>اسم شما</label>
    <input id="nameInput" type="text" placeholder="مثلاً: علی" maxlength="16">
    <div class="row">
      <button class="btn" onclick="createGame(2)">🎮 بازی دو نفره بساز</button>
      <button class="btn" onclick="createGame(4)">👥 بازی چهار نفره بساز</button>
    </div>
    <hr style="border-color:#ffffff22; margin:16px 0;">
    <label>یا با کد اتاق وارد شو</label>
    <input id="roomCodeInput" type="text" placeholder="کد اتاق (مثلا AB12CD)" maxlength="8">
    <div class="row"><button class="btn secondary" onclick="joinByCode()">ورود به اتاق</button></div>
  </div>

  <div id="lobbyWaiting" class="hidden">
    <p>در انتظار بازیکن‌ها... (<span id="waitCount"></span>)</p>
    <div id="waitPlayers"></div>
    <div class="invite-box">
      🔗 لینک دعوت:<br>
      <b id="inviteLink"></b>
    </div>
    <div class="row">
      <button class="btn small" onclick="copyInvite()">📋 کپی لینک</button>
      <button class="btn small tg-share-btn hidden" onclick="shareInvite()">📤 اشتراک در تلگرام</button>
    </div>
  </div>
</div>

<!-- ===================== صفحه بازی ===================== -->
<div id="gameScreen" class="hidden" style="width:100%; display:flex; flex-direction:column; align-items:center;">
  <div id="turnBanner"></div>
  <div id="boardWrap">
    <div id="board"></div>
    <div id="sidePanel" class="card">
      <div id="players"></div>
      <div id="dice" class="disabled" onclick="rollDice()">?</div>
      <div id="log"></div>
      <div class="invite-box" style="margin-top:10px;">
        🔗 دعوت دوستان: <b id="inviteLink2"></b>
        <div>
          <button class="btn small" onclick="copyInvite()">📋 کپی</button>
          <button class="btn small tg-share-btn hidden" onclick="shareInvite()">📤 اشتراک در تلگرام</button>
        </div>
      </div>
    </div>
  </div>
</div>

<div id="winBanner" class="hidden">
  <h2 id="winText"></h2>
  <button class="btn" onclick="location.reload()">🔄 بازی جدید</button>
</div>

<script>
// -------- تشخیص محیط تلگرام (Telegram Mini App) --------
// اگر بات را طبق راهنمای «telegram_bot.py» ست کردید، اسم بات خودتان را اینجا بگذارید
// (بدون @) تا دکمه‌ی «اشتراک در تلگرام» لینک دعوت درستی بسازد.
const BOT_USERNAME = "YOUR_BOT_USERNAME";

const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
let tgUserName = null;
if (tg) {
  tg.ready();
  tg.expand();
  try { document.body.style.background = 'transparent'; } catch(e){}
  const u = tg.initDataUnsafe && tg.initDataUnsafe.user;
  if (u) { tgUserName = (u.first_name || '') + (u.last_name ? (' ' + u.last_name) : ''); }
}

const socket = io();
let myColor = null;
let roomId = "{{ initial_room or '' }}";
let joinedFromLink = !!roomId;

// ---------- نقشه‌ی مختصات صفحه (۱۵×۱۵) ----------
const RING = [
 [6,1],[6,2],[6,3],[6,4],[6,5],
 [5,6],[4,6],[3,6],[2,6],[1,6],[0,6],
 [0,7],
 [0,8],[1,8],[2,8],[3,8],[4,8],[5,8],
 [6,9],[6,10],[6,11],[6,12],[6,13],[6,14],
 [7,14],
 [8,14],[8,13],[8,12],[8,11],[8,10],[8,9],
 [9,8],[10,8],[11,8],[12,8],[13,8],[14,8],
 [14,7],
 [14,6],[13,6],[12,6],[11,6],[10,6],[9,6],
 [8,5],[8,4],[8,3],[8,2],[8,1],[8,0],
 [7,0],
 [6,0]
];
const START_OFFSET = {red:0, green:13, yellow:26, blue:39};
const SAFE_ABS = new Set([0,8,13,21,26,34,39,47]);
const HOME_COL = {
  red:   [[7,1],[7,2],[7,3],[7,4],[7,5],[7,6]],
  green: [[1,7],[2,7],[3,7],[4,7],[5,7],[6,7]],
  yellow:[[7,13],[7,12],[7,11],[7,10],[7,9],[7,8]],
  blue:  [[13,7],[12,7],[11,7],[10,7],[9,7],[8,7]],
};
const YARD = {
  red:   [[1,1],[1,4],[4,1],[4,4]],
  green: [[1,10],[1,13],[4,10],[4,13]],
  yellow:[[10,10],[10,13],[13,10],[13,13]],
  blue:  [[10,1],[10,4],[13,1],[13,4]],
};
const HOME_ENTRY_STEP = 51, HOME_COL_LEN = 6, FINISH_STEP = 57;

function absPos(color, step){ return (START_OFFSET[color] + (step-1)) % 52; }

function cellCoord(color, step){
  if(step === 0){ return null; } // در یارد جدا رسم می‌شود
  if(step <= HOME_ENTRY_STEP){ return RING[absPos(color, step)]; }
  if(step < FINISH_STEP){ return HOME_COL[color][step-HOME_ENTRY_STEP-1]; }
  return [7,7];
}

// ---------- ساخت صفحه‌ی بازی ----------
function buildBoard(){
  const board = document.getElementById('board');
  board.innerHTML = '';
  const grid = [];
  for(let r=0;r<15;r++){ grid.push(new Array(15).fill(null)); }

  RING.forEach((c,i)=>{
    let cls='track';
    if(SAFE_ABS.has(i)) cls='safe';
    grid[c[0]][c[1]] = cls;
  });
  for(const color of ['red','green','yellow','blue']){
    HOME_COL[color].forEach(c=>{ grid[c[0]][c[1]] = 'path-'+color; });
    YARD[color].forEach(c=>{ /* پر می‌شود پایین‌تر با ناحیه‌ی رنگی بزرگ */ });
  }
  // نواحی یارد رنگی (۶×۶ در هر گوشه)
  const yardBlocks = {
    red:[0,0], green:[0,9], yellow:[9,9], blue:[9,0]
  };
  for(const color in yardBlocks){
    const [r0,c0] = yardBlocks[color];
    for(let r=r0;r<r0+6;r++) for(let c=c0;c<c0+6;c++){
      if(grid[r][c]===null) grid[r][c] = 'yard-'+color;
    }
  }
  grid[7][7] = 'center';

  for(let r=0;r<15;r++){
    for(let c=0;c<15;c++){
      const div = document.createElement('div');
      div.className = 'cell ' + (grid[r][c] || '');
      div.id = 'cell-'+r+'-'+c;
      board.appendChild(div);
    }
  }
}

function clearTokens(){
  document.querySelectorAll('.token').forEach(t=>t.remove());
}

function renderState(state){
  clearTokens();
  const board = document.getElementById('board');
  state.players.forEach((p, pi)=>{
    p.tokens.forEach((step, ti)=>{
      const el = document.createElement('div');
      el.className = 'token ' + p.color;
      el.textContent = (ti+1);
      let coord;
      if(step === 0){
        coord = YARD[p.color][ti];
      } else {
        coord = cellCoord(p.color, step);
      }
      const cell = document.getElementById('cell-'+coord[0]+'-'+coord[1]);
      if(cell){ cell.appendChild(el); }

      const isMyTurn = state.players[state.turn].color === myColor;
      if(isMyTurn && p.color === myColor && state.movable.includes(ti)){
        el.classList.add('movable');
        el.onclick = ()=> moveToken(ti);
      }
    });
  });

  // پنل بازیکنان
  const playersDiv = document.getElementById('players');
  playersDiv.innerHTML = '';
  state.players.forEach((p, i)=>{
    const chip = document.createElement('div');
    chip.className = 'player-chip' + (i===state.turn ? ' active' : '');
    chip.innerHTML = `<span class="dot ${p.color}"></span> ${p.name} ${p.connected? '' : '(قطع)'} — خانه: ${p.tokens.filter(t=>t===57).length}/4`;
    playersDiv.appendChild(chip);
  });

  // تاس
  const dice = document.getElementById('dice');
  dice.textContent = state.dice || '?';
  const myTurnNow = state.players[state.turn] && state.players[state.turn].color === myColor;
  if(myTurnNow && state.state === 'playing' && (state.dice === null)){
    dice.classList.remove('disabled');
  } else {
    dice.classList.add('disabled');
  }

  document.getElementById('turnBanner').textContent =
    state.state === 'finished' ? '' :
    (myTurnNow ? '🎯 نوبت شماست!' : `⏳ نوبت ${state.players[state.turn].name}`);

  document.getElementById('log').innerHTML = state.log.map(l=>'<div>'+l+'</div>').reverse().join('');

  if(state.state === 'finished' && state.winner){
    document.getElementById('winBanner').classList.remove('hidden');
    const winnerP = state.players.find(p=>p.color===state.winner);
    document.getElementById('winText').textContent = '🏆 ' + winnerP.name + ' برنده شد!';
  }
}

// ---------- اکشن‌ها ----------
function getName(){
  return tgUserName || document.getElementById('nameInput').value.trim() || 'بازیکن';
}
function createGame(maxPlayers){
  socket.emit('create_room', {name:getName(), max_players:maxPlayers});
}
function joinByCode(){
  const code = document.getElementById('roomCodeInput').value.trim().toUpperCase();
  if(!code) return alert('کد اتاق را وارد کنید');
  socket.emit('join_room_req', {room_id:code, name:getName()});
}
function rollDice(){
  socket.emit('roll_dice', {room_id: roomId});
}
function moveToken(idx){
  socket.emit('move_token', {room_id: roomId, token_index: idx});
}
function inviteURL(){
  // لینک عادی (برای مرورگر معمولی)
  return window.location.origin + '/game/' + roomId;
}
function telegramInviteURL(){
  // لینک دیپ‌لینک تلگرامی که مستقیم بات را با کد اتاق باز می‌کند
  return `https://t.me/${BOT_USERNAME}?start=${roomId}`;
}
function currentInviteText(){
  return tg ? telegramInviteURL() : inviteURL();
}
function copyInvite(){
  const link = currentInviteText();
  if(navigator.clipboard){
    navigator.clipboard.writeText(link).then(()=>alert('لینک کپی شد ✅')).catch(()=>alert(link));
  } else { alert(link); }
}
function shareInvite(){
  const link = telegramInviteURL();
  const text = encodeURIComponent('بیا با من بازی منچ کن 🎲');
  if(tg){
    tg.openTelegramLink('https://t.me/share/url?url=' + encodeURIComponent(link) + '&text=' + text);
  } else {
    window.open('https://t.me/share/url?url=' + encodeURIComponent(link) + '&text=' + text, '_blank');
  }
}

function refreshInviteBoxes(){
  const text = currentInviteText();
  const el1 = document.getElementById('inviteLink');
  const el2 = document.getElementById('inviteLink2');
  if(el1) el1.textContent = text;
  if(el2) el2.textContent = text;
  document.querySelectorAll('.tg-share-btn').forEach(b=> b.classList.toggle('hidden', !tg));
}

function showWaiting(state){
  document.getElementById('lobbyHome').classList.add('hidden');
  document.getElementById('lobbyWaiting').classList.remove('hidden');
  document.getElementById('waitCount').textContent = state.players.length + ' / ' + state.max_players;
  document.getElementById('waitPlayers').innerHTML = state.players.map(p=>
    `<div class="player-chip"><span class="dot ${p.color}"></span> ${p.name}</div>`).join('');
  refreshInviteBoxes();
}

function showGame(state){
  document.getElementById('lobby').classList.add('hidden');
  document.getElementById('gameScreen').classList.remove('hidden');
  refreshInviteBoxes();
  if(!document.getElementById('board').childElementCount){ buildBoard(); }
  renderState(state);
}

// ---------- سوکت‌ها ----------
socket.on('connect', ()=>{
  if(joinedFromLink){
    const name = tgUserName || prompt('اسم شما برای پیوستن به بازی؟') || 'بازیکن';
    socket.emit('join_room_req', {room_id: roomId, name});
  }
});

socket.on('room_created', (data)=>{
  roomId = data.room_id;
  myColor = data.color;
  history.replaceState(null,'', '/game/'+roomId);
  showWaiting(data.state);
});

socket.on('joined', (data)=>{
  roomId = data.room_id;
  myColor = data.color;
  history.replaceState(null,'', '/game/'+roomId);
  if(data.state.state === 'waiting'){ showWaiting(data.state); }
  else { showGame(data.state); }
});

socket.on('room_update', (state)=>{
  if(state.state === 'waiting'){ showWaiting(state); }
});

socket.on('game_start', (state)=>{ showGame(state); });
socket.on('state_update', (state)=>{ showGame(state); });

socket.on('error_msg', (msg)=>{ alert(msg); });
</script>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(PAGE_TEMPLATE, initial_room=None)


@app.route("/game/<room_id>")
def game_page(room_id):
    return render_template_string(PAGE_TEMPLATE, initial_room=room_id.upper())


# ---------------------------------------------------------------------------
#  Socket.IO events
# ---------------------------------------------------------------------------

@socketio.on("create_room")
def on_create_room(data):
    name = (data.get("name") or "بازیکن")[:16]
    max_players = 2 if data.get("max_players") == 2 else 4
    with rooms_lock:
        room = make_room(max_players, request.sid, name)
    sid_room_map[request.sid] = room["id"]
    join_room(room["id"])
    player = room["players"][0]
    emit("room_created", {"room_id": room["id"], "color": player["color"], "state": public_state(room)})


@socketio.on("join_room_req")
def on_join_room_req(data):
    room_id = (data.get("room_id") or "").upper().strip()
    name = (data.get("name") or "بازیکن")[:16]
    room = rooms.get(room_id)
    if not room:
        emit("error_msg", "اتاقی با این کد پیدا نشد.")
        return

    # اگر بازیکنی با همین sid از قبل عضو است (رفرش صفحه)
    existing = next((p for p in room["players"] if p["sid"] == request.sid), None)
    if existing:
        join_room(room_id)
        emit("joined", {"room_id": room_id, "color": existing["color"], "state": public_state(room)})
        return

    if room["state"] != "waiting":
        emit("error_msg", "بازی از قبل شروع شده و ظرفیت اتاق تکمیل است.")
        return
    if len(room["players"]) >= room["max_players"]:
        emit("error_msg", "اتاق پر است.")
        return

    with rooms_lock:
        player = add_player(room, request.sid, name)
    sid_room_map[request.sid] = room_id
    join_room(room_id)
    add_log(room, f"{player['name']} به بازی پیوست.")

    emit("joined", {"room_id": room_id, "color": player["color"], "state": public_state(room)})

    if len(room["players"]) == room["max_players"]:
        room["state"] = "playing"
        add_log(room, "🎬 بازی شروع شد!")
        socketio.emit("game_start", public_state(room), room=room_id)
    else:
        socketio.emit("room_update", public_state(room), room=room_id)


@socketio.on("roll_dice")
def on_roll_dice(data):
    room = rooms.get((data.get("room_id") or "").upper())
    if not room or room["state"] != "playing":
        return
    player = current_player(room)
    if player["sid"] != request.sid:
        emit("error_msg", "نوبت شما نیست.")
        return
    if room["dice"] is not None:
        return

    dice = random.randint(1, 6)
    room["dice"] = dice

    if dice == 6:
        room["consecutive_sixes"] += 1
    else:
        room["consecutive_sixes"] = 0

    if room["consecutive_sixes"] >= 3:
        add_log(room, f"{COLOR_LABELS[player['color']]} سه شش پشت‌سرهم آورد، نوبت از دست رفت!")
        advance_turn(room)
        socketio.emit("state_update", public_state(room), room=room["id"])
        return

    movable = movable_tokens_for(room, player, dice)
    room["movable"] = movable
    add_log(room, f"{COLOR_LABELS[player['color']]} تاس {dice} انداخت.")

    if not movable:
        add_log(room, "حرکتی ممکن نیست، نوبت بعدی.")
        socketio.emit("state_update", public_state(room), room=room["id"])
        socketio.sleep(1.1)
        advance_turn(room)
        socketio.emit("state_update", public_state(room), room=room["id"])
    else:
        socketio.emit("state_update", public_state(room), room=room["id"])


@socketio.on("move_token")
def on_move_token(data):
    room = rooms.get((data.get("room_id") or "").upper())
    if not room or room["state"] != "playing":
        return
    player = current_player(room)
    if player["sid"] != request.sid:
        return
    idx = data.get("token_index")
    if room["dice"] is None or idx not in room["movable"]:
        return

    extra = do_move(room, player, idx, room["dice"])

    if room["state"] == "finished":
        socketio.emit("state_update", public_state(room), room=room["id"])
        return

    if not extra:
        advance_turn(room)
    else:
        room["dice"] = None
        room["movable"] = []

    socketio.emit("state_update", public_state(room), room=room["id"])


@socketio.on("disconnect")
def on_disconnect():
    room_id = sid_room_map.get(request.sid)
    if not room_id:
        return
    room = rooms.get(room_id)
    if not room:
        return
    player = next((p for p in room["players"] if p["sid"] == request.sid), None)
    if player:
        player["connected"] = False
        add_log(room, f"{player['name']} قطع ارتباط شد.")
        if room["state"] == "waiting":
            room["players"].remove(player)
        socketio.emit("state_update" if room["state"] != "waiting" else "room_update",
                      public_state(room), room=room_id)


# ============================================================
#  اجرا (لوکال یا Colab)
# ============================================================

def _start_server_in_thread(host, port, debug):
    t = threading.Thread(
        target=lambda: socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True),
        daemon=True,
    )
    t.start()
    time.sleep(1.5)  # کمی صبر تا سرور بالا بیاید
    return t


def run(host="0.0.0.0", port=5000, ngrok_token=None, use_localtunnel=False, debug=False):
    """
    اجرای سرور. سه حالت:
      1) run()                         -> فقط لوکال (http://localhost:PORT)
      2) run(ngrok_token="...")        -> لینک عمومی با ngrok (نیاز به توکن رایگان)
      3) run(use_localtunnel=True)     -> لینک عمومی بدون نیاز به هیچ توکن/ثبت‌نام
                                          (برای تست سریع، مخصوصاً وقتی توکن ngrok ندارید)
    """
    if ngrok_token:
        from pyngrok import ngrok as ngrok_mod
        ngrok_mod.set_auth_token(ngrok_token)
        tunnel = ngrok_mod.connect(port, "http")
        print("=" * 60)
        print(f"🌍 لینک عمومی بازی (ngrok): {tunnel.public_url}")
        print("این لینک را باز کنید، بازی بسازید و لینک دعوت را برای بقیه بفرستید.")
        print("=" * 60)
        socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
        return

    if use_localtunnel:
        import subprocess, re
        # سرور را در یک ترد جدا بالا می‌آوریم تا بتوانیم بعدش تونل بزنیم
        _start_server_in_thread(host, port, debug)
        print("در حال بالا آوردن تونل عمومی (localtunnel)... چند ثانیه صبر کنید.")
        try:
            proc = subprocess.Popen(
                ["npx", "-y", "localtunnel", "--port", str(port)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            )
        except FileNotFoundError:
            print("❌ Node.js/npx پیدا نشد. این سلول را قبلش در Colab اجرا کنید:")
            print("   !apt-get install -y nodejs npm -qq")
            return
        url_pattern = re.compile(r"https://[a-zA-Z0-9\-]+\.loca\.lt")
        for line in proc.stdout:
            m = url_pattern.search(line)
            if m:
                print("=" * 60)
                print(f"🌍 لینک عمومی بازی: {m.group(0)}")
                print("⚠️ اولین بار که این لینک را باز می‌کنید، یک صفحه‌ی")
                print('   "Click to Continue" نشان می‌دهد؛ فقط یک بار کلیک کنید.')
                print("این لینک را برای بقیه هم بفرستید تا وارد بازی شوند.")
                print("=" * 60)
                break
        # پردازش تونل در پس‌زمینه ادامه پیدا می‌کند تا نوت‌بوک بسته شود
        while True:
            time.sleep(3600)

    print("=" * 60)
    print(f"سرور روی http://localhost:{port} در حال اجراست (فقط لوکال).")
    print("برای لینک قابل‌اشتراک با بقیه یکی از این‌ها را صدا بزنید:")
    print('   run(use_localtunnel=True)      # بدون هیچ توکن/ثبت‌نام')
    print('   run(ngrok_token="TOKEN_شما")   # با توکن رایگان ngrok')
    print("=" * 60)
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    token = os.environ.get("NGROK_TOKEN")
    if token:
        run(ngrok_token=token)
    elif os.environ.get("USE_LOCALTUNNEL"):
        run(use_localtunnel=True)
    else:
        run()
