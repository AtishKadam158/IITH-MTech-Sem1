# Importing Required Library
import socket
import os
import threading
from datetime import datetime
import stat
import hashlib
import random
import struct


class FileManagementServer:
    def __init__(self, host='0.0.0.0', port=5555, files_directory='server_files'):
        self.host = host
        self.port = port
        self.files_directory = files_directory
        self.log_file = 'server.log'

        # Credential for authentication
        self.credentials = self.load_credentials("credentials.txt")

        #Logic for Locked users (When entered wrong credentails for more than 3 times in same session)
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
                    line = line.strip()
                    if ":" in line:
                        user, secret = line.split(":", 1)
                        creds[user.strip()] = secret.strip()
        except FileNotFoundError:
            print(f"[!] Warning: {filename} not found. Creating empty credentials.")
        return creds

    # Adding log message to server.log file and printing it on console
    def log_message(self, msg_type, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] {msg_type}: {message}"
        print(entry)
        with open(self.log_file, 'a') as f:
            f.write(entry + "\n")

    # AUTHENTICATION (Checking username and correspoding password) (Task -2 Specific Task)
    def authenticate_client(self, client_socket):
        failed_attempts = 0
        username = None

        while failed_attempts < 3:
            client_socket.send(b"USERNAME:")
            username = client_socket.recv(1024).decode().strip()

            print(f"[+] Username received: {username}")

            if not username:
                return False

            self.log_message("REQUEST", "USERNAME RECEIVED")

            if username in self.locked_users:
                self.log_message("RESPONSE", "ACCOUNT LOCKED")
                client_socket.send(b"ACCOUNT LOCKED")
                return False

            if username not in self.credentials:
                failed_attempts += 1
                self.log_message("RESPONSE", "AUTH FAILED")
                client_socket.send(b"AUTH FAILED")
                continue

            nonce = str(random.randint(100000, 999999))
            print(f"[+] Generated Nonce for {username}: {nonce}")

            client_socket.send((nonce + "\n").encode())

            response = client_socket.recv(1024).decode().strip()
            print(f"[+] Client Hash Response: {response}")

            if not response:
                return False

            expected = hashlib.sha256(
                (nonce + self.credentials[username]).encode()
            ).hexdigest()

            print(f"[+] Expected Hash: {expected}")

            if response == expected:
                self.log_message("RESPONSE", "AUTH SUCCESS")
                client_socket.send(b"AUTH SUCCESS")
                return True

            failed_attempts += 1
            self.log_message("RESPONSE", "AUTH FAILED")
            client_socket.send(b"AUTH FAILED")

        self.locked_users.add(username)
        self.log_message("RESPONSE", "ACCOUNT LOCKED")
        client_socket.send(b"ACCOUNT LOCKED")
        return False

    # # Diffie hellman  (Task -2 Specific Task)
    def diffie_hellman(self, client_socket, client_address):
        p = int(os.environ["P"])
        g = int(os.environ["G"])

        b = random.randint(2, p - 2)
        B = pow(g, b, p)

        print(f"[+] Server Public Value (B): {B}")

        client_socket.send(str(B).encode())
        A = int(client_socket.recv(1024).decode())

        print(f"[+] Client Public Value (A): {A}")

        shared_key = pow(A, b, p)

        # Derive session key (BYTES)
        session_key = hashlib.sha256(str(shared_key).encode()).digest()

        self.session_keys[client_address] = session_key

        
        print(f"[+] Session key established with {client_address}: shared key - {shared_key}")


    # Listing all files in server_file folder
    def handle_list(self):
        try:
            files = [
                f for f in os.listdir(self.files_directory)
                if os.path.isfile(os.path.join(self.files_directory, f))
            ]
            return " ".join(files) if files else "No files found"
        except Exception as e:
            return f"ERROR: {str(e)}"
        
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
        path = os.path.join(self.files_directory, filename)

        # Check weather file exists or not 
        if not os.path.isfile(path):
            client_socket.send(b"FILE NOT AVAILABLE")
            self.log_message("RESPONSE", f"FILE NOT AVAILABLE: {filename}")
            return

        # Now -> Get session key
        session_key = self.session_keys.get(client_address)
        if session_key is None:
            client_socket.send(b"ERROR: NO SESSION KEY")
            self.log_message("RESPONSE", "ERROR: NO SESSION KEY")
            return

        # Send file size
        file_size = os.path.getsize(path)
        client_socket.send(f"FILE_SIZE:{file_size}".encode())
        self.log_message("RESPONSE", f"FILE_SIZE: {file_size}")

        # Wait for client ready signal
        ready = client_socket.recv(1024).decode().strip()
        if ready != "READY":
            self.log_message("REQUEST", f"Client not ready: {ready}")
            return

        seq_no = 0
        CHUNK_SIZE = 1024
        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        print(f"[*] Sending file {filename} ({file_size} bytes, {total_chunks} chunks)")

        try:
            with open(path, 'rb') as f:
                while True:
                    data = f.read(CHUNK_SIZE)
                    if not data:
                        break
                    mac_input = data + struct.pack("!I", seq_no) + session_key
                    mac = hashlib.sha256(mac_input).digest()

                    packet = struct.pack("!I", seq_no) + data + mac

                    client_socket.sendall(packet)

                    ack = client_socket.recv(1024).decode().strip()
                    if ack != f"ACK:{seq_no}":
                        self.log_message("RESPONSE", f"TRANSFER FAILED - Invalid ACK at chunk {seq_no}")
                        return

                    seq_no += 1

            client_socket.send(b"TRANSFER_COMPLETE")
            self.log_message("RESPONSE", f"FILE {filename} SENT SUCCESSFULLY ({seq_no} chunks)")
            print(f"[+] File transfer complete: {filename}")

        except Exception as e:
            error_msg = f"ERROR: Transfer failed - {str(e)}"
            client_socket.send(error_msg.encode())
            self.log_message("RESPONSE", error_msg)
            print(f"[!] Transfer error: {e}")

    
    # We suport three commands LIST, INFO <filename>, GETSIZE <filename> and QUIT 
    # This Function calls those function which is required
    def process_command(self, command, client_socket, client_address):
        parts = command.split(maxsplit=1)
        if not parts:
            return "ERROR: EMPTY COMMAND"
        cmd = parts[0].upper()

        if cmd == "LIST":
            return self.handle_list()
        elif cmd == "INFO" and len(parts) == 2:
            return self.handle_info(parts[1])
        elif cmd == "GETSIZE" and len(parts) == 2:
            return self.handle_getsize(parts[1])
        elif cmd == "GET" and len(parts) == 2:
            # GET command handles its own response (Task - 3 Specific)
            self.handle_get(parts[1], client_socket, client_address)
            return None
        elif cmd == "QUIT":
            return "QUIT"
        else:
            return "ERROR: INVALID COMMAND"

    # Server get request and provide resopnse and add log to server.log file
    def handle_client(self, client_socket, client_address):
        print(f"[+] New connection from {client_address}")
        
        try:
            username = self.authenticate_client(client_socket)
            if not username:
                print(f"[-] Authentication failed for {client_address}")
                client_socket.close()
                return

            print(f"[+] User {username} authenticated from {client_address}")

            self.diffie_hellman(client_socket, client_address)

            while True:
                data = client_socket.recv(4096).decode().strip()
                if not data:
                    break

                self.log_message("REQUEST", data)
                response = self.process_command(data, client_socket, client_address)

                if response:
                    self.log_message("RESPONSE", response)
                    client_socket.send(response.encode())
                    if response == "QUIT":
                        break

        except Exception as e:
            print(f"[!] Error handling client {client_address}: {e}")
        finally:
            # Cleanup
            self.session_keys.pop(client_address, None)
            client_socket.close()
            print(f"[-] Connection closed: {client_address}")

   
    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)

        print(f"[*] Server listening....")

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
    if "P" not in os.environ:
        os.environ["P"] = "23"
    if "G" not in os.environ:
        os.environ["G"] = "5"
    
    server = FileManagementServer()
    server.start()