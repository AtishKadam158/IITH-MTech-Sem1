import socket
import struct
import os
import time

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5001

def send_file (s, file_path):
    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    s.sendall(struct.pack("!I", 1))
    s.sendall(struct.pack("!Q", file_size))
    with open(file_path, "rb") as f:
        start=time.time()
        while True:
            data = f.read(4096)
            if not data:
                break
            s.sendall(data)
        end = time.time()
    time_taken=end-start
    s.close()
    print(f"File '{filename}' sent successfully {time_taken}")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVER_IP, SERVER_PORT))
        print(f"Connected to server {SERVER_IP}:{SERVER_PORT}")

        while True:
            file_path = input("\nEnter file path to send").strip()
            if file_path.lower() == "exit":
                s.sendall(struct.pack("!I", 0)) 
                print("Connection closed.")
                break

            if not os.path.exists(file_path):
                print("File not found.")
                continue

            send_file(s, file_path)


if __name__ == "__main__":
    main()
