from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import hashlib

cipher_hex = "de6447b1a97cf46c83c2efcbd1da54e53eb48b4e440186e5d84408f2bb24799d2d3819d12b48837b04a662ae3ba1a0f7"   #<--- Pasted my Cipher-text i got by  entering B=1

ciphertext = bytes.fromhex(cipher_hex)

shared_secret = 1
key = hashlib.sha256(str(shared_secret).encode()).digest()[:16]

cipher = AES.new(key, AES.MODE_ECB)

plaintext = unpad(cipher.decrypt(ciphertext), 16)

print(plaintext.decode())
