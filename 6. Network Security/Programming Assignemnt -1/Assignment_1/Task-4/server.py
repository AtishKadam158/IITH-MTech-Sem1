# Importing Required Library
import socket
import os
import threading
from datetime import datetime
import stat
import hashlib
import random
import struct
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Constants for AES (Task -4 Specifically)
AES_BLOCK_SIZE = 16

class FileManagementServer:
    def __init__(self, host='0.0.0.0', port=5555, files_directory='server_files'):
        self.host = host
        self.port = port
        self.files_directory = files_directory
        self.log_file = 'server.log'
        self.credentials = self.load_credentials("credentials.txt")

        self.lock = threading.Lock()
        self.locked_users = set()
        self.session_keys = {} 

        if not os.path.exists(self.files_directory):
            os.makedirs(self.files_directory)

    # Loading username and password (Task -2 Specific Task)
    def load_credentials(self, filename):
        creds = {}
        try:
            with open(filename, 'r') as f:
                for line in f:
                    if ":" in line:
                        user, secret = line.strip().split(":", 1)
                        creds[user.strip()] = secret.strip()
        except FileNotFoundError:
            print(f"[!] Warning: {filename} not found.")
            return {"alice": "qwertyuiop"} 
        return creds
    
    # Adding log message to server.log file and printing it on console
    def log_message(self, msg_type, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] {msg_type}: {message}"
        print(entry)
        with open(self.log_file, 'a') as f:
            f.write(entry + "\n")

    # Using AES for encryption and decryption (Task -4 Specific Task)
    # Doing t for key
    def derive_aes_key(self, session_key):
        return hashlib.sha256(session_key).digest()[:16]
    
    #Securing Payload by AES
    def encrypt_payload(self, plain_text, aes_key):
        iv = os.urandom(16)
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        encrypted = cipher.encrypt(pad(plain_text.encode(), AES_BLOCK_SIZE))
        return iv + encrypted

    # Decrypting Payload by AES
    def decrypt_payload(self, cipher_text, aes_key):
        try:
            iv = cipher_text[:16]
            encrypted_data = cipher_text[16:]
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            return unpad(cipher.decrypt(encrypted_data), AES_BLOCK_SIZE).decode()
        except Exception as e:
            return None

    # AUTHENTICATION (Checking username and correspoding password) (Task -2 Specific Task)
    def authenticate_client(self, client_socket):
        failed_attempts = 0
        username = None

        while failed_attempts < 3:
            try:
                client_socket.send(b"USERNAME:")
                username = client_socket.recv(1024).decode().strip()
                if not username: return None

                self.log_message("REQUEST", f"USERNAME {username}")

                with self.lock:
                    if username in self.locked_users:
                        client_socket.send(b"ACCOUNT LOCKED")
                        self.log_message("RESPONSE", "ACCOUNT LOCKED")
                        return None

                if username not in self.credentials:
                    failed_attempts += 1
                    client_socket.send(b"AUTH FAILED")
                    continue

                nonce = str(random.randint(100000, 999999))
                print(f"[+] Generated Nonce for {username}: {nonce}")
                client_socket.send(nonce.encode())
                
                response = client_socket.recv(1024).decode().strip()
                print(f"[+] Client Hash Response: {response}")
                expected = hashlib.sha256((nonce + self.credentials[username]).encode()).hexdigest()
                print(f"[+] Expected Hash: {expected}")

                if response == expected:
                    client_socket.send(b"AUTH SUCCESS")
                    self.log_message("RESPONSE", f"AUTH SUCCESS for {username}")
                    return username

                failed_attempts += 1
                client_socket.send(b"AUTH FAILED")
                self.log_message("RESPONSE", f"AUTH FAILED (Attempt {failed_attempts})")

            except Exception as e:
                print(f"[!] Auth error: {e}")
                return None

        with self.lock:
            self.locked_users.add(username)
        client_socket.send(b"ACCOUNT LOCKED")
        return None

    # # Diffie hellman  (Task -2 Specific Task)
    def diffie_hellman(self, client_socket, client_address):
        p = int(os.environ.get("P", "23"))
        g = int(os.environ.get("G", "5"))
        b = random.randint(2, p - 2)
        B = pow(g, b, p)

        client_socket.send(str(B).encode())
        A_str = client_socket.recv(1024).decode().strip()
        
        if not A_str.isdigit(): return
        
        A = int(A_str)
        shared_secret = pow(A, b, p)
        
        session_key = hashlib.sha256(str(shared_secret).encode()).digest()
        
        aes_key = self.derive_aes_key(session_key)
        print(f"[+] Server Public Value (B): {B}")
        print(f"[+] Client Public Value (A): {A}")
        self.session_keys[client_address] = (session_key, aes_key)
        self.log_message("SYSTEM", f"Session & AES keys established with {client_address}shared key - {shared_secret}")
    
    # Listing all files in server_file folder
    def handle_list(self):
        try:
            files = [f for f in os.listdir(self.files_directory) if os.path.isfile(os.path.join(self.files_directory, f))]
            return " ".join(files) if files else "No files found"
        except Exception as e: return f"ERROR: {str(e)}"

    # Info about required file  
    def handle_info(self, filename):
        path = os.path.join(self.files_directory, filename)
        if not os.path.isfile(path):
            return "ERROR: File not found"

        try:
            stats = os.stat(path)
            return (
                f"Last Modified: {datetime.fromtimestamp(stats.st_mtime)}, "
                f"Created: {datetime.fromtimestamp(stats.st_ctime)}, "
                f"Permissions: {stat.filemode(stats.st_mode)}"
            )
        except Exception as e:
            return f"ERROR: {str(e)}"


    # Getting size of required file
    def handle_getsize(self, filename):
        """Return size of specified file in bytes"""
        path = os.path.join(self.files_directory, filename)
        if not os.path.isfile(path):
            return "ERROR: File not found"
        
        try:
            return f"{os.path.getsize(path)} bytes"
        except Exception as e:
            return f"ERROR: {str(e)}"

    # Introduced New Command for requesting file from server and download that file (Task -3 Specific Task)
    def handle_get(self, filename, client_socket, client_address):
        path = os.path.join(self.files_directory, os.path.basename(filename))
        keys = self.session_keys.get(client_address)
        if not keys: return
        session_key, aes_key = keys

        # Send File Size or Error (Encrypted)
        if not os.path.isfile(path):
            client_socket.send(self.encrypt_payload("FILE NOT AVAILABLE", aes_key))
            self.log_message("RESPONSE", f"FILE NOT AVAILABLE: {filename}")
            return

        file_size = os.path.getsize(path)
        client_socket.send(self.encrypt_payload(f"FILE_SIZE:{file_size}", aes_key))
        self.log_message("RESPONSE", f"FILE_SIZE: {file_size}")

        # Wait for READY (Encrypted)
        encrypted_ready = client_socket.recv(1024)
        ready = self.decrypt_payload(encrypted_ready, aes_key)
        if ready != "READY": return

        seq_no = 0
        CHUNK_SIZE = 1024
        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE
        print(f"[*] Sending file {filename} ({file_size} bytes, {total_chunks} chunks)")

        try:
            with open(path, 'rb') as f:
                while True:
                    data = f.read(CHUNK_SIZE)
                    if not data: break

                    iv = os.urandom(16)
                    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
                    enc_data = iv + cipher.encrypt(pad(data, AES_BLOCK_SIZE))

                    mac_input = enc_data + struct.pack("!I", seq_no) + session_key
                    mac = hashlib.sha256(mac_input).digest()

                    payload = struct.pack("!I", seq_no) + enc_data + mac
        
                    client_socket.sendall(struct.pack("!I", len(payload)) + payload)

                    enc_ack = client_socket.recv(1024)
                    ack = self.decrypt_payload(enc_ack, aes_key)
                    if ack != f"ACK:{seq_no}":
                        self.log_message("ERROR", f"Invalid ACK {seq_no}")
                        return
                    seq_no += 1

            client_socket.sendall(struct.pack("!I", 0))
            self.log_message("RESPONSE", f"File {filename} sent successfully.")
            print(f"[+] File transfer complete: {filename}")

        except Exception as e:
            error_msg = f"ERROR: Transfer failed - {str(e)}"
            client_socket.send(self.encrypt_payload(error_msg, aes_key))
            self.log_message("RESPONSE", error_msg)
            print(f"[!] Transfer error: {e}")

    # We suport three commands LIST, INFO <filename>, GETSIZE <filename> and QUIT 
    # This Function calls those function which is required
    def process_command(self, command, client_socket, client_address):
        parts = command.split(maxsplit=1)
        if not parts: return "ERROR: EMPTY COMMAND"
        cmd = parts[0].upper()

        if cmd == "LIST": return self.handle_list()
        elif cmd == "INFO" and len(parts) == 2: return self.handle_info(parts[1])
        elif cmd == "GETSIZE" and len(parts) == 2: return self.handle_getsize(parts[1])
        elif cmd == "GET" and len(parts) == 2:
            self.handle_get(parts[1], client_socket, client_address)
            return None # GET handles its own response
        elif cmd == "QUIT": return "QUIT"
        else: return "ERROR: INVALID COMMAND"

    # Server get request and provide resopnse and add log to server.log file
    def handle_client(self, client_socket, client_address):
        print(f"[+] New connection from {client_address}")
        
        try:
            # 1. Authenticate (Plaintext)
            username = self.authenticate_client(client_socket)
            print(f"[+] User {username} authenticated from {client_address}")
            if not username:
                client_socket.close()
                return

            # 2. Diffie-Hellman & Key Gen
            self.diffie_hellman(client_socket, client_address)
            
            keys = self.session_keys.get(client_address)
            if not keys: return
            session_key, aes_key = keys

            # 3. Encrypted Loop
            while True:
                encrypted_cmd = client_socket.recv(4096)
                if not encrypted_cmd: break
                
                # Decrypt
                command = self.decrypt_payload(encrypted_cmd, aes_key)
                if not command: break
                
                self.log_message("REQUEST", f"[Encrypted] {command}")

                # Process
                response = self.process_command(command, client_socket, client_address)

                # Encrypt Response
                if response:
                    if response == "QUIT": break
                    
                    self.log_message("RESPONSE", f"[Encrypted] {response}")
                    client_socket.send(self.encrypt_payload(response, aes_key))

        except Exception as e:
            print(f"[!] Error: {e}")
        finally:
            self.session_keys.pop(client_address, None)
            client_socket.close()
            print(f"[-] Connection closed: {client_address}")

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        print(f"[*] Server running on...")

        try:
            while True:
                client_socket, client_address = server_socket.accept()
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                client_thread.start()
        except KeyboardInterrupt:
            print("\n[*] Server shutting down...")
        finally:
            server_socket.close()

if __name__ == "__main__":
    FileManagementServer().start()