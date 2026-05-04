import socket
import hashlib
import random
import os
import struct
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

CHUNK_SIZE = 1024
AES_BLOCK_SIZE = 16

class FileManagementClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        self.session_key = None
        self.aes_key = None

    # Deriving AES for Keys
    def derive_aes_key(self, session_key):
        return hashlib.sha256(session_key).digest()[:16]

    # We are encrypting the payload
    def encrypt_payload(self, plain_text):
        iv = os.urandom(16)
        cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
        return iv + cipher.encrypt(pad(plain_text.encode(), AES_BLOCK_SIZE))

    # We are decrypting the payload 
    def decrypt_payload(self, cipher_text):
        try:
            iv = cipher_text[:16]
            encrypted_data = cipher_text[16:]
            cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
            return unpad(cipher.decrypt(encrypted_data), AES_BLOCK_SIZE).decode()
        except Exception as e:
            return f"<Decryption Error: {e}>"

    def recv_exact(self, n):
        data = b""
        while len(data) < n:
            packet = self.socket.recv(n - len(data))
            if not packet: raise ConnectionError("Connection closed")
            data += packet
        return data

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"[+] Connected to {self.host}:{self.port}")
            
            # Authentication logic
            attempts = 0
            while attempts < 3:
                msg = self.socket.recv(1024).decode().strip()
                if msg == "USERNAME:":
                    username = input("Username: ").strip()
                    self.socket.send(username.encode())
                elif msg == "AUTH SUCCESS":
                    print("[+] Authentication successful")
                    break
                elif msg == "ACCOUNT LOCKED":
                    print("[-] Account locked")
                    return False
                elif msg == "AUTH FAILED":
                    print("[-] AUTH FAILED")
                    attempts += 1
                else:
                    nonce = msg
                    secret = input("Shared Secret: ").strip()
                    response = hashlib.sha256((nonce + secret).encode()).hexdigest()
                    self.socket.send(response.encode())

            if attempts == 3: return False

            # Diffi Hellman
            p = int(os.environ.get("P", "23"))
            g = int(os.environ.get("G", "5"))
            a = random.randint(2, p - 2)
            A = pow(g, a, p)

            B = int(self.socket.recv(1024).decode())
            self.socket.send(str(A).encode())

            shared_secret = pow(B, a, p)
            self.session_key = hashlib.sha256(str(shared_secret).encode()).digest()
            self.aes_key = self.derive_aes_key(self.session_key)
            print("[+] Session Key & AES Key established")
            return True
            
        except Exception as e:
            print(f"[-] Connection error: {e}")
            return False

    # Logic for downloading from server side
    def download_file(self, filename):
        encrypted_header = self.socket.recv(4096)
        
        header = self.decrypt_payload(encrypted_header)

        if "FILE NOT AVAILABLE" in header:
            print(f"[!] Server: {header}")
            return

        if not header.startswith("FILE_SIZE:"):
            print("[!] Invalid Header")
            return

        file_size = int(header.split(":")[1])
        print(f"[*] File Size: {file_size} bytes")
        
        self.socket.send(self.encrypt_payload("READY"))

        expected_seq = 0
        output_file = "downloaded_" + filename
        
        print(f"[*] Downloading to: {output_file}")
        print("-" * 50)

        with open(output_file, "wb") as f:
            while True:
                try:
                    len_bytes = self.recv_exact(4)
                    packet_len = struct.unpack("!I", len_bytes)[0]

                    if packet_len == 0:
                        print("-" * 50)
                        print("[✓] Transfer Complete.")
                        print(f"[*] Total chunks received: {expected_seq}")
                        break

                    packet = self.recv_exact(packet_len)

                    seq_bytes = packet[:4]
                    seq_no = struct.unpack("!I", seq_bytes)[0]
                    mac_received = packet[-32:]
                    enc_data = packet[4:-32]
                    
                    print(f"\n[*] Chunk {seq_no}:")
                    print(f"\n[Cipher]: {enc_data.hex()}\n")

                    mac_calc = hashlib.sha256(enc_data + seq_bytes + self.session_key).digest()
                    if mac_calc != mac_received:
                        print(f"[!] Integrity Check Failed at Block {seq_no}")
                        return

                    if seq_no != expected_seq:
                        print(f"[!] Sequence error: Expected {expected_seq}, got {seq_no}")
                        return

                    iv = enc_data[:16]
                    ciphertext = enc_data[16:]
                    cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
                    plaintext_chunk = unpad(cipher.decrypt(ciphertext), AES_BLOCK_SIZE)

                    try:
                        print(f"[Plain]: {plaintext_chunk.decode()}")
                    except:
                        print(f"[Plain]: <Binary Data: {len(plaintext_chunk)} bytes>")

                    f.write(plaintext_chunk)
                    
                    self.socket.send(self.encrypt_payload(f"ACK:{seq_no}"))
                    expected_seq += 1

                except Exception as e:
                    print(f"\n[!] Download Error: {e}")
                    break

    def run(self):
        if not self.connect(): return
        try:
            while True:
                command = input("\n> ").strip()
                if not command: continue
                
                cmd_parts = command.split(maxsplit=1)
                
                self.socket.send(self.encrypt_payload(command))
                
                if cmd_parts[0].upper() == "GET" and len(cmd_parts) > 1:
                    self.download_file(cmd_parts[1])
                elif command.upper() == "QUIT":
                    break
                else:
                    encrypted_response = self.socket.recv(4096)
                    print(f"[Cipher]: {encrypted_response.hex()}")
                    print(f"[Plain]: {self.decrypt_payload(encrypted_response)}")

        except KeyboardInterrupt:
            print("\n[*] Exiting...")
        finally:
            if self.socket: self.socket.close()
            print("[*] Connection closed")

if __name__ == "__main__":
    server_ip = input("Enter Server IP: ").strip()
    if not server_ip: server_ip = "127.0.0.1"
    FileManagementClient(server_ip).run()