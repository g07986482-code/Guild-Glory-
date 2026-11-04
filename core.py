# ═══════════════════════════════════════════════════════════════════════════
#  core.py — Shared core (ALL REGIONS, gen.py proven method)
#  Owner: Anurag Singh | Telegram: @Developer_NovaG
# ═══════════════════════════════════════════════════════════════════════════

import os
import sys
import re
import ssl
import json
import time
import uuid
import hmac
import string
import base64
import random
import hashlib
import asyncio
import socket
import struct
import threading
import traceback
import math
import warnings
from datetime import datetime

import aiohttp
import requests
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# gen.py wali pb2 files — proven method
import MajorloginReqBuild_pb2
import PorTs_pb2
from MajorloginResp_pb2 import MajorLoginRes as MajorLoginResponse

try:
    from protobuf_decoder.protobuf_decoder import Parser
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False
    Parser = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

# ═══════════════════════════════════════════════════════════════════════════
#  REGION CONFIG
# ═══════════════════════════════════════════════════════════════════════════
REGION_LIST = ["IND", "ID", "TH", "ME", "EUROPE", "VN", "BD", "PK",
               "TW", "RU", "NA", "SAC", "BR", "SG", "US"]

REGION_LANG = {
    "ME": "ar", "IND": "hi", "ID": "id", "VN": "vi", "TH": "th",
    "BD": "bn", "PK": "ur", "TW": "zh", "EUROPE": "fr", "RU": "ru",
    "NA": "na", "SAC": "es", "BR": "pt", "SG": "ms", "US": "us",
}

REGION_GROUP = {
    "IND": "IND",
    "BR": "AMERICA", "US": "AMERICA", "NA": "AMERICA", "SAC": "AMERICA",
    "ID": "OTHERS", "TH": "OTHERS", "ME": "OTHERS", "EUROPE": "OTHERS",
    "VN": "OTHERS", "BD": "OTHERS", "PK": "OTHERS", "TW": "OTHERS",
    "RU": "OTHERS", "SG": "OTHERS",
}

REGION_URLS = {
    "IND": {"server": "https://loginbp.ppmainecoonghj.com/",
            "client": "https://client.ind.freefiremobile.com/"},
    "AMERICA": {"server": "https://loginbp.ppmainecoonghj.com/",
                "client": "https://client.us.freefiremobile.com/"},
    "OTHERS": {"server": "https://loginbp.ppmainecoonghj.com/",
               "client": "https://clientbp.ggpolarbear.com/"},
}

def region_byte(region):
    reg = str(region or "IND").upper()
    if reg == "IND":
        return 0x14
    if reg == "BD":
        return 0x19
    return 0x15

def region_prefix(region, kind="online"):
    reg = str(region or "IND").upper()
    if reg == "BD":
        return "7119" if kind == "online" else "9219"
    if reg == "IND":
        return "7114" if kind == "online" else "9214"
    return "7115" if kind == "online" else "9215"

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════
APP_ID = 100067
CLIENT_TYPE = 2
SOURCE = 2
SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"

GARENA_BASE = "https://100067.connect.garena.com/api/v2/oauth"
REGISTER_URL = f"{GARENA_BASE}/guest:register"
GRANT_URL = f"{GARENA_BASE}/guest/token:grant"
DATADOME_URL = "https://datadome.garena.com/js/"
VER_URL_BASE = "https://version.ggwhitehawk.com/live/ver.php"
PLAYSTORE_URL = "https://play.google.com/store/apps/details?id=com.dts.freefireth&hl=en&gl=US"

MIN_REGISTER_INTERVAL = 1.0
REGISTER_BACKOFF_START = 10.0
REGISTER_BACKOFF_MAX = 60.0
REGISTER_MAX_RETRIES = 6
DATADOME_MAX_RETRIES = 4
VER_MAX_ATTEMPTS = 3

USER_AGENT_MSDK = "GarenaMSDK/4.0.44(V2538 ;Android 16;en;US;app 1.132.1 2019121227;)"
USER_AGENT_UNITY = "UnityPlayer/2018.4.12f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)"
USER_AGENT_WEB = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

_KEYSTREAM = bytes([
    0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37, 0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37,
    0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30, 0x31, 0x37, 0x30, 0x30, 0x30, 0x30, 0x30, 0x32, 0x30,
])

SESSION_HASH = "1ac4b80ecf0478a44203bf8fac6120f5"

ACCOUNTS_FILE = "accs.txt"
CLAN_TRACKER_FILE = "clan_tracker.json"
UDP_LOG_FILE = "udp_logs.txt"
SQUAD_ACCOUNTS_FILE = "squad_accounts.json"

REGION = "IND"
LANG_CODE = "hi"

SETTLE_AFTER_ALL_JOIN = 1.5
SQUAD_PLAYERS = 4
SQUAD_TIMEOUT = 600

# Movement constants (Used by match.py)
MOVE_HZ = 15.0
MOVE_INTERVAL = 1.0 / MOVE_HZ
DASH_VEL = 501
STEP_PER_TICK = DASH_VEL / (MOVE_HZ * 0.1)
STICK_DIST = 150.0
CHASE_Y_LERP = 0.5
POSE_STANDING = 0
POSE_DASHING = 2
CMD_PLAYER_STATE_UPLOAD = 2001
CHAT_FOLLOW_TRIGGERS = (1, 2)

JHUND_MAX_AGE = 10.0
JHUND_DASH_DIST = 6000.0
JHUND_SLOT_MIN = 120.0
JHUND_SLOT_MAX = 260.0
LEADER_DEADZONE = 220.0

SEND_HZ = 10.0
MOVE_INTERVAL_BD = 1.0 / SEND_HZ
WALK_SPEED = 5150.0
STEP_PER_TICK_BD = WALK_SPEED / SEND_HZ
ZONE_RADIUS_SCALE = 1000.0

CMD_PLAYER_JOIN = 101
CMD_MATCH_END = 103
CMD_DEAD = 107
CMD_SAFE_ZONE = 117
CMD_SERVER_TIME = 2000
CMD_MY_STATE = 2001
CMD_OTHER_STATES = 2012
CMD_QUICK_CHAT = 551
CMD_GRI_SYNC = 1901

PHASE_PREPARE = 1
PHASE_FIGHT = 3
QUICK_CHAT_FOLLOW = 1
QUICK_CHAT_HELP = 2

_PLAY_VERSION = "1.132.13"
_OB_VERSION = "OB55"

HARDCODED_CONFIG = {
    "latest_release_version": "OB55",
    "remote_version": "1.132.13",
    "cdn_url": "https://dl-bs.ggpolarbear.com/live/ABHotUpdates/",
    "abhotupdate_cdn_url": "https://core-bs.ggpolarbear.com/live/ABHotUpdates/",
    "client_ip": "103.200.36.133",
    "vercfg_sign": "1.f46ddde8bb35d74e",
    "region": REGION,
    "lang": LANG_CODE,
    "country_code": REGION,
    "server_url": "https://loginbp.ppmainecoonghj.com/",
    "client_url": "https://client.ind.freefiremobile.com/",
}

_print_lock = threading.Lock()
_file_lock = threading.Lock()
_gate_lock = threading.Lock()
_dd_lock = threading.Lock()
_count_lock = threading.Lock()
_log_lock = threading.Lock()

_last_register_time = 0.0
_success_count = 0
_failure_count = 0
_dd_session_cookie = None
_dd_expires_at = 0.0

# ═══════════════════════════════════════════════════════════════════════════
#  BASIC HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def _log(line):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with _log_lock:
        print(f"[{ts}] {line}", flush=True)
        try:
            with open(UDP_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {line}\n")
        except Exception:
            pass

def _tag(i, n):
    return f"{i:>2}/{n}"

def gen_nickname(prefix="vai"):
    chars = string.ascii_lowercase + string.digits
    return f"{prefix}_{''.join(random.choices(chars, k=4))}"

def enc_aes(data):
    return AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(data, 16))

def dec_aes(data):
    try:
        return unpad(AES.new(KEY, AES.MODE_CBC, IV).decrypt(data), 16)
    except ValueError:
        return AES.new(KEY, AES.MODE_CBC, IV).decrypt(data)

def sign_body(body):
    return hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()

def encode_open_id(open_id):
    return bytes(ord(open_id[i]) ^ _KEYSTREAM[i % len(_KEYSTREAM)] for i in range(len(open_id)))

def decode_jwt_payload(token):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        p2 = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(p2))
    except Exception:
        return {}

def _to_bytes(v):
    if isinstance(v, bytes):
        return v
    if isinstance(v, str):
        try:
            return bytes.fromhex(v)
        except ValueError:
            return v.encode()
    if v is None:
        raise ValueError("cannot convert None")
    return bytes(v)

def _normalize_uid(uid):
    s = str(uid).strip()
    return int(s) if s.isdigit() else s

# ═══════════════════════════════════════════════════════════════════════════
#  PROTOBUF HELPERS
# ═══════════════════════════════════════════════════════════════════════════
def enc_varint(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)

def read_varint(data, off):
    v, s = 0, 0
    while True:
        b = data[off]
        off += 1
        v |= (b & 0x7F) << s
        if not (b & 0x80):
            return v, off
        s += 7

def ptag(f, wt):
    return enc_varint((f << 3) | wt)

def f_vint(f, n):
    return ptag(f, 0) + enc_varint(n)

def f_bytes(f, b):
    return ptag(f, 2) + enc_varint(len(b)) + b

def f_str(f, s):
    b = s.encode("utf-8")
    return ptag(f, 2) + enc_varint(len(b)) + b

def parse_proto(data):
    fields = {}
    i = 0
    while i < len(data):
        try:
            key, i = read_varint(data, i)
        except Exception:
            break
        fn, wt = key >> 3, key & 7
        try:
            if wt == 0:
                v, i = read_varint(data, i)
                fields.setdefault(fn, []).append(("varint", v))
            elif wt == 1:
                v = int.from_bytes(data[i:i+8], "little")
                i += 8
                fields.setdefault(fn, []).append(("u64", v))
            elif wt == 2:
                ln, i = read_varint(data, i)
                raw = data[i:i+ln]
                i += ln
                s_ok = False
                try:
                    s = raw.decode("utf-8")
                    if s.isprintable():
                        fields.setdefault(fn, []).append(("string", s))
                        s_ok = True
                except UnicodeDecodeError:
                    pass
                if not s_ok:
                    fields.setdefault(fn, []).append(("bytes", raw.hex()))
            elif wt == 5:
                v = int.from_bytes(data[i:i+4], "little")
                i += 4
                fields.setdefault(fn, []).append(("u32", v))
            else:
                break
        except Exception:
            break
    return fields

def first_value(fields, field_num, want_kind=None):
    for kind, v in fields.get(field_num, []):
        if want_kind is None or kind == want_kind:
            return v
    return None

# ═══════════════════════════════════════════════════════════════════════════
#  ACCOUNT STORAGE
# ═══════════════════════════════════════════════════════════════════════════
def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    out = []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            p = line.split("|")
            if len(p) < 9:
                continue
            out.append({
                "uid": p[0], "pass": p[1], "name": p[2], "region": p[3],
                "open_id": p[4], "access_token": p[5], "jwt": p[6],
                "ingame_id": int(p[7]) if p[7].isdigit() else 0,
                "game_url": p[8],
            })
    return out

def append_account(acc):
    line = "|".join([
        acc["uid"], acc["pass"], acc["name"], acc["region"],
        acc["open_id"], acc["access_token"], acc["jwt"],
        str(acc["ingame_id"]), acc["game_url"],
    ])
    with _file_lock:
        with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

def load_squad_accounts(path=SQUAD_ACCOUNTS_FILE):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        out = []
        for rec in data:
            if not isinstance(rec, dict):
                continue
            uid = rec.get("uid")
            pw = rec.get("pass") or rec.get("password")
            if not uid or not pw:
                continue
            out.append(rec)
        return out
    except Exception:
        return []

def _load_json_dict(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def load_clan_tracker():
    return _load_json_dict(CLAN_TRACKER_FILE)

def save_clan_tracker(tracker):
    with _file_lock:
        with open(CLAN_TRACKER_FILE, "w", encoding="utf-8") as f:
            json.dump(tracker, f, indent=2, ensure_ascii=False)

def track_account_clan(uid, clan_id, account_name="", ingame_id=""):
    tracker = load_clan_tracker()
    tracker.setdefault("clans", {})
    tracker.setdefault("accounts", {})
    ck = str(clan_id)
    tracker["clans"].setdefault(ck, {
        "accounts": [],
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    if uid not in tracker["clans"][ck]["accounts"]:
        tracker["clans"][ck]["accounts"].append(uid)
    tracker["accounts"][uid] = {
        "clan_id": ck, "name": account_name, "ingame_id": ingame_id,
        "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_clan_tracker(tracker)
    return True

# ═══════════════════════════════════════════════════════════════════════════
#  VERSION / DATADOME
# ═══════════════════════════════════════════════════════════════════════════
def get_play_store_version():
    headers = {"User-Agent": USER_AGENT_WEB, "Accept-Language": "en-US,en;q=0.9"}
    html = requests.get(PLAYSTORE_URL, headers=headers, timeout=15).text
    versions = re.findall(r"\b(1\.\d{1,3}\.\d{1,3})\b", html)
    if not versions:
        raise RuntimeError("no version on playstore page")
    real = [v for v in versions if v != "1.000.000"]
    return (real or versions)[-1]

def fetch_ver_config(initial_version, region=None, lang=None):
    region = region or REGION
    lang = lang or REGION_LANG.get(region, "en")
    version = initial_version
    last = None
    for attempt in range(1, VER_MAX_ATTEMPTS + 1):
        url = (
            f"{VER_URL_BASE}?version={version}"
            f"&lang={lang}&device=android&channel=3rd_party&appstore=thirdparty"
            f"&region={region}&whitelist_version=1.7.0&whitelist_sp_version=1.0.0"
            f"&device_name=vivo%20V2538"
            f"&device_CPU=ARM64%20FP%20ASIMD%20AES"
            f"&device_GPU=Adreno%20%28TM%29%20722"
            f"&device_mem=7282"
        )
        try:
            cfg = requests.get(url, timeout=15).json()
        except Exception as e:
            last = e
            time.sleep(1.0 * attempt)
            continue
        if cfg.get("code") == 0:
            grp = REGION_GROUP.get(region, "OTHERS")
            cfg["region"] = region
            cfg["lang"] = lang
            cfg["country_code"] = region
            cfg["server_url"] = REGION_URLS[grp]["server"]
            cfg["client_url"] = REGION_URLS[grp]["client"]
            return cfg
        if cfg.get("remote_version"):
            version = cfg["remote_version"]
        last = cfg
        time.sleep(1.0 * attempt)
    raise RuntimeError(f"ver.php failed: {last}")

def get_datadome(tag, force=False):
    global _dd_session_cookie, _dd_expires_at
    with _dd_lock:
        now = time.time()
        if not force and _dd_session_cookie and _dd_expires_at > now:
            return _dd_session_cookie
        headers = {
            "User-Agent": USER_AGENT_WEB,
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://sso.garena.com/universal/register?locale=en-SG",
            "Origin": "https://sso.garena.com",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        payload = {
            "jsType": "le",
            "eventCounters": '{"mousemove":1,"click":1,"keydown":11}',
            "ddk": "AE3F04AD3F0D3A462481A337485081",
            "Referer": "https://sso.garena.com/universal/register?locale=en-SG",
            "request": "/universal/register?locale=en-SG",
            "responsePage": "origin",
            "ddv": "5.7.0",
        }
        last = None
        for attempt in range(1, DATADOME_MAX_RETRIES + 1):
            try:
                r = requests.post(DATADOME_URL, data=payload, headers=headers, timeout=15)
                r.raise_for_status()
                result = r.json()
            except Exception as e:
                last = e
                time.sleep(1.5 * attempt)
                continue
            if result.get("status") == 200 and result.get("cookie"):
                for part in result["cookie"].split(";"):
                    if "datadome=" in part:
                        dd = part.replace("datadome=", "").strip()
                        if dd:
                            _dd_session_cookie = dd
                            _dd_expires_at = now + 300.0
                            return dd
            last = result
            time.sleep(1.5 * attempt)
        raise RuntimeError(f"DataDome failed: {last}")

def _wait_register_slot(tag):
    global _last_register_time
    while True:
        with _gate_lock:
            now = time.time()
            wait = MIN_REGISTER_INTERVAL - (now - _last_register_time)
            if wait <= 0:
                _last_register_time = now
                return
        time.sleep(min(wait, 0.5))

# ═══════════════════════════════════════════════════════════════════════════
#  GUEST REGISTER / TOKEN  (gen.py exact)
# ═══════════════════════════════════════════════════════════════════════════
def guest_register(tag, device_id, max_retries=REGISTER_MAX_RETRIES):
    pwd = ''.join(random.choices(string.ascii_uppercase + string.digits, k=64))
    payload = {"app_id": APP_ID, "client_type": CLIENT_TYPE,
               "password": pwd, "source": SOURCE}
    body = json.dumps(payload, separators=(",", ":"))
    last_err = None
    for attempt in range(1, max_retries + 1):
        _wait_register_slot(tag)
        datadome = get_datadome(tag, force=(attempt > 1 and attempt % 3 == 0))
        headers = {
            "User-Agent": USER_AGENT_MSDK,
            "Authorization": f"Signature {sign_body(body)}",
            "Cookie": f"datadome={datadome}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }
        try:
            r = requests.post(REGISTER_URL, data=body, headers=headers, timeout=25)
            data = r.json()
        except Exception as e:
            last_err = e
            time.sleep(2.0 * attempt)
            continue
        code = data.get("code")
        if code == 0:
            return str(data["data"]["uid"]), pwd
        if code in (1006, 1005):
            wait = min(REGISTER_BACKOFF_START * (2 ** (attempt - 1)), REGISTER_BACKOFF_MAX)
            last_err = data
            time.sleep(wait)
            continue
        raise RuntimeError(f"guest:register failed: {data}")
    raise RuntimeError(f"guest:register gave up: {last_err}")

def guest_token(tag, uid, device_id, password):
    uid_val = _normalize_uid(uid)
    payload = {
        "client_id": APP_ID, "client_secret": SECRET, "client_type": CLIENT_TYPE,
        "device_id": device_id, "password": password,
        "response_type": "token", "uid": uid_val,
    }
    body = json.dumps(payload, separators=(",", ":"))
    datadome = get_datadome(tag)
    last_err = None
    for attempt in range(1, 5):
        headers = {
            "User-Agent": USER_AGENT_MSDK,
            "Authorization": f"Signature {sign_body(body)}",
            "Cookie": f"datadome={datadome}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }
        try:
            r = requests.post(GRANT_URL, data=body, headers=headers, timeout=20)
            data = r.json()
        except Exception as e:
            last_err = e
            time.sleep(2.0 * attempt)
            continue
        code = data.get("code")
        if code == 0:
            return data["data"]
        if code in (1006, 1005):
            wait = min(REGISTER_BACKOFF_START * (2 ** (attempt - 1)), REGISTER_BACKOFF_MAX)
            last_err = data
            time.sleep(wait)
            continue
        last_err = data
        if attempt < 4:
            datadome = get_datadome(tag, force=True)
            time.sleep(1.5 * attempt)
            continue
    raise RuntimeError(f"guest/token:grant failed: {last_err}")

# ═══════════════════════════════════════════════════════════════════════════
#  MAJOR REGISTER  (gen.py exact)
# ═══════════════════════════════════════════════════════════════════════════
def major_register(tag, open_id, access_token, name, password, cfg):
    url = cfg["server_url"].rstrip("/") + "/MajorRegister"
    lang = cfg.get("lang", "en")
    body = f_str(1, name)
    body += f_str(2, access_token)
    body += f_str(3, open_id)
    body += f_vint(5, 102000007)
    body += f_vint(6, 4)
    body += f_vint(7, 1)
    body += f_vint(13, 1)
    body += f_bytes(14, encode_open_id(open_id))
    body += f_str(15, lang)
    body += f_vint(16, 2)
    body += f_str(22, password)
    headers = {
        "User-Agent": USER_AGENT_UNITY,
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "X-GA-SV": str(int(time.time())),
        "ReleaseVersion": cfg["latest_release_version"],
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
    }
    r = requests.post(url, data=enc_aes(body), headers=headers, timeout=20)
    try:
        fields = parse_proto(dec_aes(r.content))
    except Exception:
        fields = parse_proto(r.content)
    result = first_value(fields, 1, "varint")
    return result == 1

# ═══════════════════════════════════════════════════════════════════════════
#  MAJOR LOGIN + GET LOGIN DATA  (gen.py exact — pb2 method)
# ═══════════════════════════════════════════════════════════════════════════
def _build_major_login_pb2(open_id, access_token, platform, client_version,
                           region="IND", country="IND", lang="en"):
    p = MajorloginReqBuild_pb2.MajorLogin()
    p.open_id = open_id
    p.access_token = access_token
    p.client_version = client_version
    p.event_time = str(int(time.time()))
    p.game_name = "free fire"
    p.platform_id = 1
    p.system_software = "Android OS 16 / API-36 (BP4A.251205.006/M066BXXS8CZI1)"
    p.system_hardware = "Handheld"
    p.telecom_operator = "WIFI"
    p.network_type = "WIFI"
    p.screen_width = 1600
    p.screen_height = 720
    p.screen_dpi = "300"
    p.processor_details = "ARM64 FP ASIMD AES | 2400 | 8"
    p.memory = 3507
    p.gpu_renderer = "Mali-G57 MC2"
    p.gpu_version = "OpenGL ES 3.2 v1.r38p1"
    p.unique_device_id = "Google|6acc6a56-b955-42d6-9920-7c3faa8992e3"
    p.client_ip = "122.174.21.30"
    p.language = lang
    p.open_id_type = "4"
    p.device_type = "Handheld"
    p.device_model = "samsung SM-M066B"
    p.country_code = country
    p.platform_sdk_id = 1
    p.network_operator_a = "WIFI"
    p.network_type_a = "WIFI"
    p.client_using_version = SESSION_HASH
    p.external_storage_total = 47195
    p.external_storage_available = 19418
    p.internal_storage_total = 5135
    p.internal_storage_available = 5135
    p.game_disk_storage_available = 19546
    p.game_disk_storage_total = 47195
    p.external_sdcard_avail_storage = 19546
    p.external_sdcard_total_storage = 47195
    p.field_70 = 4
    p.login_by = 3
    p.library_path = "/data/app/~~bsxEK2UVui2u9YoL_QKi_w==/com.garena.game.ffi-p7Uh_JDc-8hCjRgLvsaRqg==/lib/arm64"
    p.reg_avatar = 3
    p.library_token = ("dd9d4c174e0472d34b7fd34bd5924bc9|"
                       "/data/app/~~bsxEK2UVui2u9YoL_QKi_w==/com.garena.game.ffi-p7Uh_JDc-8hCjRgLvsaRqg==/base.apk")
    p.channel_type = 3
    p.cpu_type = 2
    p.cpu_architecture = "64"
    p.client_version_code = "2019121269"
    p.field_85 = 3
    p.graphics_api = "OpenGLES2"
    p.supported_astc_bitset = 8191
    p.login_open_id_type = 4
    p.loading_time = 13070
    p.release_channel = "android"
    p.extra_info = ("KqsHT3kf8XDT3vqFEnlSSQFMl5SRiWL2SxIxcx47LozWRI7AqvwWJ9eJ/"
                    "fXX0amawG9xA6DLOyWSJCij9Fp7M5o3bzp7/MjO1jDqX8PwDD8qq5vO")
    p.android_engine_init_flag = 111107
    p.field_96 = json.dumps({"cur_rate": [90, 60], "support_etc2": False},
                            separators=(",", ":"))
    p.if_push = 1
    p.is_vpn = 1
    p.origin_platform_type = "4"
    p.primary_platform_type = "4"
    p.field_102 = b""
    p.field_104 = 80395
    p.field_105 = 1
    p.field_106 = ("https://dl-tata.freefireind.in/live/ABHotUpdates/"
                   "|https://core-tata.freefireind.in/live/ABHotUpdates/"
                   "|dff941d41e6e3a9e76f05ed71fdc8d87")
    p.field_107 = "1.6168622e0868ddbd"
    return enc_aes(p.SerializeToString())

def major_login(tag, open_id, access_token, cfg, platform, region=None):
    url = cfg["server_url"].rstrip("/") + "/MajorLogin"
    plain = _build_major_login_pb2(
        open_id, access_token, platform,
        cfg["remote_version"],
        cfg.get("region", "IND"),
        cfg.get("country_code", "IND"),
        cfg.get("lang", "en"),
    )
    headers = {
        "User-Agent": USER_AGENT_UNITY,
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Authorization": "Bearer",
        "X-GA": "v1 1",
        "X-GA-SV": str(int(time.time())),
        "ReleaseVersion": cfg["latest_release_version"],
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
    }
    r = requests.post(url, data=plain, headers=headers, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"MajorLogin HTTP {r.status_code}: {r.text[:200]}")
    body = r.content

    def _try(blob):
        if len(blob) < 10:
            return None
        try:
            m = MajorLoginResponse()
            m.ParseFromString(blob)
            if getattr(m, "token", "") and getattr(m, "account_id", 0):
                return m
        except Exception:
            return None

    # YE LINE MISSING THI
    cand = _try(body)

    if not cand and len(body) > 64:
        cand = _try(body[64:])
    if not cand:
        for off in range(1, min(128, len(body))):
            cand = _try(body[off:])
            if cand:
                break
    if not cand:
        raise RuntimeError(f"MajorLogin parse failed, raw: {body[:100].hex()}")
        
    return {
        "account_id": cand.account_id,
        "jwt": cand.token,
        "game_url": getattr(cand, "server_url", "") or cfg["server_url"],
        "region": getattr(cand, "lock_region", "") or cfg.get("region", "IND"),
        "aes_key": getattr(cand, "ak", b""),
        "aes_iv": getattr(cand, "aiv", b""),
        "server_time": getattr(cand, "kts", 0),
    }
def get_login_data(tag, open_id, access_token, cfg, platform, jwt):
    url = cfg["client_url"].rstrip("/") + "/GetLoginData"
    plain = _build_major_login_pb2(
        open_id, access_token, platform,
        cfg["remote_version"],
        cfg.get("region", "IND"),
        cfg.get("country_code", "IND"),
        cfg.get("lang", "en"),
    )
    headers = {
        "User-Agent": USER_AGENT_UNITY,
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "Authorization": f"Bearer {jwt}",
        "X-GA": "v1 1",
        "X-GA-SV": str(int(time.time())),
        "ReleaseVersion": cfg["latest_release_version"],
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
    }
    r = requests.post(url, data=plain, headers=headers, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"GetLoginData HTTP {r.status_code}: {r.text[:200]}")
    body = r.content

    def _try(blob):
        try:
            m = PorTs_pb2.GetLoginData()
            m.ParseFromString(blob)
            if getattr(m, "AccountUID", 0) or getattr(m, "Online_IP_Port", ""):
                return m
        except Exception:
            return None

    cand = _try(body)
    if not cand and len(body) > 64:
        cand = _try(body[64:])
    if not cand:
        for off in range(1, min(128, len(body))):
            cand = _try(body[off:])
            if cand:
                break
    if not cand:
        raise RuntimeError(f"GetLoginData parse failed, raw: {body[:100].hex()}")
    return {
        "account_id": getattr(cand, "AccountUID", 0),
        "region": getattr(cand, "Region", "") or cfg.get("region", "IND"),
        "nickname": getattr(cand, "Nickname", ""),
        "game_server": getattr(cand, "Online_IP_Port", ""),
        "chat_server": getattr(cand, "Chat_IP_Port", ""),
        "event_url": getattr(cand, "Event_URL", ""),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  REGION CFG BUILDER
# ═══════════════════════════════════════════════════════════════════════════
def build_region_cfg(region):
    region = region.upper()
    grp = REGION_GROUP.get(region, "OTHERS")
    cfg = dict(HARDCODED_CONFIG)
    cfg["region"] = region
    cfg["lang"] = REGION_LANG.get(region, "en")
    cfg["country_code"] = region
    cfg["server_url"] = REGION_URLS[grp]["server"]
    cfg["client_url"] = REGION_URLS[grp]["client"]
    return cfg

def get_cfg_for_region(region):
    """Build config for region and refresh from ver.php."""
    cfg = build_region_cfg(region)
    lang = REGION_LANG.get(region, "en")
    try:
        pv = get_play_store_version()
        fresh = fetch_ver_config(pv, region=region, lang=lang)
        for k, v in fresh.items():
            if v:
                cfg[k] = v
    except Exception as e:
        print(f"      {region}: config refresh skipped ({e})")
    return cfg


# ═══════════════════════════════════════════════════════════════════════════
#  ACCOUNT CREATION
# ═══════════════════════════════════════════════════════════════════════════
def create_one_account(index, total, cfg, custom_name=None):
    tag = _tag(index, total)
    time.sleep(random.uniform(0.05, 0.5))
    try:
        print(f"  [{tag}] register...", end="", flush=True)
        device_id = "02-" + str(uuid.uuid4())
        uid, password = guest_register(tag, device_id)
        print(f" uid={uid}", end="", flush=True)

        print(f"  token...", end="", flush=True)
        tokens = guest_token(tag, uid, device_id, password)
        open_id = tokens["open_id"]
        access_token = tokens["access_token"]
        platform = int(tokens.get("platform",
                                  tokens.get("main_active_platform", 4)) or 4)
        print(f" ok", end="", flush=True)

        print(f"  nick...", end="", flush=True)
        nickname = gen_nickname(custom_name if custom_name else "vai")
        print(f" {nickname}", end="", flush=True)

        print(f"  majreg...", end="", flush=True)
        ok = major_register(tag, open_id, access_token, nickname, password, cfg)
        print(f" {'ok' if ok else 'skip'}", end="", flush=True)

        print(f"  login...", end="", flush=True)
        login = major_login(tag, open_id, access_token, cfg, platform,
                            region=cfg["country_code"])
        payload = decode_jwt_payload(login["jwt"]) if login.get("jwt") else {}
        lock_reg = (payload.get("lock_region") or cfg["country_code"]).upper()

        cfg_use = cfg
        if lock_reg != cfg.get("country_code", cfg["region"]):
            cfg_use = build_region_cfg(lock_reg)
            login = major_login(tag, open_id, access_token, cfg_use,
                                platform, region=lock_reg)

        print(f"  data...", end="", flush=True)
        ld = get_login_data(tag, open_id, access_token, cfg_use,
                            platform, login["jwt"])
        print(f" done", flush=True)

        account = {
            "uid": uid,
            "pass": password,
            "name": nickname,
            "ingame_id": login.get("account_id"),
            "region": lock_reg,
            "open_id": open_id,
            "access_token": access_token,
            "refresh_token": tokens.get("refresh_token"),
            "jwt": login.get("jwt"),
            "game_server": ld.get("game_server"),
            "chat_server": ld.get("chat_server"),
            "game_url": login.get("game_url") or cfg_use["server_url"],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        append_account(account)
        global _success_count
        with _count_lock:
            _success_count += 1
        return account
    except Exception as e:
        global _failure_count
        with _count_lock:
            _failure_count += 1
        print(f"  X [{tag}] FAILED: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  INTERACTIVE — GEN ACCOUNTS
# ═══════════════════════════════════════════════════════════════════════════
def ask_region_menu(default="IND"):
    print(f"\n  Choose Region:")
    row = []
    for i, r in enumerate(REGION_LIST, 1):
        row.append(f"{i:>2}. {r}")
        if i % 3 == 0:
            print(f"      " + "      ".join(row))
            row = []
    if row:
        print(f"      " + "      ".join(row))
    while True:
        try:
            raw = input("  > ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if not raw:
            return default
        if raw in REGION_LIST:
            return raw
        if raw.isdigit() and 1 <= int(raw) <= len(REGION_LIST):
            return REGION_LIST[int(raw) - 1]
        print(f"  ! invalid, try again")


def generate_accounts_interactive():
    print(f"\n  Gen Count => ", end="")
    try:
        count = int(input().strip())
    except (ValueError, EOFError, KeyboardInterrupt):
        return []
    if count <= 0:
        return []

    print(f"  Name => ", end="")
    try:
        name_prefix = input().strip()
    except (EOFError, KeyboardInterrupt):
        return []
    if not name_prefix:
        name_prefix = "vai"

    global REGION, LANG_CODE
    REGION = ask_region_menu(default=REGION)
    LANG_CODE = REGION_LANG.get(REGION, "en")
    print(f"\n  Region => {REGION}\n")

    cfg = get_cfg_for_region(REGION)
    print(f"  [*] version={cfg.get('remote_version', '?')} "
          f"server={cfg.get('server_url', '?')}\n")

    accounts = []
    for i in range(1, count + 1):
        try:
            acc = create_one_account(i, count, cfg, name_prefix)
            if acc:
                accounts.append(acc)
                print(f"  Gen => {acc['name']} (region={acc['region']})")
        except Exception as e:
            print(f"  X [{i}/{count}] failed: {e}")
        time.sleep(0.5)

    return accounts


# ═══════════════════════════════════════════════════════════════════════════
#  GUEST TOKEN (async, used by clan + match) - EXACT SAME AS SYNC VERSION
# ═══════════════════════════════════════════════════════════════════════════
async def get_guest_token(uid, password, max_retries=6):
    uid_val = _normalize_uid(uid)
    payload = {
        "client_id": APP_ID, "client_secret": SECRET, "client_type": CLIENT_TYPE,
        "device_id": "02-" + str(uuid.uuid4()),
        "password": password,
        "response_type": "token", "uid": uid_val,
    }
    body = json.dumps(payload, separators=(",", ":"))
    
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            datadome = await asyncio.to_thread(get_datadome, "[clan]", (attempt > 1))
        except Exception as e:
            last_err = f"DataDome failed: {e}"
            await asyncio.sleep(min(2.0 * attempt, 10.0))
            continue
        
        headers = {
            "User-Agent": USER_AGENT_MSDK,
            "Authorization": f"Signature {sign_body(body)}",
            "Cookie": f"datadome={datadome}",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(GRANT_URL, data=body, headers=headers, timeout=20) as r:
                    if r.status != 200:
                        last_err = f"HTTP {r.status}: {(await r.text())[:200]}"
                        await asyncio.sleep(min(2.0 * attempt, 10.0))
                        continue
                    data = await r.json()
                    code = data.get("code")
                    if code == 0:
                        d = data["data"]
                        return d["open_id"], d["access_token"], int(d.get("platform", 4) or 4)
                    if code in (1006, 1005):
                        wait = min(REGISTER_BACKOFF_START * (2 ** (attempt - 1)), REGISTER_BACKOFF_MAX)
                        last_err = data
                        await asyncio.sleep(wait)
                        continue
                    last_err = data
        except Exception as e:
            last_err = str(e)
        await asyncio.sleep(min(2.0 * attempt, 10.0))
    raise RuntimeError(f"guest token grant failed: {last_err}")


# ═══════════════════════════════════════════════════════════════════════════
#  CLAN JOIN (Fixed 400 Error)
# ═══════════════════════════════════════════════════════════════════════════
async def join_clan_for_account(account, clan_id):
    uid = str(account.get("uid") or "").strip()
    password = account.get("pass") or account.get("password")
    if not uid or not password:
        return False, "Missing uid or password"

    account_region = (account.get("region") or "IND").upper()

    # FORCE fresh token
    try:
        open_id, access_token, platform = await get_guest_token(uid, password)
    except Exception as e:
        return False, f"Token grant failed: {e}"
    if not open_id or not access_token:
        return False, "Failed to get token"

    platform = int(platform or 4)
    cfg_local = build_region_cfg(account_region)

    try:
        login = await asyncio.to_thread(
            major_login, "[clan]", open_id, access_token,
            cfg_local, platform, account_region
        )
    except Exception as e:
        return False, f"MajorLogin failed: {e}"

    jwt = login.get("jwt")
    base_url = login.get("game_url") or cfg_local["server_url"]
    payload = decode_jwt_payload(jwt) if jwt else {}
    region_from_jwt = (payload.get("lock_region") or account_region).upper()

    # Build RequestJoinClan protobuf
    body = bytearray()
    body.extend(enc_varint((1 << 3) | 0))
    body.extend(enc_varint(int(clan_id)))
    payload_bytes = AES.new(KEY, AES.MODE_CBC, IV).encrypt(pad(bytes(body), 16))

    headers = {
        "User-Agent": USER_AGENT_UNITY,
        "Accept": "*/*",
        "Accept-Encoding": "deflate, gzip",
        "X-Ga-Sv": str(int(time.time())),
        "Authorization": f"Bearer {jwt}",
        "X-Ga": "v1 1",
        "ReleaseVersion": _OB_VERSION,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Unity-Version": "2018.4.12f1",
        "Connection": "Keep-Alive",
        "Expect": "100-continue",
        "X-Region": region_from_jwt,
    }

    url = f"{base_url.rstrip('/')}/RequestJoinClan"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=payload_bytes,
                                    headers=headers, ssl=ssl_context) as r:
                status = r.status
                resp_body = await r.text()
    except Exception as e:
        return False, f"JoinClan failed: {e}"

    if status == 200:
        track_account_clan(uid, clan_id, account.get("name", ""),
                           account.get("ingame_id", ""))
        return True, "Successfully sent join request"
    
    # Print error detail
    return False, f"HTTP {status} - {resp_body[:200]}"


async def join_clan_interactive():
    print(f"\n  Enter Guild Uid => ", end="")
    try:
        clan_id = input().strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not clan_id or not clan_id.isdigit():
        print(f"  X Guild Uid must be numeric")
        return

    accounts = load_accounts()
    if not accounts:
        accounts = load_squad_accounts()
    if not accounts:
        print(f"  X No accounts found.")
        return

    tracker = load_clan_tracker()
    accounts_in_clans = tracker.get("accounts", {})
    available = [a for a in accounts if a.get("uid") not in accounts_in_clans]

    if not available:
        print(f"  ! All accounts already in clans.")
        return

    print(f"\n  Joining {len(available)} account(s) to clan {clan_id}...\n")
    ok_count = 0
    for acc in available:
        ok_flag, msg = await join_clan_for_account(acc, clan_id)
        if ok_flag:
            print(f"  Joined => {acc.get('name', '?')}")
            ok_count += 1
        else:
            print(f"  X {acc.get('name', '?')} => {msg}")
        await asyncio.sleep(1.0)

    print(f"\n  [+] done: {ok_count}/{len(available)} joined")