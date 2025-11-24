import socket
import threading
import struct
import os
import time

os.makedirs("received_files", exist_ok=True)

HOST = "0.0.0.0"
PORT = 5001

def handle_client(conn, addr):
    print(f"Connected to {addr}")
    try:
        while True:
            ready = conn.recv(4)
            if not ready:
                break

            ready_flag = struct.unpack("!I", ready)[0]
            if ready_flag == 0:
                print(f"Client {addr} disconnected gracefully.")
                break

            size_data = conn.recv(8)
            if not size_data:
                break
            file_size = struct.unpack("!Q", size_data)[0]

            file_path = os.path.join("received_files", f"Received_File_From_{addr[0]}.bin")

            start_time = time.time()
            received = 0

            with open(file_path, "wb") as f:
                while received < file_size:
                    chunk = conn.recv(min(4096, file_size - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)

            duration = time.time() - start_time
            print(f"File received from {addr}: {file_size} bytes in {duration:.2f} sec")

    except Exception as e:
        print(f"Error handling client {addr}: {e}")
    finally:
        conn.close()
        print(f"Connection closed for {addr}")

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()
            print(f"Active connections: {threading.active_count() - 1}")

if __name__ == "__main__":
    start_server()
