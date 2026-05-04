import binascii

cipher_hex = "4a1d3f1875ce9abc18583a11239e84e84d5f3f1423cf83ed1d5f381075c587e94b5d39187d9980a0"
ciphertext = binascii.unhexlify(cipher_hex)

known_prefix = b"cs6903{"

partial_key = bytes([c ^ p for c, p in zip(ciphertext[:7], known_prefix)])

for last_byte in range(256):
    key = partial_key + bytes([last_byte])
    full_key = (key * (len(ciphertext) // len(key) + 1))[:len(ciphertext)]
    plaintext = bytes([c ^ k for c, k in zip(ciphertext, full_key)])
    try:
        decoded = plaintext.decode()
        if decoded.startswith("cs6903{") and decoded.endswith("}"):
            print("FLAG:", decoded)
            break
    except:
        pass
