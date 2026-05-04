import socket

HOST_ADDR = '192.168.51.76'
PORT_NUM = 65001
AUTH_ID = b'cs25mtech14003\n'
BS = 16

class PaddingOracle:
    def __init__(self, host, port):
        self.s = socket.create_connection((host, port))

    def _read(self, delimiter):
        data = b''
        while not data.endswith(delimiter):
            char = self.s.recv(1)
            if not char: break
            data += char
        return data

    def get_target(self):
        self._read(b'Student ID: ')
        self.s.sendall(AUTH_ID)
        self._read(b'Ciphertext (hex): ')
        hex_str = self._read(b'\n').strip().decode()
        return bytes.fromhex(hex_str)

    def test_payload(self, payload):
        self._read(b'Send ciphertext (hex): ')
        self.s.sendall(payload.hex().encode() + b'\n')
        return self._read(b'\n').strip() == b'VALID'

    def solve_block(self, prev, target, last):
        inter = bytearray(BS)
        plain = bytearray(BS)
        
        chars = [ord(c) for c in 'cs69{}0123456789abcdef']
        search_space = chars + [b for b in range(256) if b not in chars]

        for i in range(BS - 1, -1, -1):
            pad_val = BS - i
            modified = bytearray(prev)
            
            for k in range(i + 1, BS):
                modified[k] = inter[k] ^ pad_val
            
            for g in search_space:
                modified[i] = prev[i] ^ g ^ pad_val
                if self.test_payload(bytes(modified) + target):
                    if i == 15 and last and g == 1:
                        modified[14] ^= 0x01
                        if not self.test_payload(bytes(modified) + target):
                            continue
                    
                    plain[i] = g
                    inter[i] = modified[i] ^ pad_val
                    print(f"Byte {i:02}: {chr(g) if 32 <= g <= 126 else hex(g)}")
                    break
        return plain

    def run_attack(self):
        ct = self.get_target()
        chunks = [ct[i:i+BS] for i in range(0, len(ct), BS)]
        output = b''

        for n in range(1, len(chunks)):
            print(f"\nTargeting Block {n}...")
            p = self.solve_block(chunks[n-1], chunks[n], n == len(chunks)-1)
            output += p
            print(f"Result: {p}")

        pad = output[-1]
        print(f"\nFLAG: {output[:-pad].decode('utf-8', errors='ignore')}")

if __name__ == "__main__":
    attacker = PaddingOracle(HOST_ADDR, PORT_NUM)
    attacker.run_attack()
