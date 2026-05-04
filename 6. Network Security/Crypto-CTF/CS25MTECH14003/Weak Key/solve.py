from Crypto.Cipher import DES

CIPHER_HEX = "fabdb86979cd456171ed803f7dc91f131ff6f747f7be5beb83cda6c78483fdf5f1e6e5272683bb0e47ce5ae80d641098"


WEAK_KEYS = [
    "0101010101010101", "FEFEFEFEFEFEFEFE", "E0E0E0E0F1F1F1F1", "1F1F1F1F0E0E0E0E",
    "01FE01FE01FE01FE", "FE01FE01FE01FE01", "1FE01FE00EF10EF1", "E01FE01FF10EF10E",
    "01E001E001F101F1", "E001E001F101F101", "1FFE1FFE0EFE0EFE", "FE1FFE1FFE0EFE0E",
    "011F011F010E010E", "1F011F010E010E01", "E0FEE0FEF1FEF1FE", "FEE0FEE0FEF1FEF1"
]


def unpad(data: bytes) -> bytes | None:
    pad_len = data[-1]
    return data[:-pad_len] if all(b == pad_len for b in data[-pad_len:]) else None


def try_decrypt(cipher_bytes: bytes, key_hex: str) -> None:
    key = bytes.fromhex(key_hex)
    des = DES.new(key, DES.MODE_ECB)
    plaintext = unpad(des.decrypt(cipher_bytes))

    if plaintext is None:
        return

    try:
        print(f"KEY: {key_hex}")
        print(f"PLAINTEXT: {plaintext.decode()}")
    except UnicodeDecodeError:
        print(f"KEY: {key_hex}  RAW: {plaintext}")


def main() -> None:
    cipher_bytes = bytes.fromhex(CIPHER_HEX)
    for key_hex in WEAK_KEYS:
        try_decrypt(cipher_bytes, key_hex)


if __name__ == "__main__":
    main()
