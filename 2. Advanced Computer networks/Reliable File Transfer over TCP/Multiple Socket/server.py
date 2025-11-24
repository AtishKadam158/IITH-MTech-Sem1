import socket
import threading
import struct
import os
import time

HOST = "0.0.0.0"
PORT = 5005
OUTPUT_FOLDER = "received_files"
OUTPUT_FILE = os.path.join(OUTPUT_FOLDER, "final_received_file.pdf")

received_chunks = {}
total_chunks_expected = None
last_received_time = time.time()
lock = threading.Lock()

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def handle_client(conn, addr):
    global total_chunks_expected, last_received_time

    print(f"Connected with {addr}")
    try:
        header = conn.recv(16)
        if len(header) < 16:
            print(f"Invalid header from {addr}")
            return
        chunk_index, total_chunks, chunk_size = struct.unpack("!IIQ", header)
        total_chunks_expected = total_chunks  

        chunk_data = b''
        remaining = chunk_size
        while remaining > 0:
            data = conn.recv(min(4096, remaining))
            if not data:
                break
            chunk_data += data
            remaining -= len(data)

        if len(chunk_data) != chunk_size:
            print(f"Warning: incomplete chunk {chunk_index} from {addr} ({len(chunk_data)}/{chunk_size})")
        with lock:
            received_chunks[chunk_index] = chunk_data
            last_received_time = time.time()
            print(f"Received chunk {chunk_index + 1}/{total_chunks} from {addr}")

    except Exception as e:
        print(f"Error with {addr}: {e}")

    finally:
        conn.close()
        print(f"Connection closed: {addr}")


def assemble_file():
    global total_chunks_expected, received_chunks

    while True:
        time.sleep(1)
        with lock:
            if total_chunks_expected and len(received_chunks) == total_chunks_expected:
                if time.time() - last_received_time < 2:
                    continue

                print("All chunks received. Assembling file...")
                try:
                    with open(OUTPUT_FILE, "wb") as f:
                        for i in range(total_chunks_expected):
                            if i not in received_chunks:
                                print(f"Missing chunk {i}")
                                return
                            f.write(received_chunks[i])

                    print(f"File assembled successfully → {OUTPUT_FILE}")

                except Exception as e:
                    print(f"Error writing file: {e}")
                received_chunks.clear()
                total_chunks_expected = None


def start_server():
    print(f"Server listening on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()

        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
            print(f"Active connections: {threading.active_count() - 1}")


if __name__ == "__main__":
    threading.Thread(target=assemble_file, daemon=True).start()
    start_server()
