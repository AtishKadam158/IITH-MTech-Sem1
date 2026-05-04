import base64
from Crypto.Util.Padding import unpad
from Crypto.Cipher import AES

def decrypt_flag():
    b64_key = "mMFmx8Mq9c02l35ftfAj2w=="
    b64_iv  = "dP0iOzhqWFDfbJy5rI9ywA=="
    b64_ct  = "DqE8yl5dwkPkPhXt0MIa4i5IvHVpDiOM1osy6mG/bFBRW+ICcSUomGKa5mlCFps9"

    raw_key = base64.b64decode(b64_key)
    raw_iv  = base64.b64decode(b64_iv)
    raw_ct  = base64.b64decode(b64_ct)

    try:
        aes = AES.new(raw_key, AES.MODE_CBC, raw_iv)
        result = unpad(aes.decrypt(raw_ct), AES.block_size)
        print("\n[+] Flag : ", result.decode("utf-8"), "\n")
    except Exception as err:
        print("\n[-] Decryption failed:", err)

if __name__ == "__main__":
    decrypt_flag()
