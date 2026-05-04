from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import time
import random

IV = b"\x42" * 16

ciphertext = open("secret.docx.enc", "rb").read()

def generate_key(seed):
    random.seed(seed)
    key = bytearray()
    for _ in range(32):
        key.append(random.randint(0, 255))
    return bytes(key)

start_time = int(time.time()) - 100000 
end_time   = int(time.time()) + 100000 

for seed in range(start_time, end_time):
    key = generate_key(seed)

    cipher = AES.new(key, AES.MODE_CBC, IV)
    try:
        plaintext = unpad(cipher.decrypt(ciphertext), 16)

        if plaintext.startswith(b'PK'):
            print("KEY FOUND:", key)
            open("recovered.docx", "wb").write(plaintext)
            break

    except:
        pass
