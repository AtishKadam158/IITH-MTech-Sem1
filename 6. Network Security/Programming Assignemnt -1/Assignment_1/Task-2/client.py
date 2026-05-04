# Importing required Modules
import socket
import hashlib
import random
import os


class FileManagementClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        self.session_key = None

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"[+] Connected to {self.host}:{self.port}")

            # Logic for allowing three times if enter wrong credentials (Task - 2 Specific Task)
            attempts = 0
            while attempts < 3:
                msg = self.socket.recv(1024).decode().strip()
                if msg != "USERNAME:":
                    print("[-] Protocol error")
                    return False

                username = input("Username: ").strip()
                self.socket.send(username.encode())

                nonce = self.socket.recv(1024).decode().strip()
                if nonce == "ACCOUNT LOCKED":
                    print("[-] Account locked")
                    return False

                secret = input("Shared Secret: ").strip()
                response = hashlib.sha256((nonce + secret).encode()).hexdigest()
                self.socket.send(response.encode())

                result = self.socket.recv(1024).decode().strip()

                if result == "AUTH SUCCESS":
                    print("[+] Authentication successful")
                    break

                print("[-] AUTH FAILED")
                attempts += 1

            if attempts == 3:
                print("[-] Authentication failed 3 times. Connection closed.")
                return False

            #Diffie–Hellman (Task - 2 Specific Task)
            p = int(os.environ["P"])
            g = int(os.environ["G"])

            a = random.randint(2, p - 2)
            A = pow(g, a, p)

            B = int(self.socket.recv(1024).decode())
            self.socket.send(str(A).encode())

            self.session_key = pow(B, a, p)
            print("[+] Session key established")

            return True

        except KeyError:
            print("[-] Environment variables P and G not set")
            return False

        except Exception as e:
            print(f"[-] Connection error: {e}")
            return False

    def send_command(self, command):
        self.socket.send(command.encode())
        return self.socket.recv(4096).decode()

    def run(self):
        if not self.connect():
            self.socket.close()
            return

        try:
            while True:
                command = input("> ").strip()
                if not command:
                    continue

                response = self.send_command(command)
                print(response)

                if command.upper() == "QUIT":
                    break
        finally:
            self.socket.close()
            print("[*] Connection closed")


if __name__ == "__main__":
    server_ip = input("Server IP: ").strip()
    FileManagementClient(server_ip).run()
