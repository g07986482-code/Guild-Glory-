# ═══════════════════════════════════════════════════════════════════════════
#  match.py — Match Engine (ALL REGIONS)
#  Owner: Anurag Singh | Telegram: @Developer_NovaG
# ═══════════════════════════════════════════════════════════════════════════

import asyncio
import socket
import struct
import time
import json
import os
import math
import sys
import itertools
import random
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

try:
    from protobuf_decoder.protobuf_decoder import Parser
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False
    Parser = None

from core import (
    _log, enc_aes, dec_aes, enc_varint, read_varint,
    ptag, f_vint, f_bytes, f_str, parse_proto, first_value,
    decode_jwt_payload, build_region_cfg, major_login, get_login_data,
    load_accounts, load_squad_accounts, _to_bytes,
    HARDCODED_CONFIG, _PLAY_VERSION, _OB_VERSION,
    REGION_LANG, REGION_GROUP, region_byte, region_prefix,
    POSE_STANDING, POSE_DASHING, CHAT_FOLLOW_TRIGGERS,
)

# ═══════════════ CONSTANTS ═══════════════
MATCH_MAX_LIFETIME = 700.0
MATCH_INFO_TIMEOUT = 60.0
SQUAD_PLAYERS = 4
SETTLE_AFTER_ALL_JOIN = 1.5
SQUAD_TIMEOUT = 600

SEND_HZ = 10.0
MOVE_INTERVAL = 1.0 / SEND_HZ
WALK_SPEED = 5150.0
STEP_PER_TICK = WALK_SPEED / SEND_HZ
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

# ═══════════════ AUTH AES ═══════════════
AUTH_AES_KEY = bytes([0x19, 0x47, 0xB9, 0x74, 0xD9, 0x73, 0xF3, 0x7F,
                      0x42, 0x06, 0x01, 0x38, 0x42, 0x00, 0x10, 0x30])
AUTH_AES_IV = bytes([0x28, 0x7F, 0xCA, 0x7A, 0xF9, 0x67, 0xF3, 0x7A,
                     0x65, 0x02, 0x01, 0x10, 0x40, 0x40, 0x00, 0x30])
AUTH_CMD = 0x65


def build_auth_datagram(token, account_id, region="IND"):
    payload = token.encode("utf-8") if isinstance(token, str) else token
    p = 16 - (len(payload) % 16)
    data = AES.new(AUTH_AES_KEY, AES.MODE_CBC, AUTH_AES_IV).encrypt(
        payload + bytes([p]) * p)
    out = bytearray()
    out.append(AUTH_CMD & 0xFF)
    out.append(region_byte(region) & 0xFF)
    out += struct.pack(">Q", int(account_id) & 0xFFFFFFFFFFFFFFFF)
    out += struct.pack(">I", int(time.time()) & 0xFFFFFFFF)
    out += struct.pack(">i", len(data))
    out += data
    return bytes(out)


async def build_auth_packet(account_id, token, server_time, key, iv,
                            region="IND", typ="OnLine"):
    uid_hex = f"{int(account_id):016x}"
    ts_hex = f"{int(server_time):08x}"
    enc = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(token.encode(), 16)).hex()
    enc_len = f"{len(enc) // 2:08x}"
    pre_on = region_prefix(region, "online")
    pre_chat = region_prefix(region, "chat")
    if typ == "OnLine":
        return bytes.fromhex(pre_on + uid_hex + ts_hex + "00000000" + enc_len + enc)
    return bytes.fromhex(pre_chat + uid_hex + ts_hex + enc_len + enc)


async def send_keep_alive(region="IND"):
    return bytes([0x02, region_byte(region) & 0xFF])


# ═══════════════ UDP CRYPTO ═══════════════
CRC7_TABLE = bytes([
    0, 9, 18, 27, 36, 45, 54, 63, 72, 65, 90, 83, 108, 101, 126, 119, 25, 16, 11, 2, 61, 52, 47, 38,
    81, 88, 67, 74, 117, 124, 103, 110, 50, 59, 32, 41, 22, 31, 4, 13, 122, 115, 104, 97, 94, 87,
    76, 69, 43, 34, 57, 48, 15, 6, 29, 20, 99, 106, 113, 120, 71, 78, 85, 92, 100, 109, 118, 127,
    64, 73, 82, 91, 44, 37, 62, 55, 8, 1, 26, 19, 125, 116, 111, 102, 89, 80, 75, 66, 53, 60, 39,
    46, 17, 24, 3, 10, 86, 95, 68, 77, 114, 123, 96, 105, 30, 23, 12, 5, 58, 51, 40, 33, 79, 70,
    93, 84, 107, 98, 121, 112, 7, 14, 21, 28, 35, 42, 49, 56, 65, 72, 83, 90, 101, 108, 119, 126,
    9, 0, 27, 18, 45, 36, 63, 54, 88, 81, 74, 67, 124, 117, 110, 103, 16, 25, 2, 11, 52, 61, 38,
    47, 115, 122, 97, 104, 87, 94, 69, 76, 59, 50, 41, 32, 31, 22, 13, 4, 106, 99, 120, 113, 78,
    71, 92, 85, 34, 43, 48, 57, 6, 15, 20, 29, 37, 44, 55, 62, 1, 8, 19, 26, 109, 100, 127, 118, 73,
    64, 91, 82, 60, 53, 46, 39, 24, 17, 10, 3, 116, 125, 102, 111, 80, 89, 66, 75, 23, 30, 5, 12,
    51, 58, 33, 40, 95, 86, 77, 68, 123, 114, 105, 96, 14, 7, 28, 21, 42, 35, 56, 49, 70, 79, 84,
    93, 98, 107, 112, 121,
])
_DELTA = 0x9E3779B9
_ROUNDS = 16
_FIELD_SIZES = {0: 1, 1: 2, 2: 2, 3: 1, 4: 2}
_FIELD_NAMES = {0: "sendOption", 1: "cmd", 2: "orderId", 3: "flags", 4: "length"}
HDR_RELIABLE = 10
UDP_HEAD_AND_ENCRY_SIZE = 40
MTU_LIMIT = 1300
_SALT_LEN, _ZERO_LEN = 2, 7


def optimize_udp_socket(sock):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)
    except Exception:
        pass


async def crc7_buff(crc, buf):
    c = crc & 0x7F
    for b in buf:
        c = CRC7_TABLE[((2 * (c & 0xFF)) ^ (b & 0xFF)) & 0xFF] & 0x7F
    return c & 0x7F


async def tea_enc(v0, v1, k0, k1, k2, k3):
    s = 0
    for _ in range(_ROUNDS):
        s = (s + _DELTA) & 0xFFFFFFFF
        v0 = (v0 + ((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF
                    ^ ((v1 + s) & 0xFFFFFFFF)
                    ^ (((v1 >> 5) + k1) & 0xFFFFFFFF))) & 0xFFFFFFFF
        v1 = (v1 + ((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF
                    ^ ((v0 + s) & 0xFFFFFFFF)
                    ^ (((v0 >> 5) + k3) & 0xFFFFFFFF))) & 0xFFFFFFFF
    return v0, v1


async def tea_dec(v0, v1, k0, k1, k2, k3):
    s = (_DELTA * _ROUNDS) & 0xFFFFFFFF
    for _ in range(_ROUNDS):
        v1 = (v1 - ((((v0 << 4) & 0xFFFFFFFF) + k2) & 0xFFFFFFFF
                    ^ ((v0 + s) & 0xFFFFFFFF)
                    ^ (((v0 >> 5) + k3) & 0xFFFFFFFF))) & 0xFFFFFFFF
        v0 = (v0 - ((((v1 << 4) & 0xFFFFFFFF) + k0) & 0xFFFFFFFF
                    ^ ((v1 + s) & 0xFFFFFFFF)
                    ^ (((v1 >> 5) + k1) & 0xFFFFFFFF))) & 0xFFFFFFFF
        s = (s - _DELTA) & 0xFFFFFFFF
    return v0, v1


async def tea_cbc_encrypt(padded, key_bytes):
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(padded))
    prev_cipher = bytearray(8)
    prev_intermediate = bytearray(8)
    for i in range(0, len(padded), 8):
        xored = bytearray(8)
        for j in range(8):
            xored[j] = padded[i + j] ^ prev_cipher[j]
        e0, e1 = await tea_enc(struct.unpack_from("<I", xored, 0)[0],
                               struct.unpack_from("<I", xored, 4)[0],
                               k0, k1, k2, k3)
        enc = bytearray(8)
        struct.pack_into("<I", enc, 0, e0)
        struct.pack_into("<I", enc, 4, e1)
        for j in range(8):
            out[i + j] = enc[j] ^ prev_intermediate[j]
        prev_cipher[:] = out[i:i + 8]
        prev_intermediate[:] = xored
        if i % 64 == 0:
            await asyncio.sleep(0)
    return bytes(out)


async def tea_cbc_decrypt(body, key_bytes):
    k0, k1, k2, k3 = (struct.unpack_from("<I", key_bytes, o)[0] for o in (0, 4, 8, 12))
    out = bytearray(len(body))
    prev_intermediate = bytearray(8)
    prev_cipher = bytearray(8)
    xored = bytearray(8)
    dec = bytearray(8)
    for i in range(0, len(body), 8):
        for j in range(8):
            xored[j] = body[i + j] ^ prev_intermediate[j]
        d0, d1 = await tea_dec(struct.unpack_from("<I", xored, 0)[0],
                               struct.unpack_from("<I", xored, 4)[0],
                               k0, k1, k2, k3)
        struct.pack_into("<I", dec, 0, d0)
        struct.pack_into("<I", dec, 4, d1)
        for j in range(8):
            out[i + j] = dec[j] ^ prev_cipher[j]
        prev_cipher[:] = body[i:i + 8]
        prev_intermediate[:] = dec
        if i % 64 == 0:
            await asyncio.sleep(0)
    return bytes(out)


async def build_padded(content):
    pad_len = (8 - (len(content) + 10) % 8) % 8
    return bytes([pad_len, 0, 0]) + b"\x00" * pad_len + content + b"\x00" * 7


async def oicq_unpad(padded):
    if not padded or len(padded) < 8:
        return None
    if not all(padded[-1 - i] == 0 for i in range(7)):
        return None
    pad_len = padded[0] & 0x07
    s = 3 + pad_len
    e = len(padded) - 7
    return padded[s:e] if s < e else b""


async def encode_header(layout, so, cmd, oid, flags, length, k, v80):
    out = bytearray()
    for code in layout:
        value = {0: so, 1: cmd, 2: oid, 3: flags, 4: length}[code]
        if _FIELD_SIZES[code] == 1:
            out.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            out.append(v & 0xFF)
            out.append((v >> 8) & 0xFF)
    return bytes(out)


async def layouts_from_mask(mask):
    s = str(mask).strip()
    try:
        ru = [int(c) for c in s]
    except ValueError:
        ru = [0, 1, 2, 3, 4]
    if sorted(ru) != [0, 1, 2, 3, 4]:
        ru = [0, 1, 2, 3, 4]
    return ru, [c for c in ru if c != 2]


async def build_packet(msg_key, layout, so, cmd, oid, flags, content, key, encrypted=True):
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    body = await tea_cbc_encrypt(await build_padded(content), key) if encrypted else content
    hdr = bytearray([msg_key, 0])
    for code in layout:
        value = {0: so, 1: cmd, 2: oid, 3: flags, 4: len(body)}[code]
        if _FIELD_SIZES[code] == 1:
            hdr.append((value & 0xFF) ^ k)
        else:
            v = ((value & 0xFFFF) ^ v80) & 0xFFFF
            hdr.append(v & 0xFF)
            hdr.append((v >> 8) & 0xFF)
    packet = bytearray(hdr + body)
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet)


async def build_hello_packet(text, key, layout):
    data = text.encode("utf-8")[:25]
    content = len(data).to_bytes(4, "little") + data + b"\x00" * 9
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    layout = [int(c) for c in str(layout).strip()]
    enc_body = await tea_cbc_encrypt(await build_padded(content), key)
    header_bytes = await encode_header(layout, 1, 1, 0, 1, len(enc_body), k, v80)
    packet = bytearray([0x63, 0x00]) + header_bytes + enc_body
    packet[1] = await crc7_buff(0, bytes(packet[2:])) & 0x7F
    return bytes(packet).hex()


# ═══════════════ VARINT PRIMITIVES ═══════════════
def _put_varint(out, v):
    v = int(v)
    while v >= 0x80:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    out.append(v & 0x7F)


def _put_zigvarint(out, v):
    z = (int(v) << 1) ^ (int(v) >> 63)
    _put_varint(out, z & 0xFFFFFFFFFFFFFFFF)


def _put_float_bits(out, f):
    bits = struct.unpack("<I", struct.pack("<f", float(f)))[0]
    _put_varint(out, bits)


def _put_string(out, s):
    raw = s.encode("utf-8") if isinstance(s, str) else s
    _put_zigvarint(out, len(raw))
    out += raw


def _rd_varint(b, p):
    v = i = 0
    while True:
        c = b[p + i]
        v |= (c & 0x7F) << (7 * i)
        i += 1
        if not c & 0x80:
            return v, p + i


def _zag(v):
    return (v >> 1) ^ -(v & 1)


# ═══════════════ JOIN / SPLIT TOKEN ═══════════════
def _tea_encrypt_len(n):
    t = 1 + _SALT_LEN + n + _ZERO_LEN
    r = t % 8
    return t + (8 - r if r else 0)


def _dg_size(token_len, reliable=True):
    zv = bytearray()
    _put_zigvarint(zv, token_len)
    body = len(zv) + token_len
    return (HDR_RELIABLE if reliable else 8) + _tea_encrypt_len(body)


def split_token_bytes(token_bytes):
    n = len(token_bytes)
    raw = int(n * 0.85)
    p1 = raw - (raw % 40)
    while UDP_HEAD_AND_ENCRY_SIZE + _dg_size(p1) > MTU_LIMIT and p1 > 40:
        p1 -= 40
    return token_bytes[:p1], token_bytes[p1:]


def build_join_info_head(account_id, game_mode=15, match_mode=1, map_id=1,
                         country="IND", client_version="1.132.13",
                         client_version_code="2019121229",
                         client_url=("csoversea.stronghold.freefiremobile.com;"
                                     "0.0.0.0;34.126.76.45;34.87.177.14;"
                                     "34.87.170.230;35.185.183.57"),
                         room_id=0, match_id=0,
                         drift_bottle_owner_id=0, drift_bottle_owner_name="",
                         enable_antihack_tick=1, friend_count=0,
                         client_ip="", client_fingerprint="",
                         session_tag=0, is_emulator=1):
    room = int(match_id or room_id)
    b = bytearray()
    _put_varint(b, int(account_id))
    _put_varint(b, room)
    b.append(1)
    b.append(int(game_mode) & 0xFF)
    _put_varint(b, room)
    b.append(int(map_id) & 0xFF)
    b.append(0); _put_varint(b, 0); _put_varint(b, 0); b.append(0)
    b.append(int(is_emulator) & 0xFF)
    b.append(0); b.append(1); b.append(2); b.append(3)
    b.append(int(enable_antihack_tick) & 0xFF)
    b.append(1)
    _put_string(b, country)
    _put_varint(b, 0)
    b.append(1); b.append(2); b.append(0); b.append(1); b.append(0); b.append(0); b.append(4)
    _put_string(b, client_version)
    _put_string(b, client_version_code)
    _put_string(b, client_url)
    b.append(0); b.append(0)
    _put_varint(b, int(friend_count))
    b.append(0)
    _put_varint(b, int(drift_bottle_owner_id))
    _put_string(b, drift_bottle_owner_name or "")
    b.append(1)
    _put_string(b, ""); _put_string(b, "")
    b.append(0)
    _put_varint(b, 0); _put_varint(b, 0)
    b.append(0); b.append(0); b.append(0)
    _put_varint(b, 0)
    _put_string(b, "")
    _put_varint(b, 0)
    b.append(0); b.append(1); b.append(0); b.append(0)
    _put_varint(b, 0); _put_varint(b, 0)
    b.append(0); b.append(1)
    _put_string(b, "")
    _put_varint(b, 0)
    b.append(0); b.append(0); b.append(0)
    b.append(int(match_mode) & 0xFF)
    b.append(0)
    _put_varint(b, int(session_tag))
    b.append(2); b.append(0)
    _put_string(b, client_ip or "")
    _put_string(b, client_fingerprint or "")
    return bytes(b)


def build_join_post_body(account_id, token_part2, **kw):
    body = bytearray()
    body += build_join_info_head(account_id, **kw)
    _put_string(body, token_part2)
    return bytes(body)


async def build_join_match_startup(join_token, udp_key, match_code, account_id, block_val,
                                   server_ip="", region="IND",
                                   client_version="1.132.13",
                                   client_version_code="2019121229",
                                   access_token="", match_id=0, country="IND",
                                   map_id=1, game_mode=15, match_mode=1):
    join_token = join_token.strip()
    udp_key_b = bytes.fromhex(udp_key)
    match_code = [int(c) for c in str(match_code).strip()]
    enc_token = join_token.encode("utf-8") if isinstance(join_token, str) else join_token
    part1, part2 = split_token_bytes(enc_token)
    prepare_body = bytearray()
    _put_string(prepare_body, part1)
    prepare_pkt = (await build_packet(0x5E, match_code, 2, 447, 0, 1,
                                      bytes(prepare_body), udp_key_b)).hex()
    post_body = build_join_post_body(
        account_id, part2,
        game_mode=game_mode, match_mode=match_mode, map_id=map_id,
        country=country, client_version=client_version,
        client_version_code=client_version_code,
        match_id=int(match_id or block_val),
        client_ip=server_ip.split(":")[0] if server_ip else "",
    )
    post_pkt = await build_packet(0x5A, match_code, 2, 448, 1, 1, post_body, udp_key_b)
    return [prepare_pkt], post_pkt.hex()


async def decode_packet(packet, key, mask=None):
    data = bytes(packet) if isinstance(packet, bytes) else bytes.fromhex(packet)
    if len(data) < 8:
        return None
    k = key[0]
    v80 = ((k << 8) | k) & 0xFFFF
    crc_ok = (data[1] & 0x7F) == await crc7_buff(0, data[2:])
    if mask:
        ru, nr = await layouts_from_mask(mask)
        layouts = [("RUDP", ru), ("nonRUDP", nr)]
    else:
        layouts = [("RUDP", list(p)) for p in itertools.permutations([0, 1, 2, 3, 4])]
        layouts += [("nonRUDP", list(p)) for p in itertools.permutations([0, 1, 3, 4])]
    cands = []
    for kind, layout in layouts:
        off = 2
        f = {}
        ok = True
        for code in layout:
            size = _FIELD_SIZES[code]
            if off + size > len(data):
                ok = False
                break
            f[_FIELD_NAMES[code]] = (data[off] ^ k) if size == 1 else \
                ((data[off] | (data[off + 1] << 8)) ^ v80) & 0xFFFF
            off += size
        if not ok:
            continue
        if f["flags"] > 7 or f["sendOption"] > 7:
            continue
        if f["length"] != len(data) - off:
            continue
        body = data[off:off + f["length"]]
        content = None
        if f["flags"] & 1:
            if len(body) < 8 or len(body) % 8 != 0:
                continue
            content = await oicq_unpad(await tea_cbc_decrypt(body, key))
            if content is None:
                continue
        else:
            content = body
        score = (1 if crc_ok else 0) + (1 if content is not None else 0)
        cands.append({"kind": kind, "layout": layout, "headerLen": off,
                      "msgKey": data[0], "cmd": f["cmd"], "flags": f["flags"],
                      "sendOrder": f["sendOption"], "orderId": f.get("orderId"),
                      "length": f["length"], "content": content,
                      "crcOk": crc_ok, "score": score})
    if not cands:
        return None
    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands[0]


# ═══════════════ STATE BUILDERS ═══════════════
def build_player_state_upload(player_id, pos, rot, tdir, vel, aim_float,
                              server_time, physx_state=0, physx_pose=0,
                              platform=0, low_grav=0, ping=0,
                              jump=0, slide=0, custom=0):
    o = bytearray()
    _put_varint(o, int(player_id))
    _put_zigvarint(o, pos[0]); _put_zigvarint(o, pos[1]); _put_zigvarint(o, pos[2])
    _put_zigvarint(o, rot[0]); _put_zigvarint(o, rot[1]); _put_zigvarint(o, rot[2])
    _put_zigvarint(o, tdir[0]); _put_zigvarint(o, tdir[1])
    _put_zigvarint(o, vel[0]); _put_zigvarint(o, vel[1]); _put_zigvarint(o, vel[2])
    o.append(physx_state & 0xFF)
    o.append(physx_pose & 0xFF)
    _put_float_bits(o, aim_float[0])
    _put_float_bits(o, aim_float[1])
    _put_float_bits(o, aim_float[2])
    _put_varint(o, platform)
    o.append(1 if low_grav else 0)
    _put_varint(o, ping)
    o.append(jump & 0xFF)
    _put_varint(o, slide)
    o.append(custom & 0xFF)
    _put_varint(o, server_time & 0xFFFFFFFF)
    return bytes(o)


# ═══════════════ DECODERS ═══════════════
def parse_player_join(body):
    if body is None or len(body) < 4:
        return None
    try:
        p = 0
        user_id, p = _rd_varint(body, p)
        _samo, p = _rd_varint(body, p)
        player_id, p = _rd_varint(body, p)
        raw_len, p = _rd_varint(body, p)
        n = _zag(raw_len)
        name = body[p:p + n].decode("utf-8", "replace")
    except (IndexError, ValueError):
        return None
    return user_id, player_id, name


def decode_my_state(body):
    if body is None or len(body) < 6:
        return None
    try:
        p = 0
        _mt, p = _rd_varint(body, p)
        _cnt, p = _rd_varint(body, p)
        p += 1
        x, p = _rd_varint(body, p)
        y, p = _rd_varint(body, p)
        z, p = _rd_varint(body, p)
    except (IndexError, ValueError):
        return None
    return (_zag(x), _zag(y), _zag(z))


def decode_players_v2(body):
    players = {}
    if body is None or len(body) < 4:
        return players
    p = 2
    while p < len(body) - 1:
        try:
            short_id = body[p]; p += 1
            x, p = _rd_varint(body, p); y, p = _rd_varint(body, p); z, p = _rd_varint(body, p)
            vx, p = _rd_varint(body, p); vy, p = _rd_varint(body, p); vz, p = _rd_varint(body, p)
            yrot = body[p]; p += 1
            aim_y = body[p]; p += 1
            aim_xz = body[p]; p += 1
            pstate = body[p]; p += 1
            ppose = body[p]; p += 1
            _plat, p = _rd_varint(body, p)
            _cust = body[p]; p += 1
        except (IndexError, ValueError):
            break
        pos = (_zag(x), _zag(y), _zag(z))
        if not (1 <= short_id <= 64):
            break
        if any(abs(v) > 4000000 for v in pos):
            break
        players[short_id] = {
            "pos": pos, "vel": (_zag(vx), _zag(vy), _zag(vz)),
            "yrot": yrot, "aim_y": aim_y, "aim_xz": aim_xz,
            "physx_state": pstate, "physx_pose": ppose,
        }
    return players


def decode_server_time(body):
    if not body:
        return None
    try:
        tick, p = _rd_varint(body, 0)
        phase = body[p] if p < len(body) else 0
    except (IndexError, ValueError):
        return None
    return tick, phase


def _read_vec2pos(b, p):
    x, p = _rd_varint(b, p); z, p = _rd_varint(b, p)
    return (_zag(x), _zag(z)), p


def decode_safezone(body):
    if not body:
        return None
    try:
        p = 0
        stage = body[p]; p += 1
        outer_center, p = _read_vec2pos(body, p)
        outer_radius, p = _rd_varint(body, p)
        inner_center, p = _read_vec2pos(body, p)
        inner_radius, p = _rd_varint(body, p)
        _tst = body[p] if p < len(body) else 0; p += 1
        start_time, p = _rd_varint(body, p)
        end_time, p = _rd_varint(body, p)
    except (IndexError, ValueError):
        return None
    return {"stage": stage, "outer_center": outer_center, "outer_radius": outer_radius,
            "inner_center": inner_center, "inner_radius": inner_radius,
            "start": start_time, "end": end_time}


def parse_gri_block(body):
    if body is None or len(body) < 2:
        return {}
    try:
        block_len = struct.unpack_from("<H", body, 0)[0]
    except struct.error:
        return {}
    p = 2
    end = min(2 + block_len, len(body))
    fields = {}
    while p < end:
        fid = body[p]; p += 1
        if p >= end:
            break
        try:
            v, p = _rd_varint(body, p)
        except (IndexError, ValueError):
            break
        fields[fid] = v
    return fields


def get_match_phase(body):
    fields = parse_gri_block(body)
    if 3 not in fields:
        return None
    value = fields[3]
    if value < 0x10000:
        return None
    phase = (value >> 16) & 0xFFFF
    start = (value >> 32) & 0xFFFFFFFF
    end = value & 0xFFFF
    return phase, fields.get(2), start, end


def decode_quick_chat(body):
    if body is None or len(body) < 3:
        return None
    try:
        p = 0
        chat_id, p = _rd_varint(body, p)
        _item, p = _rd_varint(body, p)
        sender, p = _rd_varint(body, p)
    except (IndexError, ValueError):
        return None
    return chat_id, sender & 0xFF, sender


# ═══════════════ MOVEMENT STATE ═══════════════
class MovementState:
    def __init__(self, account_id):
        self.account_id = int(account_id)
        self.my_id = None
        self.my_short = None
        self.my_pos = None
        self.server_pos = None
        self.target_short = None
        self.target_pos = None
        self.target_seen = None
        self.target_vel = (0.0, 0.0)
        self.target_pose = 0
        self.target_state = 0
        self.target_yrot = 0
        self.target_aim_y = 0
        self.target_aim_xz = 0
        self.zone_center = None
        self.zone_radius = 0.0
        self.phase = None
        self.round_no = None
        self.server_tick = None
        self.tick_local = None
        self.tick_rate = 30.0
        self.alive = True
        self.downed = {}
        self.roster = {}
        self.joined_at = None
        self.blocked = 0
        self.yaw = 0.0
        self.orbit_angle = 0.0

    def teammates(self):
        if self.my_id is None:
            return set()
        team = (self.my_id >> 24) & 0xFF
        return {s for s, (fid, _) in self.roster.items()
                if (fid >> 24) & 0xFF == team and s != self.my_short}

    def set_identity(self, full_id):
        self.my_id = int(full_id)
        self.my_short = self.my_id & 0xFF
        if self.joined_at is None:
            self.joined_at = time.time()

    def add_player(self, full_id, name):
        self.roster[int(full_id) & 0xFF] = (int(full_id), name)

    def name_of(self, short):
        entry = self.roster.get(short)
        return entry[1] if entry else "?"

    def seed_my_pos(self, pos):
        self.server_pos = pos
        if self.my_pos is None:
            self.my_pos = pos
            self.blocked = 0
            return
        dx = pos[0] - self.my_pos[0]
        dz = pos[2] - self.my_pos[2]
        gap = math.sqrt(dx * dx + dz * dz)
        if gap > 120000.0:
            self.my_pos = pos
            self.blocked = 0
        elif gap > 1500.0:
            self.blocked += 1
            if self.blocked >= 5:
                self.my_pos = pos
                self.blocked = 0
        else:
            self.blocked = 0

    def set_target(self, short):
        if self.my_short is not None and short == self.my_short:
            return False
        if short != self.target_short:
            self.target_pos = None
        self.target_vel = (0.0, 0.0)
        self.target_seen = None
        self.target_short = short
        return True

    def update_target(self, info, now):
        prev_pos, prev_seen = self.target_pos, self.target_seen
        self.target_pos = info["pos"]
        self.target_seen = now
        if prev_pos is not None and prev_seen is not None:
            dt = now - prev_seen
            if 0.01 < dt < 2.0:
                vx = (info["pos"][0] - prev_pos[0]) / dt
                vz = (info["pos"][2] - prev_pos[2]) / dt
                if abs(vx) < 30000 and abs(vz) < 30000:
                    self.target_vel = (vx, vz)
        self.target_yrot = info.get("yrot", self.target_yrot)
        self.target_aim_y = info.get("aim_y", self.target_aim_y)
        self.target_aim_xz = info.get("aim_xz", self.target_aim_xz)
        self.target_state = info.get("physx_state", self.target_state)
        self.target_pose = info.get("physx_pose", self.target_pose)

    def sync_clock(self, tick, now):
        if self.server_tick is not None and self.tick_local is not None:
            dt = now - self.tick_local
            dtick = tick - self.server_tick
            if dt > 0.5 and 0 < dtick < 10000:
                self.tick_rate = self.tick_rate * 0.7 + (dtick / dt) * 0.3
        self.server_tick = tick
        self.tick_local = now

    def server_time(self, now):
        if self.server_tick is None:
            if self.joined_at is None:
                return 0
            return int((now - self.joined_at) * 1000.0) & 0xFFFFFFFF
        elapsed = now - self.tick_local
        ticks = self.server_tick + elapsed * self.tick_rate
        return int(ticks * 1000.0 / self.tick_rate) & 0xFFFFFFFF


class MovementPlanner:
    def __init__(self, step=STEP_PER_TICK, orbit_fraction=0.55, orbit_speed=6.0,
                 auto_zone=True, move_in_prepare=True, stick_dist=150.0,
                 max_step=None, coast_limit=3.0):
        self.step = float(step)
        self.max_step = float(max_step or step * 1.25)
        self.orbit_fraction = float(orbit_fraction)
        self.orbit_speed = float(orbit_speed)
        self.auto_zone = bool(auto_zone)
        self.move_in_prepare = bool(move_in_prepare)
        self.stick_dist = float(stick_dist)
        self.coast_limit = float(coast_limit)
        self._last_yaw = 0.0

    def next_yaw(self):
        return self._last_yaw

    def aim_point(self, st, now):
        rescue = self._rescue_point(st)
        if rescue is not None:
            return rescue
        target = self._target_point(st, now)
        zone = self._zone_point(st)
        if target is None:
            return zone
        if zone is not None and self._outside_zone(st, target):
            return zone
        return target

    def _target_point(self, st, now):
        if st.target_pos is None:
            return None
        if st.target_seen is not None:
            gap = now - st.target_seen
            if 0.05 < gap < self.coast_limit:
                vx, vz = st.target_vel
                return (st.target_pos[0] + vx * gap,
                        st.target_pos[1],
                        st.target_pos[2] + vz * gap)
        return st.target_pos

    def _rescue_point(self, st):
        if not st.downed or st.my_pos is None:
            return None
        best, best_d = None, None
        for pos in st.downed.values():
            if pos is None:
                continue
            dx = pos[0] - st.my_pos[0]
            dz = pos[2] - st.my_pos[2]
            d = math.sqrt(dx * dx + dz * dz)
            if best_d is None or d < best_d:
                best, best_d = pos, d
        return best

    def _zone_point(self, st):
        if not self.auto_zone or st.zone_center is None or st.zone_radius <= 0:
            return None
        cx, cz = st.zone_center[0], st.zone_center[-1]
        y = st.my_pos[1] if st.my_pos else 0
        ring = st.zone_radius * self.orbit_fraction
        if st.my_pos is not None:
            dx = st.my_pos[0] - cx
            dz = st.my_pos[2] - cz
            here = math.sqrt(dx * dx + dz * dz)
            if here <= ring * 1.15:
                if here > 1:
                    st.orbit_angle = math.degrees(math.atan2(dz, dx))
                stride = float(self.step)
                max_deg = math.degrees(stride / max(ring, 1)) * 0.85
                st.orbit_angle = (st.orbit_angle + min(self.orbit_speed, max_deg)) % 360.0
                rad = math.radians(st.orbit_angle)
                return (cx + ring * math.cos(rad), y, cz + ring * math.sin(rad))
        return (cx, y, cz)

    def _outside_zone(self, st, point):
        if st.zone_center is None or st.zone_radius <= 0:
            return False
        cx, cz = st.zone_center[0], st.zone_center[-1]
        dx = point[0] - cx
        dz = point[2] - cz
        return math.sqrt(dx * dx + dz * dz) > st.zone_radius * 0.75

    def plan(self, st, now):
        if st.my_pos is None or st.my_id is None:
            return None
        my = st.my_pos
        if st.phase is None:
            return my, 0.0, False
        phases = (PHASE_FIGHT,)
        if self.move_in_prepare:
            phases = (PHASE_FIGHT, PHASE_PREPARE, 2, 9)
        if st.phase not in phases:
            return my, 0.0, False
        aim = self.aim_point(st, now)
        if aim is None:
            return my, 0.0, False
        dx = aim[0] - my[0]
        dz = aim[2] - my[2]
        dist = math.sqrt(dx * dx + dz * dz)
        ty = aim[1] if len(aim) > 2 else my[1]
        new_y = int(my[1] + (ty - my[1]) * 0.35)
        if dist <= self.stick_dist or dist < 1e-6:
            return (my[0], new_y, my[2]), dist, False
        step = float(self.step)
        if dist > 8000.0:
            step = self.max_step
        move = step if dist > step else dist
        nx = my[0] + dx / dist * move
        nz = my[2] + dz / dist * move
        return (int(nx), new_y, int(nz)), dist, True


def _build_position_body(player_id, old_pos, new_pos, aim_yaw, server_time, moving):
    if moving and old_pos is not None:
        dx = new_pos[0] - old_pos[0]
        dz = new_pos[2] - old_pos[2]
        dist = math.sqrt(dx * dx + dz * dz)
        if dist >= 1:
            ux, uz = dx / dist, dz / dist
            vel = (int(ux * 500), 0, int(uz * 500))
            rot = (int(ux * 100), 0, int(uz * 100))
            tdir = (int(ux * 100), int(uz * 100))
            aim = (ux, 0.0, uz)
            pose = POSE_DASHING
        else:
            vel = (0, 0, 0)
            rot = (0, 0, 0)
            tdir = (0, 0)
            aim = (0.0, 0.0, 0.0)
            pose = POSE_STANDING
    else:
        vel = (0, 0, 0)
        rad = math.radians(aim_yaw)
        fx, fz = math.sin(rad), math.cos(rad)
        rot = (int(fx * 100), 0, int(fz * 100))
        tdir = (int(fx * 100), int(fz * 100))
        aim = (fx, 0.0, fz)
        pose = POSE_STANDING
    return build_player_state_upload(
        player_id, new_pos, rot, tdir, vel, aim, server_time,
        physx_state=0, physx_pose=pose, ping=90)


# ═══════════════ DISPATCH INCOMING ═══════════════
def dispatch_incoming(cmd, body, st, tag, verbose=False):
    if body is None:
        return
    if cmd == CMD_PLAYER_JOIN:
        info = parse_player_join(body)
        if info is None:
            return
        uid, full_id, name = info
        st.add_player(full_id, name)
        if uid == st.account_id:
            st.set_identity(full_id)
    elif cmd == CMD_MY_STATE:
        pos = decode_my_state(body)
        if pos is not None:
            st.seed_my_pos(pos)
    elif cmd == CMD_OTHER_STATES:
        players = decode_players_v2(body)
        mates = st.teammates()
        for short, info in players.items():
            if short not in mates:
                continue
            if info.get("physx_pose") == 8:
                st.downed[short] = info["pos"]
            elif short in st.downed:
                st.downed.pop(short, None)
        if st.target_short is not None:
            info = players.get(st.target_short)
            if info is not None:
                st.update_target(info, time.time())
    elif cmd == CMD_SERVER_TIME:
        parsed = decode_server_time(body)
        if parsed is not None:
            st.sync_clock(parsed[0], time.time())
    elif cmd == CMD_GRI_SYNC:
        parsed = get_match_phase(body)
        if parsed is not None:
            phase, round_no, _s, _e = parsed
            st.phase = phase
            if round_no is not None:
                st.round_no = round_no
    elif cmd == CMD_SAFE_ZONE:
        zone = decode_safezone(body)
        if zone is None:
            return
        center = zone.get("inner_center") or zone.get("outer_center")
        radius = zone.get("inner_radius") or zone.get("outer_radius") or 0
        if center and radius > 0:
            st.zone_center = (center[0], 0, center[1])
            st.zone_radius = radius * ZONE_RADIUS_SCALE
    elif cmd == CMD_QUICK_CHAT:
        parsed = decode_quick_chat(body)
        if parsed is None:
            return
        chat_id, short, _raw = parsed
        if chat_id in (QUICK_CHAT_FOLLOW, QUICK_CHAT_HELP):
            st.set_target(short)
    elif cmd == CMD_DEAD:
        try:
            pid, _ = _rd_varint(body, 0)
        except (IndexError, ValueError):
            return
        if st.my_id is not None and pid == st.my_id:
            st.alive = False


# ═══════════════ MOVEMENT LOOP ═══════════════
async def movement_loop(sock, remote_addr, udp_key_b, match_code, state, stop_event, tag):
    planner = MovementPlanner()
    nr = (await layouts_from_mask(match_code))[1]
    loop = asyncio.get_event_loop()
    next_tick = time.time()
    while not stop_event.is_set():
        now = time.time()
        if now < next_tick:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=next_tick - now)
                break
            except asyncio.TimeoutError:
                pass
            continue
        next_tick += MOVE_INTERVAL
        if next_tick < now:
            next_tick = now + MOVE_INTERVAL
        if not state.alive or state.my_id is None:
            continue
        planned = planner.plan(state, now)
        if planned is None:
            continue
        new_pos, dist, moving = planned
        old_pos = state.my_pos
        state.my_pos = new_pos
        yaw = planner.next_yaw()
        srv_time = state.server_time(now)
        body = _build_position_body(state.my_id, old_pos, new_pos, yaw, srv_time, moving)
        pkt = await build_packet(0x6B, nr, 0, CMD_MY_STATE, None, 1,
                                 body, udp_key_b, encrypted=True)
        try:
            await loop.sock_sendto(sock, pkt, remote_addr)
        except Exception:
            pass


# ═══════════════ MAIN UDP PLAY LOOP ═══════════════
async def play_game(server_ip_port, prepare_packets, post_packet, udp_key, match_code,
                    account_id, player_region, client_version, tag="[?]",
                    account_jwt="", sleep_ms=0, squad_done=None):
    match_start = time.time()
    ping_task = afk_task = hello_task = sock = None
    ping_stop = asyncio.Event()
    afk_stop = asyncio.Event()
    state = MovementState(account_id)
    reason = "ended"

    try:
        ip, port = server_ip_port.split(":")
        port = int(port)
        resolved_ip = socket.gethostbyname(ip)
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        optimize_udp_socket(sock)
        sock.setblocking(False)
        udp_key_b = bytes.fromhex(udp_key)
        remote = (resolved_ip, port)
        gap = sleep_ms / 1000.0 if sleep_ms else 0.02

        if account_jwt:
            auth_pkt = build_auth_datagram(account_jwt, account_id, player_region)
            await loop.sock_sendto(sock, auth_pkt, remote)

        hello_hex = await build_hello_packet(f"{account_id}_2585", udp_key_b, match_code)
        hello_bytes = bytes.fromhex(hello_hex)
        await loop.sock_sendto(sock, hello_bytes, remote)
        _log(f"{tag} UDP connected remote={resolved_ip}:{port}")

        ack_state = "waiting_for_hello_reply"
        startup_sent = False
        local_closed = False
        send_lock = asyncio.Lock()
        nr = (await layouts_from_mask(match_code))[1]

        async def ka_loop():
            pklist = [0x66, 0x6D, 0x69, 0x6C, 0x6B, 0x6E, 0x6F, 0x70]
            i = 0
            while not ping_stop.is_set():
                if ack_state != "waiting_for_hello_reply":
                    break
                try:
                    await asyncio.wait_for(ping_stop.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
            while not ping_stop.is_set():
                pk = pklist[i % len(pklist)]
                cnt = int(time.time() * 1000) & 0xFFFFFFFF
                pkt = await build_packet(pk, nr, 0, 3, None, 0,
                                         cnt.to_bytes(4, "little") + b"\x00\x00\x00",
                                         udp_key_b, encrypted=False)
                try:
                    await loop.sock_sendto(sock, pkt, remote)
                except Exception:
                    pass
                i += 1
                try:
                    await asyncio.wait_for(ping_stop.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    pass

        async def hello_retry_loop():
            for _ in range(8):
                if ping_stop.is_set() or ack_state != "waiting_for_hello_reply":
                    return
                try:
                    await asyncio.wait_for(ping_stop.wait(), timeout=0.8)
                except asyncio.TimeoutError:
                    pass
                if ping_stop.is_set() or ack_state != "waiting_for_hello_reply":
                    return
                try:
                    await loop.sock_sendto(sock, hello_bytes, remote)
                except Exception:
                    pass

        ping_task = asyncio.create_task(ka_loop())
        hello_task = asyncio.create_task(hello_retry_loop())
        afk_task = asyncio.create_task(
            movement_loop(sock, remote, udp_key_b, match_code, state, afk_stop, tag))
        last_activity = time.time()

        async def send_join_match():
            nonlocal ack_state, startup_sent
            if startup_sent:
                return
            async with send_lock:
                if startup_sent:
                    return
                for p in prepare_packets:
                    await loop.sock_sendto(sock, bytes.fromhex(p), remote)
                    await asyncio.sleep(gap)
                await asyncio.sleep(gap)
                await loop.sock_sendto(sock, bytes.fromhex(post_packet), remote)
                startup_sent = True
                ack_state = "startup_sent"
                _log(f"{tag} -> PREPARE+POST sent")

        while not local_closed:
            if time.time() - match_start > MATCH_MAX_LIFETIME:
                reason = "ended"
                break
            try:
                resp, sa = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 65535), timeout=1.5)
                if resp:
                    last_activity = time.time()
                    frame = await decode_packet(resp, udp_key_b, match_code)
                    if frame:
                        cmd = frame.get('cmd')
                        oid = frame.get('orderId')
                        msg_key = frame.get('msgKey', 0)
                        content = frame.get('content')

                        if msg_key < 100 and oid is not None:
                            da = await build_packet(
                                0x68, nr, 0, 2, None, 1,
                                ((oid + 1) & 0xFFFF).to_bytes(2, "little"),
                                udp_key_b)
                            await loop.sock_sendto(sock, da, sa)

                        if cmd == 1:
                            if ack_state == "waiting_for_hello_reply":
                                ack_state = "ready_to_send_startup"
                        elif cmd == 3:
                            c = content or b""
                            cnt = c[:4] if len(c) >= 4 else c
                            rp = await build_packet(0x6D, nr, 0, 3, None, 0,
                                                    cnt + b"\x00\x00\x00",
                                                    udp_key_b, encrypted=False)
                            await loop.sock_sendto(sock, rp, sa)
                        elif cmd == 130:
                            _log(f"{tag}   [OK] JOIN_MATCH_FINISHED - in game")
                        elif cmd == 103:
                            _log(f"{tag}   [END] MATCH_END received")
                            local_closed = True
                            reason = "ended"
                        dispatch_incoming(cmd, content, state, tag)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                _log(f"{tag} UDP err: {e}")
                await asyncio.sleep(0.5)
            if ack_state == "ready_to_send_startup" and not startup_sent:
                await send_join_match()
            elif ack_state == "startup_sent" and (time.time() - last_activity) > 30:
                reason = "ended"
                break
    except Exception as e:
        _log(f"{tag} UDP err: {e}")
        reason = "error"
    finally:
        ping_stop.set()
        afk_stop.set()
        for t in (ping_task, hello_task, afk_task):
            if t:
                t.cancel()
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        _log(f"{tag} UDP closed reason={reason}")
        # --- YE HAI LOOP FIX ---
        if squad_done is not None:
            squad_done["count"] = squad_done.get("count", 0) + 1
            if squad_done["count"] >= squad_done["total"]:
                squad_done["event"].set()
    return reason


# ═══════════════ SQUAD TEAM PROTOBUF HELPERS ═══════════════
_C_S1 = "0200044B122D3B02010000000000000000000000000000E3172CED00"
_C_14_1 = b"\x32" + bytes([len(_C_S1)]) + _C_S1.encode() + b"\x30\x30" * 3
_C_14_3 = bytes.fromhex(
    "7e585c521207074f5d030c5c545104570455070f0a555a085201095701025b560601545606010f07100802487d5c4043481e07"
    "1f081a1709034c0757787500566b45627e7a6548407565577a700e7708627a047e7e041005447b5d655070547e437c607f7656"
    "5675704e5877525b5a5b515662410a105f5c5a4c1e637f1c7147430b4f6c557778605b67416b50635850500056575e005a7606"
    "057005067e0c15060045455e56447a665a6672694b5046524b057b79427c715560577b575f0a120e4b470e631b536262186b0f"
    "73406359475343795c481d7918564b47790c13054d1d714b5d75451740515f7e586d414e40595a03000e654e0741507a091b08"
    "4c6668777b1c4c676517505d6e7a4c4e7d7c791f5269057f42440207041005004d7e5c5977037d4a631f560255026b7a647e6b"
    "0007015503746353500e1a0048701a0153626506774f18065e0558610457421856007313771b60010b140745554d7f50477d68"
    "770662600646696876026242541c4a49037f74750a1204074f487402135059457f517b415266604a434506064e79004c5a7b4f"
    "700d14044a58454a5a7c5e5f5b764354425e1267735041537d6041180a6d694305"
)
_C_14_7 = bytes.fromhex("1d02474b420204030506171d677c716374687d5f557051565753")
_C_14_11 = b"\x03" + (
    "bbSQ69i8H3F5AdV2KyoVlWj2cgPtsEL3Pi8QcWkc/NJiGxtxXsmeZDDwFPKPbvd56sULGeaD3qha9S6hKIkIb3oXVAAFErlI76uU2p2AqNdJyaucxz1ba5ecHPCBohQR6E5Y1UzpsgpxutURpI8pbqY0tCpeL1bOT+F5UaysgFmTeoIalHxxEYPQx7OVJHElCV5el0vpIs98JSA3nB8FWin6ckz5Fd0sG4n2g0B7OUOvcreqilCT737xI24wPxLdidSr1AJ2MK0/m3ugV1iqzPXhttKyvfmMNVY8DoXBBUcYt3vpK7mgbnietrOqJIbJC3O4ygX6IWl/hkp+ngsjfeOZSornpzFnxM/kkqZgZjVOweXe61FRU6JsGSeTeY63kqA/mbCPfdwodSYJE2hXfVJofxRG1644gFPYRkCPUjJazd2l9WAh9kd86kYbjphbxwz55ciWvZ3sDJR11W96ezyxJPhJPD8FQoQVmno6BP4e7QI1xe+h35bkS1epZq6K6xUP5YtHFvqbhARMNQKUYYzXQWRFMNL1JgAeMJNO0+eCPL57+RXzRKtlgM/rVsIWhNw8Oo9SdP+7wsGrMK+HIOJaF1apAXNRQ9mCqxI="
).encode()


def _vi(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _one(field, v):
    if isinstance(v, dict):
        body = _pb(v)
        return _vi((field << 3) | 2) + _vi(len(body)) + body
    if isinstance(v, int):
        return _vi(field << 3) + _vi(v)
    if isinstance(v, (str, bytes)):
        b = v.encode() if isinstance(v, str) else v
        return _vi((field << 3) | 2) + _vi(len(b)) + b
    raise TypeError(type(v))


def _pb(fields):
    out = bytearray()
    for f, v in fields.items():
        if isinstance(v, list):
            for it in v:
                out += _one(f, it)
        else:
            out += _one(f, v)
    return bytes(out)


def _br_frame(ptype, region, proto, key, iv):
    enc = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(proto, 16))
    return bytes([ptype, region_byte(region)]) + len(enc).to_bytes(4, "big") + enc


def _br_idc(reg, pings=(75, 123)):
    return [{1: "IDC1", 2: pings[0], 3: reg},
            {1: "IDC2", 2: pings[1], 3: reg}]


def br_create_squad_pkt(region, client_version, key, iv):
    reg = str(region or "IND").upper()
    f = {
        1: 1,
        2: {
            2: b"\x01", 3: 1, 4: SQUAD_PLAYERS - 1, 5: "en",
            8: _br_idc(reg), 9: 2,
            10: bytes.fromhex("01090a0b12191a202729"),
            11: 1, 13: 1,
            14: {1: _C_14_1, 2: 40, 3: _C_14_3, 4: "w\\Z]", 6: 12, 7: _C_14_7,
                 8: client_version or "1.132.13", 9: 6, 10: 2, 11: _C_14_11},
            19: 329, 21: bytes.fromhex("374f521955"),
            24: [{1: 3, 2: 360}, {1: 4, 2: 391}, {1: 5, 2: 156},
                 {1: 29, 2: 204}, {1: 22, 2: 118}, {1: 14, 2: 139}, {1: 21}],
            30: "https://dl-ind-production.freefiremobile.com/2832022628717E276054_7104117490_107_1767713981_0",
        },
    }
    return _br_frame(0x05, reg, _pb(f), key, iv)


def br_join_team_pkt(code, region, client_version, key, iv):
    reg = str(region or "IND").upper()
    field9 = {1: _C_14_1, 2: 40, 3: _C_14_3, 4: "w\\Z]", 6: 12, 7: _C_14_7,
              8: client_version or "1.132.13", 9: 6, 10: 2, 11: _C_14_11}
    f = {1: 4, 2: {
        4: bytes.fromhex("01090a0b121619201d2729"),
        5: str(code), 6: 6, 8: 1,
        9: field9,
        11: _br_idc(reg, (99, 136)),
        13: "en", 16: bytes.fromhex("374f521955"),
        20: [{1: 3, 2: 360}, {1: 4, 2: 391}, {1: 5, 2: 156},
             {1: 29, 2: 204}, {1: 22, 2: 118}, {1: 14, 2: 139}, {1: 21}],
        27: {1: 2, 2: 4}}}
    return _br_frame(0x05, reg, _pb(f), key, iv)


def br_start_squad_pkt(uid, region, key, iv):
    reg = str(region or "IND").upper()
    return _br_frame(0x05, reg,
                     _pb({1: 9, 2: {1: int(uid), 7: _br_idc(reg)}}),
                     key, iv)


async def send_op31(group_id, region, key, iv):
    fields = {1: 31, 2: {1: int(group_id)}}
    pkt = f"05{region_byte(region):02x}"
    proto = _pb(fields)
    enc = AES.new(key, AES.MODE_CBC, iv).encrypt(pad(proto, 16)).hex()
    header = pkt + "0000" + enc
    enc_bytes = bytes.fromhex(enc)
    return bytes.fromhex(pkt) + len(enc_bytes).to_bytes(4, "big") + enc_bytes


def _decode_frame_payload(payload):
    if not HAS_PARSER:
        return None
    try:
        from protobuf_decoder.protobuf_decoder import Parser
        parsed = Parser().parse(payload.hex())
        decoded = {}
        for r in parsed:
            wt = r.wire_type
            if wt == "length_delimited":
                try:
                    sub = r.data.results
                    nested = {}
                    for sr in sub:
                        if sr.wire_type == "length_delimited":
                            try:
                                inner = sr.data.results
                                nested_inner = {}
                                for ir in inner:
                                    if ir.wire_type == "length_delimited":
                                        nested_inner[str(ir.field)] = {"data": "nested"}
                                    else:
                                        nested_inner[str(ir.field)] = {"data": ir.data}
                                nested[str(sr.field)] = nested_inner
                            except Exception:
                                nested[str(sr.field)] = {"data": str(sr.data)}
                        else:
                            nested[str(sr.field)] = {"data": sr.data}
                    decoded[str(r.field)] = nested
                except Exception:
                    decoded[str(r.field)] = {"data": str(r.data)}
            else:
                decoded[str(r.field)] = {"data": r.data}
        return decoded
    except Exception:
        return None


def _extract_team_code(decoded, master_id):
    if not isinstance(decoded, dict):
        return None
    candidates = []
    r5 = decoded.get("5")
    if isinstance(r5, dict):
        for k in ("1", "2", "3", "4", "5", "6", "11"):
            v = r5.get(k)
            if isinstance(v, dict):
                v = v.get("data")
            if isinstance(v, (str, int)):
                candidates.append(str(v))
    for k in ("1", "2", "3"):
        v = decoded.get(k)
        if isinstance(v, dict):
            v = v.get("data")
        if isinstance(v, (str, int)):
            candidates.append(str(v))
    for c in candidates:
        if not c or c == str(master_id):
            continue
        if c.isdigit() and len(c) >= 12 and c != str(master_id):
            continue
        return c
    for c in candidates:
        if c and c != str(master_id):
            return c
    return None


def _match_info_from_frame(ptype, cmd, decoded, payload=None):
    is_matchmaking = (ptype == 0x03 and cmd == 5)
    is_reconnect = (ptype == 0x11 and cmd == 3)
    if not (is_matchmaking or is_reconnect):
        return None

    def _extract(d):
        if not isinstance(d, dict):
            return None
        r5 = d.get("5") or d.get(5) or {}
        if not isinstance(r5, dict):
            return None
        ip_port = r5.get("2") or r5.get(2)
        udp_key = r5.get("3") or r5.get(3)
        token = r5.get("4") or r5.get(4)
        mcode = r5.get("42") or r5.get(42)
        if isinstance(ip_port, dict):
            ip_port = ip_port.get("data")
        if isinstance(udp_key, dict):
            udp_key = udp_key.get("data")
        if isinstance(token, dict):
            token = token.get("data")
        if isinstance(mcode, dict):
            mcode = mcode.get("data")
        if (isinstance(ip_port, str) and ":" in ip_port
                and isinstance(udp_key, str)
                and isinstance(token, str) and mcode is not None):
            r5_clean = dict(r5)
            r5_clean["2"] = ip_port
            r5_clean["3"] = udp_key
            r5_clean["4"] = token
            r5_clean["42"] = str(mcode)
            return r5_clean
        return None

    result = _extract(decoded)
    if result:
        return result

    if payload is not None:
        try:
            alt = parse_proto(payload)
            alt_norm = {}
            for k, vals in alt.items():
                for kind, v in vals:
                    if kind == "bytes":
                        try:
                            nested = parse_proto(bytes.fromhex(v))
                            alt_norm[str(k)] = {
                                str(nk): [{"data": nv} for _, nv in nv_list]
                                for nk, nv_list in nested.items()
                            }
                            break
                        except Exception:
                            pass
                    else:
                        alt_norm.setdefault(str(k), []).append({"data": v})
            return _extract(alt_norm)
        except Exception:
            pass
    return None


def _collect_all_ints(obj, out):
    if isinstance(obj, dict):
        if "data" in obj and isinstance(obj["data"], int):
            out.add(obj["data"])
        for v in obj.values():
            _collect_all_ints(v, out)
    elif isinstance(obj, list):
        for x in obj:
            _collect_all_ints(x, out)
    elif isinstance(obj, int):
        out.add(obj)


# ═══════════════ SLAVE LOOP ═══════════════
async def slave_loop(acct, holder, match_infos, stop_evt):
    tag = acct["tag"]
    region = acct.get("region", "IND")
    ip, port = acct["game_server"].split(":")
    key, iv = acct["key"], acct["iv"]
    jwt = acct["jwt"]
    ingame_id = int(acct["ingame_id"])
    ts = acct["ts"]
    auth_online = await build_auth_packet(ingame_id, jwt, ts, key, iv, region, "OnLine")
    ka_bytes = await send_keep_alive(region)
    remote_version = acct["cfg"].get("remote_version", _PLAY_VERSION)

    while not stop_evt.is_set():
        try:
            reader, writer = await asyncio.open_connection(ip, int(port))
            writer.write(auth_online)
            await writer.drain()
            writer.write(ka_bytes)
            await writer.drain()
            _log(f"Tcp Connected => {acct.get('name', tag)}")

            ka_stop = asyncio.Event()

            async def ka_loop():
                while not ka_stop.is_set():
                    try:
                        await asyncio.sleep(15)
                        writer.write(ka_bytes)
                        await writer.drain()
                    except Exception:
                        return

            ka_task = asyncio.create_task(ka_loop())

            try:
                await asyncio.wait_for(holder["team_code_ready"].wait(), 30)
            except asyncio.TimeoutError:
                ka_stop.set()
                ka_task.cancel()
                writer.close()
                continue

            team_code = holder["team_code"]
            j = br_join_team_pkt(team_code, region, remote_version, key, iv)
            writer.write(j)
            await writer.drain()

            joined = False
            join_sent_at = time.time()
            buf = bytearray()

            while not stop_evt.is_set():
                try:
                    chunk = await asyncio.wait_for(reader.read(65536), timeout=1.0)
                except asyncio.TimeoutError:
                    if not joined and time.time() - join_sent_at > 3:
                        joined = True
                        holder["slave_joined"].add(ingame_id)
                        print(f"  Bot Joined The Team => {acct.get('name', tag)}")
                    continue
                except Exception:
                    break
                if not chunk:
                    break
                buf.extend(chunk)
                while len(buf) >= 5:
                    ptype = buf[0]
                    plen = int.from_bytes(buf[1:5], "big")
                    if plen > 100_000 or len(buf) < 5 + plen:
                        break
                    payload = bytes(buf[5:5 + plen])
                    del buf[:5 + plen]
                    decoded = _decode_frame_payload(payload)
                    cmd = None
                    if isinstance(decoded, dict):
                        v = decoded.get("4")
                        if isinstance(v, dict):
                            v = v.get("data")
                        if isinstance(v, int):
                            cmd = v
                    if ptype == 0x05 and plen >= 200 and not joined:
                        joined = True
                        holder["slave_joined"].add(ingame_id)
                        print(f"  Bot Joined The Team => {acct.get('name', tag)}")
                    minfo = _match_info_from_frame(ptype, cmd, decoded, payload)
                    if minfo is not None and tag not in match_infos:
                        match_infos[tag] = minfo

            ka_stop.set()
            ka_task.cancel()
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            if stop_evt.is_set():
                break
        except Exception:
            await asyncio.sleep(2.0)


# ═══════════════ MASTER LOOP ═══════════════
async def master_loop(acct, slave_ids, holder, match_infos):
    tag = acct["tag"]
    region = acct.get("region", "IND")
    ip, port = acct["game_server"].split(":")
    key, iv = acct["key"], acct["iv"]
    jwt = acct["jwt"]
    ingame_id = int(acct["ingame_id"])
    ts = acct["ts"]
    slave_set = {int(x) for x in slave_ids}
    remote_version = acct["cfg"].get("remote_version", _PLAY_VERSION)
    
    auth_online = await build_auth_packet(ingame_id, jwt, ts, key, iv, region, "OnLine")
    ka_bytes = await send_keep_alive(region)

    reader, writer = await asyncio.open_connection(ip, int(port))
    writer.write(auth_online)
    await writer.drain()
    writer.write(ka_bytes)
    await writer.drain()
    _log(f"Tcp Connected => {acct.get('name', tag)}")

    ka_stop = asyncio.Event()

    async def ka_loop():
        while not ka_stop.is_set():
            try:
                await asyncio.sleep(15)
                writer.write(ka_bytes)
                await writer.drain()
            except Exception:
                return

    ka_task = asyncio.create_task(ka_loop())
    await asyncio.sleep(1.0)
    
    c = br_create_squad_pkt(region, remote_version, key, iv)
    writer.write(c)
    await writer.drain()
    print(f"  Team Created")

    created = False
    op31_sent = False
    buf = bytearray()

    async def start_watcher():
        try:
            await asyncio.wait_for(holder["team_code_ready"].wait(), 25)
        except asyncio.TimeoutError:
            return
        t0 = time.time()
        while time.time() - t0 < 25:
            if holder["slave_joined"] >= slave_set:
                break
            await asyncio.sleep(0.4)
        await asyncio.sleep(SETTLE_AFTER_ALL_JOIN)
        print(f"  Starting Match...")
        s = br_start_squad_pkt(ingame_id, region, key, iv)
        try:
            writer.write(s)
            await writer.drain()
        except Exception:
            return

    start_task = asyncio.create_task(start_watcher())

    try:
        while True:
            try:
                chunk = await asyncio.wait_for(reader.read(65536), timeout=30)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
            if not chunk:
                break
            buf.extend(chunk)
            while len(buf) >= 5:
                ptype = buf[0]
                plen = int.from_bytes(buf[1:5], "big")
                if plen > 100_000 or len(buf) < 5 + plen:
                    break
                payload = bytes(buf[5:5 + plen])
                del buf[:5 + plen]
                decoded = _decode_frame_payload(payload)
                cmd = None
                if isinstance(decoded, dict):
                    v = decoded.get("4")
                    if isinstance(v, dict):
                        v = v.get("data")
                    if isinstance(v, int):
                        cmd = v

                if ptype == 0x05 and isinstance(decoded, dict):
                    data = decoded.get("5", {})

                    if cmd == 1 and not created and plen >= 100:
                        gid = None
                        if isinstance(data, dict):
                            g = data.get("1")
                            if isinstance(g, dict):
                                g = g.get("data")
                            if isinstance(g, int):
                                gid = g
                        if gid is None:
                            gid = ingame_id
                        created = True
                        holder["group_id"] = gid

                    elif cmd == 32 and not holder["team_code"]:
                        tc_val = _extract_team_code(decoded, ingame_id)
                        if tc_val:
                            holder["team_code"] = tc_val
                            holder["team_code_ready"].set()
                            print(f"  Teamcode => {tc_val}")

                    if created and not op31_sent and holder["group_id"]:
                        op31_sent = True
                        try:
                            p31 = await send_op31(holder["group_id"], region, key, iv)
                            writer.write(p31)
                            await writer.drain()
                        except Exception:
                            pass

                    if cmd == 6:
                        found = set()
                        _collect_all_ints(decoded, found)
                        newj = found & slave_set
                        if newj:
                            holder["slave_joined"] |= newj

                    if cmd == 10:
                        print(f"  Match Started")

                minfo = _match_info_from_frame(ptype, cmd, decoded, payload)
                if minfo is not None and tag not in match_infos:
                    match_infos[tag] = minfo

    finally:
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass
        ka_stop.set()
        ka_task.cancel()
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


# ═══════════════ GUEST TOKEN & LOGIN ═══════════════
async def get_guest_token(uid, password, max_retries=6):
    import aiohttp
    url = "https://100067.connect.garena.com/oauth/guest/token/grant"
    versions = ['4.0.18P6', '4.0.19P7', '4.0.20P1', '4.1.0P3', '4.1.5P2', '4.2.1P8',
                '4.2.3P1', '5.0.1B2', '5.0.2P4', '5.1.0P1', '5.2.0B1', '5.2.5P3',
                '5.3.0B1', '5.3.2P2', '5.4.0P1', '5.4.3B2', '5.5.0P1', '5.5.2P3']
    models = ['SM-A125F', 'SM-A225F', 'SM-A325M', 'SM-A515F', 'SM-A725F',
              'SM-M215F', 'SM-M325FV', 'Redmi 9A', 'Redmi 9C', 'POCO M3',
              'POCO M4 Pro', 'RMX2185', 'RMX3085', 'moto g(9) play',
              'CPH2239', 'V2027', 'OnePlus Nord', 'ASUS_Z01QD']
    android_versions = ['9', '10', '11', '12', '13', '14']
    languages = ['en-US', 'bn-BD', 'hi-IN', 'id-ID', 'th-TH', 'vi-VN',
                 'ru-RU', 'es-MX', 'pt-BR']
    countries = ['IND', 'BGD', 'IDN', 'THA', 'VNM', 'RUS', 'MEX', 'BRA', 'USA']
    ua = (f"GarenaMSDK/{random.choice(versions)}({random.choice(models)};"
          f"Android {random.choice(android_versions)};"
          f"{random.choice(languages)};{random.choice(countries)};)")
    headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": ua,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close",
    }
    from core import _normalize_uid, SECRET
    data = {
        "uid": _normalize_uid(uid), "password": password,
        "response_type": "token", "client_type": "2",
        "client_secret": SECRET, "client_id": "100067",
    }
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=data) as r:
                    if r.status != 200:
                        last_err = f"HTTP {r.status}"
                        await asyncio.sleep(min(2.0 * attempt, 10.0))
                        continue
                    j = await r.json()
                    oid = j.get("open_id")
                    tok = j.get("access_token")
                    plat = j.get("platform", 4)
                    if oid and tok:
                        return oid, tok, int(plat or 4)
                    last_err = f"missing fields: {j}"
        except Exception as e:
            last_err = str(e)
        await asyncio.sleep(min(2.0 * attempt, 10.0))
    raise RuntimeError(f"guest token grant failed: {last_err}")


async def _try_login_with_region(rec, account_region, tag):
    uid = rec.get("uid")
    password = rec.get("pass") or rec.get("password")
    open_id = rec.get("open_id")
    access_token = rec.get("access_token")
    platform = rec.get("platform")

    # Pehli baar token check karo
    if not open_id or not access_token:
        open_id, access_token, platform = await get_guest_token(uid, password)
        rec["open_id"] = open_id
        rec["access_token"] = access_token
        rec["platform"] = platform
    platform = int(platform or 4)

    cfg_local = build_region_cfg(account_region)

    login = None
    last_err = None
    for attempt in range(1, 5):
        try:
            login = await asyncio.to_thread(
                major_login, tag, open_id, access_token, cfg_local,
                platform, account_region)
            break
        except Exception as e:
            last_err = e
            # Agar token expire ho gaya hai (parse failed / HTTP 400), toh naya token force lo
            if "parse failed" in str(e) or "HTTP" in str(e):
                print(f"  [!] Token expired for {tag}, refreshing...")
                try:
                    open_id, access_token, platform = await get_guest_token(uid, password)
                    rec["open_id"] = open_id
                    rec["access_token"] = access_token
                    rec["platform"] = platform
                    platform = int(platform or 4)
                    # Naye token ke saath turant retry karo
                    login = await asyncio.to_thread(
                        major_login, tag, open_id, access_token, cfg_local,
                        platform, account_region)
                    break
                except Exception as e2:
                    last_err = e2
            await asyncio.sleep(min(2.0 * attempt, 10.0))
            
    if login is None:
        raise RuntimeError(f"{tag} major_login gave up: {last_err}")

    payload = decode_jwt_payload(login["jwt"]) if login.get("jwt") else {}
    lock_reg = (payload.get("lock_region") or "").upper()

    if lock_reg and lock_reg != account_region:
        account_region = lock_reg
        cfg_local = build_region_cfg(lock_reg)
        login = await asyncio.to_thread(
            major_login, tag, open_id, access_token, cfg_local,
            platform, lock_reg)

    ld = await asyncio.to_thread(
        get_login_data, tag, open_id, access_token, cfg_local,
        platform, login["jwt"])
    
    return {
        "tag": tag, "uid": uid, "ingame_id": login["account_id"],
        "open_id": open_id, "access_token": access_token, "jwt": login["jwt"],
        "key": _to_bytes(login.get("aes_key") or b""),
        "iv": _to_bytes(login.get("aes_iv") or b""),
        "ts": login.get("server_time", 0),
        "game_server": ld["game_server"], "chat_server": ld["chat_server"],
        "server_url": login.get("game_url"), "name": rec.get("name", "?"),
        "cfg": cfg_local,
        "region": account_region,
    }


async def login_account(rec, cfg, tag):
    account_region = (rec.get("region") or "IND").upper()
    attempts = [account_region]
    for fallback in ("IND", "BD", "ME", "SG", "ID", "TH", "VN", "PK", "US", "BR"):
        if fallback not in attempts:
            attempts.append(fallback)
    last_err = None
    for reg in attempts:
        try:
            acct = await _try_login_with_region(rec, reg, tag)
            if reg != account_region:
                rec["region"] = reg
            return acct
        except Exception as e:
            last_err = e
            if "implausible result" in str(e) or "HTTP" in str(e):
                rec["open_id"] = None
                rec["access_token"] = None
                rec["platform"] = None
                continue
            raise
    raise RuntimeError(f"{tag} login failed for all regions: {last_err}")

# ═══════════════ SQUAD ORCHESTRATION ═══════════════
async def run_one_squad(batch, region_hint=None):
    if not batch:
        return False
    if region_hint:
        cfg = build_region_cfg(region_hint)
    else:
        cfg = build_region_cfg(batch[0].get("region", "IND"))

    logged_in = []
    for i, rec in enumerate(batch):
        tag = "[M]" if i == 0 else f"[S{i}]"
        try:
            acct = await login_account(rec, cfg, tag)
            acct["tag"] = tag
            logged_in.append(acct)
        except Exception as e:
            print(f"  X {tag} login failed: {e}")
        await asyncio.sleep(1.5)

    if len(logged_in) < 2:
        return False

    master = logged_in[0]
    slaves = logged_in[1:]
    slave_ids = [int(s["ingame_id"]) for s in slaves]
    squad_ids = [int(a["ingame_id"]) for a in logged_in]
    print(f"  Team Leader => {master.get('name', '?')}")

    holder = {
        "group_id": None,
        "team_code": None,
        "team_code_ready": asyncio.Event(),
        "slave_joined": set(),
        "master_id": None,
    }
    match_infos = {}
    slave_stop = asyncio.Event()
    slave_tasks = [asyncio.create_task(
        slave_loop(s, holder, match_infos, slave_stop)) for s in slaves]
    await asyncio.sleep(2.0)
    master_task = asyncio.create_task(
        master_loop(master, slave_ids, holder, match_infos))
        
    expected_tags = [a["tag"] for a in logged_in]
    deadline = time.time() + 180
    while time.time() < deadline:
        if all(t in match_infos for t in expected_tags):
            break
        await asyncio.sleep(0.5)
        
    missing = [t for t in expected_tags if t not in match_infos]
    if missing:
        slave_stop.set()
        for t in slave_tasks + [master_task]:
            t.cancel()
        await asyncio.gather(*(slave_tasks + [master_task]), return_exceptions=True)
        return False

    squad_done = {
        "event": asyncio.Event(),
        "count": 0,
        "total": len(logged_in),
        "started_at": time.time(),
    }
    udp_tasks = []
    for a in logged_in:
        r5 = match_infos[a["tag"]]
        server_ip_port = r5["2"]
        udp_key = r5["3"]
        join_token = r5["4"]
        match_code = r5["42"]
        real_match_id = r5.get("1") or 0
        real_map_id = r5.get("6") or 1
        real_game_mode = r5.get("7") or 15
        real_match_mode = r5.get("8") or 1
        real_sleep_ms = r5.get("5") or 0

        def _u(v):
            return v.get("data") if isinstance(v, dict) else v

        real_match_id = _u(real_match_id) or 0
        real_map_id = _u(real_map_id) or 1
        real_game_mode = _u(real_game_mode) or 15
        real_match_mode = _u(real_match_mode) or 1
        real_sleep_ms = _u(real_sleep_ms) or 0

        prepare_packets, post_packet = await build_join_match_startup(
            join_token, udp_key, match_code,
            int(a["ingame_id"]), real_match_id,
            server_ip=server_ip_port, region=a["region"],
            client_version=a["cfg"].get("remote_version", _PLAY_VERSION),
            client_version_code="2019121229",
            access_token=a["access_token"],
            match_id=real_match_id,
            country=a["region"],
            map_id=real_map_id,
            game_mode=real_game_mode,
            match_mode=real_match_mode,
        )
        udp_tasks.append(asyncio.create_task(play_game(
            server_ip_port, prepare_packets, post_packet, udp_key, match_code,
            int(a["ingame_id"]), a["region"],
            a["cfg"].get("remote_version", _PLAY_VERSION),
            tag=a["tag"],
            account_jwt=join_token,
            sleep_ms=real_sleep_ms,
            squad_done=squad_done,
        )))

    tcp_tasks = slave_tasks + [master_task]
    print(f"  Match Post")
    try:
        wait_task = asyncio.create_task(squad_done["event"].wait())
        all_udp = asyncio.gather(*udp_tasks, return_exceptions=True)
        
        done_set, pending = await asyncio.wait(
            [wait_task, all_udp],
            timeout=SQUAD_TIMEOUT,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not wait_task.done():
            wait_task.cancel()
            
        for task in udp_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*udp_tasks, return_exceptions=True)
    except Exception:
        pass
    finally:
        slave_stop.set()
        for t in tcp_tasks:
            t.cancel()
        await asyncio.gather(*tcp_tasks, return_exceptions=True)
    
    return True


async def run_squad_game(accounts, region_hint=None):
    try:
        with open(UDP_LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"# {datetime.now().isoformat()}\n")
    except Exception:
        pass
    if not accounts:
        return False

    total = len(accounts)
    batch_size = SQUAD_PLAYERS
    batches = [accounts[i:i + batch_size] for i in range(0, total, batch_size)]

    results = []

    async def run_batch(idx, batch):
        try:
            res = await run_one_squad(batch, region_hint=region_hint)
            results.append(res)
        except Exception:
            results.append(False)

    await asyncio.gather(*[run_batch(i, b) for i, b in enumerate(batches, 1)], return_exceptions=True)
    
    return True if any(results) else False


# ═══════════════ INTERACTIVE ENTRY ═══════════════
async def start_match_interactive():
    accounts = load_squad_accounts()
    print(f"  [DEBUG] squad_accounts: {len(accounts)}")
    if len(accounts) < 2:
        accounts = load_accounts()
        print(f"  [DEBUG] accs.txt loaded: {len(accounts)}")
    if len(accounts) < 2:
        print(f"  X Need at least 2 accounts (found {len(accounts)})")
        return
        
    # Ask region
    from core import REGION_LIST
    print(f"\n  Choose Match Region:")
    row = []
    for i, r in enumerate(REGION_LIST, 1):
        row.append(f"{i:>2}. {r}")
        if i % 3 == 0:
            print(f"      " + "      ".join(row))
            row = []
    if row:
        print(f"      " + "      ".join(row))

    try:
        raw = input("  > ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        return

    if raw.isdigit() and 1 <= int(raw) <= len(REGION_LIST):
        region_hint = REGION_LIST[int(raw) - 1]
    elif raw in REGION_LIST:
        region_hint = raw
    else:
        region_hint = None

    print(f"\n  Starting match in region: {region_hint or 'auto'}\n")
    await run_squad_game(accounts, region_hint=region_hint)