import socket, re, time
from Crypto.Cipher import DES

SERVER_IP, SERVER_PORT = "192.168.51.76", 65003
ROLL_NO    = "cs25mtech14003"
BLOCK_SIZE = 8
KNOWN_HEAD = b"cs6903{"
ASCII_SET  = range(32, 127)

def build_key(n):
    return str(n).zfill(8).encode()[:8]

def strip_parity(n):
    return bytes(b & 0xFE for b in build_key(n))

def fetch_ciphertext():
    conn = socket.socket()
    conn.connect((SERVER_IP, SERVER_PORT))
    conn.settimeout(3)
    buf = b""
    conn.sendall(b"\n")
    time.sleep(0.5)
    conn.sendall(ROLL_NO.encode() + b"\n")
    time.sleep(1)
    try:
        while True: buf += conn.recv(4096)
    except: pass
    conn.close()
    match = re.search(r"Ciphertext.*?:\s*([0-9a-fA-F]{32,})", buf.decode(errors="ignore"))
    if not match: exit("No ciphertext found")
    return bytes.fromhex(match.group(1))

def build_keyspace():
    return list({strip_parity(k): k for k in range(10000, 100000)}.values())

def build_forward_table(keyspace):
    table = {}
    for k1 in keyspace:
        c = DES.new(build_key(k1), DES.MODE_ECB)
        for ch in ASCII_SET:
            table[c.encrypt(KNOWN_HEAD + bytes([ch]))] = (k1, ch)
    return table

def build_reverse_map(keyspace, first_block):
    return {k1: DES.new(build_key(k1), DES.MODE_ECB).decrypt(first_block) for k1 in keyspace}

def mitm_attack(keyspace, forward_table, reverse_map):
    for k2 in keyspace:
        c2 = DES.new(build_key(k2), DES.MODE_ECB)
        for k1, mid in reverse_map.items():
            if c2.encrypt(mid) in forward_table:
                final_k1, final_char = forward_table[c2.encrypt(mid)]
                return final_k1, k2, final_char
    return None, None, None

def decrypt_flag(cipher_bytes, k1, k2):
    c1 = DES.new(build_key(k1), DES.MODE_ECB)
    c2 = DES.new(build_key(k2), DES.MODE_ECB)
    return b"".join(
        c1.decrypt(c2.encrypt(c1.decrypt(cipher_bytes[i:i+8])))
        for i in range(0, len(cipher_bytes), 8)
    )

def main():
    cipher_bytes = fetch_ciphertext()
    first_block  = cipher_bytes[:BLOCK_SIZE]
    keyspace     = build_keyspace()
    forward_table = build_forward_table(keyspace)
    reverse_map   = build_reverse_map(keyspace, first_block)
    k1, k2, _     = mitm_attack(keyspace, forward_table, reverse_map)
    if not k1: exit("Attack failed")
    recovered = decrypt_flag(cipher_bytes, k1, k2)
    print("FLAG:", recovered.rstrip(b" ").decode(errors="replace"))

main()
