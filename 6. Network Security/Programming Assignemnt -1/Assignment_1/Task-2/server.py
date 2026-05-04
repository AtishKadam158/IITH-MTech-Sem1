# Importing Required Library
import socket
import os
import threading
from datetime import datetime
import stat
import hashlib
import random


class FileManagementServer:
    def __init__(self, host='0.0.0.0', port=5555, files_directory='server_files'):
        self.host = host
        self.port = port
        self.files_directory = files_directory
        self.log_file = 'server.log'
        # Credential for authentication
        self.credentials = self.load_credentials("credentials.txt")

        # Logic for Locked users (When entered wrong credentails for more than 3 times in same session)
        self.locked_users = set()

        self.session_keys = {}

        if not os.path.exists(self.files_directory):
            os.makedirs(self.files_directory)

    # Loading username and password (Task -2 Specific Task)
    def load_credentials(self, filename):
        creds = {}
        with open(filename, 'r') as f:
            for line in f:
                if ":" in line:
                    user, secret = line.strip().split(":", 1)
                    creds[user] = secret
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

    # Diffie hellman  (Task -2 Specific Task)
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
        self.session_keys[client_address] = shared_key
        print(f"[+] Session key established with {client_address}: {shared_key}")

    # Listing all files in server_file folder
    def handle_list(self):
        files = [
            f for f in os.listdir(self.files_directory)
            if os.path.isfile(os.path.join(self.files_directory, f))
        ]
        return ", ".join(files) if files else "No files found"

    # Info about required file
    def handle_info(self, filename):
        path = os.path.join(self.files_directory, filename)
        if not os.path.isfile(path):
            return "ERROR: File not found"

        stats = os.stat(path)
        return (
            f"Last Modified: {datetime.fromtimestamp(stats.st_mtime)}, "
            f"Created: {datetime.fromtimestamp(stats.st_ctime)}, "
            f"Permissions: {stat.filemode(stats.st_mode)}"
        )

    # Getting size of required file
    def handle_getsize(self, filename):
        path = os.path.join(self.files_directory, filename)
        if not os.path.isfile(path):
            return "ERROR: File not found"
        return f"{os.path.getsize(path)} bytes"

    # We suport three commands LIST, INFO <filename>, GETSIZE <filename> and QUIT
    # This Function calls those function which is required
    def process_command(self, command):
        parts = command.split(maxsplit=1)
        cmd = parts[0].upper()

        if cmd == "LIST":
            return self.handle_list()
        elif cmd == "INFO" and len(parts) == 2:
            return self.handle_info(parts[1])
        elif cmd == "GETSIZE" and len(parts) == 2:
            return self.handle_getsize(parts[1])
        elif cmd == "QUIT":
            return "QUIT"
        else:
            return "ERROR: Invalid command"

    # Server get request and provide resopnse and add log to server.log file
    def handle_client(self, client_socket, client_address):
        try:
            if not self.authenticate_client(client_socket):
                client_socket.close()
                return

            self.diffie_hellman(client_socket, client_address)

            while True:
                data = client_socket.recv(4096).decode().strip()
                if not data:
                    break

                self.log_message("REQUEST", data)
                response = self.process_command(data)
                self.log_message("RESPONSE", response)

                if response == "QUIT":
                    break

                client_socket.send(response.encode())

        finally:
            self.session_keys.pop(client_address, None)
            client_socket.close()

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)

        print("[*] Server listening...")

        try:
            while True:
                client_socket, client_address = server_socket.accept()

                print(f"[+] New connection from {client_address[0]}:{client_address[1]}")

                threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                ).start()

        except KeyboardInterrupt:
            print("\n[!] Server shutting down...")

        finally:
            server_socket.close()


if __name__ == "__main__":
    FileManagementServer().start()
