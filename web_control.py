# ═══════════════════════════════════════════════════════════════════════════
#  web_control.py — MASTER GLORY Backend (PAID 📩)
# ═══════════════════════════════════════════════════════════════════════════

import os
import re
import sys
import json
import time
import asyncio
import threading
import traceback
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import core
import match

# ═══════════════ PATHS ═══════════════
BASE_DIR      = Path(__file__).parent
ACCS_FILE     = BASE_DIR / "accs.txt"
SQUAD_FILE    = BASE_DIR / "squad_accounts.json"
CLAN_FILE     = BASE_DIR / "clan_tracker.json"
MATCH_HISTORY = BASE_DIR / "match_history.json"
SETTINGS_FILE = BASE_DIR / "settings.json"
LOG_FILE      = BASE_DIR / "udp_logs.txt"

# ═══════════════ DEFAULT SETTINGS ═══════════════
DEFAULT_SETTINGS = {
    "default_region":   "IND",
    "match_delay_mins": 2,
    "auto_loop":        False,
    "team_size":        4,
    "theme":            "titanium",
}

# ═══════════════ GLOBAL STATE ═══════════════
SYSTEM_START = time.time()

STATE = {
    "gen_running":     False,
    "clan_running":    False,
    "match_running":   False,
    "auto_match":      False,
    "match_started":   0,
    "match_completed": 0,
    "match_failed":    0,
    "teams_running":   [],
    "web_logs":        [],
    "account_stats":   {},
    "active_matches":  {},
}

_settings_cache = dict(DEFAULT_SETTINGS)
_history_cache  = []

# ═══════════════ JSON HELPERS ═══════════════
def _load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def _save_json(path, data):
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

# ═══════════════ SETTINGS ═══════════════
def load_settings():
    global _settings_cache
    data = _load_json(SETTINGS_FILE, {})
    merged = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        for k, v in data.items():
            if k in DEFAULT_SETTINGS:
                merged[k] = v
    _settings_cache = merged
    return merged

def save_settings(data):
    global _settings_cache
    clean = {}
    for k, v in DEFAULT_SETTINGS.items():
        clean[k] = data.get(k, DEFAULT_SETTINGS[k])
    _settings_cache = clean
    _save_json(SETTINGS_FILE, clean)
    return clean

# ═══════════════ MATCH HISTORY ═══════════════
def load_history():
    global _history_cache
    data = _load_json(MATCH_HISTORY, [])
    _history_cache = data if isinstance(data, list) else []
    return _history_cache

def append_history(entry):
    global _history_cache
    _history_cache.append(entry)
    if len(_history_cache) > 500:
        _history_cache = _history_cache[-500:]
    _save_json(MATCH_HISTORY, _history_cache)

# ═══════════════ LOGGER ═══════════════
class WebLogger:
    def __init__(self, original_stream):
        self.original_stream = original_stream

    def write(self, message):
        if not message or not message.strip():
            return
        try:
            self.original_stream.write(message)
            self.original_stream.flush()
        except Exception:
            pass

        if "HTTP/1.1" in message:
            return

        clean = re.sub(r'\x1b\[[0-9;]*m', '', message).strip()
        if not clean:
            return

        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {clean}"
        STATE["web_logs"].append(line)
        if len(STATE["web_logs"]) > 300:
            STATE["web_logs"] = STATE["web_logs"][-300:]

    def flush(self):
        try:
            self.original_stream.flush()
        except Exception:
            pass

    def isatty(self):
        return False

sys.stdout = WebLogger(sys.stdout)
sys.stderr = WebLogger(sys.stderr)

# ═══════════════ HELPERS ═══════════════
def _compute_uptime(uid):
    stats = STATE["account_stats"].get(uid)
    if not stats or not stats.get("started_at"):
        return 0
    return int(time.time() - stats["started_at"])

def _account_status(uid):
    stats = STATE["account_stats"].get(uid, {})
    if stats.get("is_paused"):
        return "PAUSED"
    return stats.get("status", "OFFLINE")

def _build_teams():
    raw = core.load_accounts()
    if not raw:
        return [], 0

    team_size = int(_settings_cache.get("team_size", 4) or 4)
    raw = list(reversed(raw))

    teams = []
    team_index = 1

    for i in range(0, len(raw), team_size):
        chunk = raw[i:i + team_size]
        members = []
        for acc in chunk:
            uid = str(acc.get("uid", ""))
            members.append({
                "uid":          uid,
                "name":         acc.get("name", "Unknown"),
                "region":       acc.get("region", "IND"),
                "ingame_id":    acc.get("ingame_id", 0),
                "status":       _account_status(uid),
                "uptime":       _compute_uptime(uid),
                "matches_done": STATE["account_stats"].get(uid, {}).get("matches_done", 0),
                "is_paused":    STATE["account_stats"].get(uid, {}).get("is_paused", False),
            })
        teams.append({
            "id":         f"TEAM {team_index}",
            "team_index": team_index,
            "members":    members,
            "running":    f"TEAM {team_index}" in STATE["teams_running"],
            "size":       len(members),
        })
        team_index += 1

    return teams, len(raw)

def _team_uids(team):
    return [m["uid"] for m in team.get("members", [])]

def _run_async_thread(coro_func, *args, **kwargs):
    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro_func(*args, **kwargs))
        except Exception:
            traceback.print_exc()
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for t in pending:
                    t.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.close()
    threading.Thread(target=_runner, daemon=True).start()

# ═══════════════ FASTAPI ═══════════════
app = FastAPI(title="Master Glory Control")

(BASE_DIR / "static").mkdir(exist_ok=True)
(BASE_DIR / "templates").mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@app.on_event("startup")
async def _on_startup():
    load_settings()
    load_history()
    print("[BOOT] Master Glory backend started.")
    print(f"[BOOT] Settings: {_settings_cache}")

# ═══════════════ ROUTES ═══════════════
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    teams, total_acc = _build_teams()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "teams":     teams,
            "total_acc": total_acc,
            "settings":  _settings_cache,
            "state":     STATE,
        }
    )

@app.get("/api/stats")
async def api_stats():
    teams, total_acc = _build_teams()

    online_count  = 0
    in_game_count = 0
    paused_count  = 0

    for team in teams:
        for m in team["members"]:
            st = m["status"]
            if m["is_paused"] or st == "PAUSED":
                paused_count += 1
            elif st in ("IN_MATCH", "IN_GAME"):
                in_game_count += 1
                online_count += 1
            elif st in ("ONLINE", "CONNECTING", "SEARCHING"):
                online_count += 1

    return {
        "status":          "ok",
        "uptime":          int(time.time() - SYSTEM_START),
        "total_accounts":  total_acc,
        "total_teams":     len(teams),
        "online":          online_count,
        "in_game":         in_game_count,
        "paused":          paused_count,
        "match_started":   STATE["match_started"],
        "match_completed": STATE["match_completed"],
        "match_failed":    STATE["match_failed"],
        "teams_running":   list(STATE["teams_running"]),
        "settings":        _settings_cache,
        "teams":           teams,
    }

@app.get("/api/logs")
async def api_logs(limit: int = 150):
    return {"logs": STATE["web_logs"][-limit:]}

@app.get("/api/status")
async def api_status():
    return {
        "gen_running":   STATE["gen_running"],
        "clan_running":  STATE["clan_running"],
        "match_running": STATE["match_running"],
        "auto_match":    STATE["auto_match"],
    }

@app.get("/api/history")
async def api_history(limit: int = 100):
    return {"history": _history_cache[-limit:]}

@app.get("/api/settings")
async def api_settings_get():
    return {"status": "ok", "settings": _settings_cache}

@app.post("/api/settings")
async def api_settings_post(payload: dict):
    saved = save_settings(payload)
    return {"status": "ok", "settings": saved}

@app.post("/api/gen")
async def api_gen(count: int = Form(...), name: str = Form("MasteR"), region: str = Form("IND")):
    if STATE["gen_running"]:
        raise HTTPException(400, "Generation already running")

    def _worker():
        STATE["gen_running"] = True
        try:
            cfg = core.get_cfg_for_region(region)
            for i in range(1, count + 1):
                try:
                    core.create_one_account(i, count, cfg, name)
                except Exception as e:
                    print(f"[GEN] {i}/{count} failed: {e}")
        finally:
            STATE["gen_running"] = False

    threading.Thread(target=_worker, daemon=True).start()
    return {"status": "ok", "message": f"Generating {count} accounts"}

@app.post("/api/clan_join")
async def api_clan_join(guild_id: str = Form(...), uids: str = Form(None)):
    if not guild_id.isdigit():
        raise HTTPException(400, "Guild ID must be numeric")
    if STATE["clan_running"]:
        raise HTTPException(400, "Clan join already running")

    async def _do():
        STATE["clan_running"] = True
        try:
            all_accounts = core.load_accounts()
            if uids:
                selected = set(uids.split(","))
                accounts = [a for a in all_accounts if str(a.get("uid")) in selected]
            else:
                accounts = all_accounts

            print(f"[CLAN] Joining {len(accounts)} accounts to guild {guild_id}")
            for acc in accounts:
                try:
                    ok, msg = await core.join_clan_for_account(acc, guild_id)
                    name = acc.get("name", "?")
                    print(f"[CLAN] {name} -> {'OK' if ok else msg}")
                except Exception as e:
                    print(f"[CLAN] Error: {e}")
                await asyncio.sleep(1.5)
        finally:
            STATE["clan_running"] = False

    _run_async_thread(_do)
    count = len(uids.split(',')) if uids else 'all'
    return {"status": "ok", "message": f"Joining {count} accounts"}

@app.post("/api/start_team")
async def api_start_team(
    team_id: str = Form(...),
    region: str = Form(None),
    loop_match: str = Form("false"),
    delay_mins: int = Form(2),
):
    if STATE["match_running"]:
        raise HTTPException(400, "A match is already running")

    teams, _ = _build_teams()
    target = next((t for t in teams if t["id"] == team_id), None)
    if not target:
        raise HTTPException(404, f"Team {team_id} not found")

    uids = _team_uids(target)
    if len(uids) < 2:
        raise HTTPException(400, "Team has fewer than 2 accounts")

    all_accounts = core.load_accounts()
    accounts = [a for a in all_accounts if str(a.get("uid")) in uids]
    if len(accounts) < 2:
        raise HTTPException(400, "Selected accounts not found")

    use_region = region or _settings_cache.get("default_region", "IND")
    auto_loop  = (loop_match == "true") or _settings_cache.get("auto_loop", False)
    delay_sec  = max(10, int(delay_mins or 2) * 60)

    async def _do():
        STATE["match_running"] = True
        STATE["auto_match"]    = auto_loop
        if team_id not in STATE["teams_running"]:
            STATE["teams_running"].append(team_id)

        try:
            while True:
                STATE["match_started"] += 1
                STATE["active_matches"][team_id] = time.time()

                for acc in accounts:
                    uid = str(acc.get("uid"))
                    st  = STATE["account_stats"].setdefault(uid, {})
                    st["status"]     = "IN_MATCH"
                    st["started_at"] = st.get("started_at") or time.time()
                    st["is_paused"]  = False

                entry = {
                    "team":       team_id,
                    "uids":       uids,
                    "region":     use_region,
                    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "status":     "started",
                }

                reason = "error"
                try:
                    await match.run_squad_game(accounts, region_hint=use_region)
                    reason = "ended"
                    STATE["match_completed"] += 1
                except Exception as e:
                    STATE["match_failed"] += 1
                    print(f"[MATCH] {team_id} failed: {e}")

                entry["ended_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                entry["status"]   = "completed" if reason == "ended" else "failed"
                append_history(entry)

                for acc in accounts:
                    uid = str(acc.get("uid"))
                    st  = STATE["account_stats"].setdefault(uid, {})
                    st["status"]       = "ONLINE"
                    st["matches_done"] = st.get("matches_done", 0) + 1
                    st["last_seen"]    = time.time()

                STATE["active_matches"].pop(team_id, None)

                if not STATE["auto_match"]:
                    break

                for _ in range(delay_sec):
                    if not STATE["auto_match"]:
                        break
                    await asyncio.sleep(1)
                if not STATE["auto_match"]:
                    break
        finally:
            STATE["match_running"] = False
            STATE["auto_match"]    = False
            if team_id in STATE["teams_running"]:
                STATE["teams_running"].remove(team_id)
            STATE["active_matches"].pop(team_id, None)

    _run_async_thread(_do)
    return {"status": "ok", "team": team_id, "accounts": len(accounts)}

@app.post("/api/stop_team")
async def api_stop_team(team_id: str = Form(...)):
    if team_id in STATE["teams_running"]:
        STATE["teams_running"].remove(team_id)
    STATE["active_matches"].pop(team_id, None)

    if not STATE["teams_running"]:
        STATE["auto_match"]    = False
        STATE["match_running"] = False

    print(f"[STOP] Team {team_id} stopped.")
    return {"status": "ok", "team": team_id}

@app.post("/api/stop_all")
async def api_stop_all():
    STATE["auto_match"]     = False
    STATE["match_running"]  = False
    STATE["teams_running"]  = []
    STATE["active_matches"] = {}
    print("[STOP] All stopped.")
    return {"status": "ok"}

@app.post("/api/history/clear")
async def api_history_clear():
    global _history_cache
    _history_cache = []
    _save_json(MATCH_HISTORY, [])
    print("[HISTORY] Cleared.")
    return {"status": "ok"}

@app.post("/api/account/pause")
async def api_account_pause(payload: dict):
    uid = str(payload.get("uid", "")).strip()
    if not uid:
        raise HTTPException(400, "Missing uid")
    st = STATE["account_stats"].setdefault(uid, {})
    st["is_paused"] = not st.get("is_paused", False)
    st["status"]    = "PAUSED" if st["is_paused"] else "ONLINE"
    return {"status": "ok", "is_paused": st["is_paused"]}

@app.post("/api/account/delete")
async def api_account_delete(payload: dict):
    uid = str(payload.get("uid", "")).strip()
    if not uid:
        raise HTTPException(400, "Missing uid")

    accs = core.load_accounts()
    new_accs = [a for a in accs if str(a.get("uid")) != uid]

    try:
        with open(ACCS_FILE, "w", encoding="utf-8") as f:
            for a in new_accs:
                line = "|".join([
                    str(a.get("uid", "")), str(a.get("pass", "")),
                    str(a.get("name", "")), str(a.get("region", "IND")),
                    str(a.get("open_id", "")), str(a.get("access_token", "")),
                    str(a.get("jwt", "")), str(a.get("ingame_id", 0)),
                    str(a.get("game_url", "")),
                ])
                f.write(line + "\n")
    except Exception as e:
        raise HTTPException(500, f"Write failed: {e}")

    STATE["account_stats"].pop(uid, None)
    return {"status": "ok"}

@app.post("/api/account/sync")
async def api_account_sync(payload: dict):
    uid = str(payload.get("uid", "")).strip()
    if not uid:
        raise HTTPException(400, "Missing uid")
    st = STATE["account_stats"].setdefault(uid, {})
    st["last_seen"] = time.time()
    return {"status": "ok"}

@app.post("/api/account/add")
async def api_account_add(payload: dict):
    uid      = str(payload.get("uid", "")).strip()
    password = str(payload.get("password", "")).strip()
    if not uid or not password:
        raise HTTPException(400, "uid and password required")

    accs = core.load_accounts()
    if any(str(a.get("uid")) == uid for a in accs):
        raise HTTPException(400, "Account already exists")

    try:
        with open(ACCS_FILE, "a", encoding="utf-8") as f:
            line = "|".join([uid, password, "manual", "IND", "", "", "", "0", ""])
            f.write(line + "\n")
    except Exception as e:
        raise HTTPException(500, f"Write failed: {e}")

    return {"status": "ok"}

@app.post("/api/logs/clear")
async def api_logs_clear():
    STATE["web_logs"] = []
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    print(f"[BOOT] Starting uvicorn on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")