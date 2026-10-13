import os, json, hmac, hashlib, sqlite3, asyncio
from urllib.parse import parse_qsl
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

TOKEN = os.environ["8944919667:AAGmiAACDftIDM69XxWN-qiRbjOgTNHuhVk"]
ADMINS = {int(x) for x in os.environ["7733792615"].split(",")}
URL = os.environ["https://mireillethe33.github.io/Kazik-miniapp/"]
PORT = int(os.environ.get("PORT", 8080))

db = sqlite3.connect("casino.db", check_same_thread=False)
db.execute("create table if not exists p(id integer primary key, un text, st text, ban int default 0, gr text default '[]')")
db.commit()

ITEMS = {"деньги": "money", "money": "money", "победа": "wc", "вв": "wc", "wc": "wc", "щит": "shield", "shield": "shield",
         "удвоитель": "double", "double": "double", "страховка": "insure", "insure": "insure", "буст": "boost", "boost": "boost",
         "ставки": "betup", "betup": "betup", "удача": "luckup", "luckup": "luckup", "глаз": "eye", "eye": "eye",
         "рука": "hand", "hand": "hand", "сброс": "reset", "reset": "reset"}
HELP = ("!выдать @юз предмет [N]\n!выдатьвсем предмет [N]\n!бан @юз\n!разбан @юз\n!инфо @юз\n!игроки\n\n"
        "Предметы: деньги, победа (поб.валюта), щит, удвоитель, страховка, буст, ставки, удача,\n"
        "глаз и рука (вернуть проданные), сброс.\n@юз можно заменить на числовой ID.")

def auth(init):
    try:
        d = dict(parse_qsl(init, keep_blank_values=True)); h = d.pop("hash")
        chk = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
        key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(hmac.new(key, chk.encode(), hashlib.sha256).hexdigest(), h): return None
        return json.loads(d["user"])
    except Exception:
        return None

async def sync(req):
    u = auth(req.headers.get("X-Init", ""))
    if not u: return web.json_response({"err": "auth"}, status=401)
    st = (await req.json()).get("st")
    uid, un = u["id"], (u.get("username") or "").lower()
    row = db.execute("select st,ban,gr from p where id=?", (uid,)).fetchone()
    if not row:
        db.execute("insert into p(id,un) values(?,?)", (uid, un)); row = (None, 0, "[]")
    out = {"ban": row[1], "grants": json.loads(row[2])}
    if st is None: out["st"] = json.loads(row[0]) if row[0] else None
    elif not row[1]: db.execute("update p set st=? where id=?", (json.dumps(st), uid))
    db.execute("update p set un=?, gr='[]' where id=?", (un, uid)); db.commit()
    return web.json_response(out)

def find(t):
    t = t.lstrip("@").lower()
    r = db.execute("select id from p where id=?", (int(t),)).fetchone() if t.isdigit() else db.execute("select id from p where un=?", (t,)).fetchone()
    return r[0] if r else None

def give(uid, item, n):
    gr = json.loads(db.execute("select gr from p where id=?", (uid,)).fetchone()[0]); gr.append({"item": item, "n": n})
    db.execute("update p set gr=? where id=?", (json.dumps(gr), uid)); db.commit()

dp = Dispatcher()

@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("🎰 Lucky Royale", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Играть", web_app=WebAppInfo(url=URL))]]))

@dp.message(F.text.startswith("!"))
async def admin(m: Message):
    if m.from_user.id not in ADMINS: return
    a = m.text.split(); c = a[0][1:].lower()
    num = lambda i: max(1, int(a[i])) if len(a) > i and a[i].lstrip("-").isdigit() else 1
    if c in ("помощь", "help"): return await m.answer(HELP)
    if c == "игроки":
        r = db.execute("select count(*), sum(ban) from p").fetchone(); return await m.answer(f"Игроков: {r[0]}, в бане: {r[1] or 0}")
    if c in ("выдатьвсем", "giveall") and len(a) > 1 and a[1].lower() in ITEMS:
        ids = [x[0] for x in db.execute("select id from p")]
        for i in ids: give(i, ITEMS[a[1].lower()], num(2))
        return await m.answer(f"✅ Выдано всем ({len(ids)})")
    if c in ("выдать", "give", "бан", "ban", "разбан", "unban", "инфо", "info"):
        if len(a) < 2: return await m.answer("Укажи @юз")
        uid = find(a[1])
        if not uid: return await m.answer("Не найден (игрок должен хоть раз открыть игру)")
        if c in ("бан", "ban", "разбан", "unban"):
            db.execute("update p set ban=? where id=?", (1 if c in ("бан", "ban") else 0, uid)); db.commit()
            return await m.answer("🚫 Забанен" if c in ("бан", "ban") else "✅ Разбанен")
        if c in ("инфо", "info"):
            r = db.execute("select st,ban from p where id=?", (uid,)).fetchone(); s = json.loads(r[0] or "{}")
            return await m.answer(f"ID {uid}\nДеньги {s.get('bal')} · 🏆 {s.get('wc')}\nУдача ур.{s.get('luck')} · Ставки ур.{s.get('betLv')}\nГлаз продан: {s.get('eye')} · Рука продана: {s.get('hand')}\nБан: {r[1]}")
        if len(a) < 3 or a[2].lower() not in ITEMS: return await m.answer("!выдать @юз предмет [N]\n\n" + HELP)
        give(uid, ITEMS[a[2].lower()], num(3)); return await m.answer("✅ Выдано")

async def main():
    app = web.Application(); app.router.add_post("/api/sync", sync)
    app.router.add_get("/", lambda r: web.FileResponse("casino.html"))
    run = web.AppRunner(app); await run.setup(); await web.TCPSite(run, "0.0.0.0", PORT).start()
    await dp.start_polling(Bot(TOKEN))

asyncio.run(main())
