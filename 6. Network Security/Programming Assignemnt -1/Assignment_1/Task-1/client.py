import socket

class FileManagementClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.socket = None

    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"[+] Connected to {self.host}:{self.port}")
            return True

        except Exception as e:
            print(f"[-] Connection error: {e}")
            return False

    def send_command(self, command):
        self.socket.send(command.encode())
        return self.socket.recv(4096).decode()

    def run(self):
        if not self.connect():
            return

        try:
            while True:
                raw_input = input("> ").strip()

                if not raw_input:
                    continue

                parts = raw_input.split(maxsplit=1)

                cmd = parts[0].upper()

                if len(parts) == 2:
                    command = f"{cmd} {parts[1]}"
                else:
                    command = cmd

                response = self.send_command(command)

                if response:
                    print(f"RESPONSE: {response}")

                if cmd == "QUIT":
                    break

        finally:
            self.socket.close()
            print("[*] Connection closed")

# Starting point to code
if __name__ == "__main__":
    server_ip = input("Server IP: ").strip()
    FileManagementClient(server_ip).run()
