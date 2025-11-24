import socket
import threading
import struct
import os
import math
import time

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5005
CHUNK_SIZE = 1024 * 1024
NUM_CONNECTIONS = 4  

def send_chunk(chunk_index, total_chunks, chunk_data):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER_IP, SERVER_PORT))
        header = struct.pack("!IIQ", chunk_index, total_chunks, len(chunk_data))
        s.sendall(header)
        s.sendall(chunk_data)
        s.close()
        print(f"Sent chunk {chunk_index+1}/{total_chunks}")
    except Exception as e:
        print(f"Error sending chunk {chunk_index}: {e}")

def main():
    file_path = input("Enter file path to send: ").strip()
    if not os.path.exists(file_path):
        print("File not found.")
        return

    file_size = os.path.getsize(file_path)
    total_chunks = math.ceil(file_size / CHUNK_SIZE)
    print(f"Splitting '{file_path}' into {total_chunks} chunks...")

    with open(file_path, "rb") as f:
        chunks = [f.read(CHUNK_SIZE) for _ in range(total_chunks)]

    print(f"Starting upload with {NUM_CONNECTIONS} connections...")
    start_time = time.time()
    i = 0
    while i < total_chunks:
        active_threads = []
        for j in range(NUM_CONNECTIONS):
            if i >= total_chunks:
                break
            t = threading.Thread(target=send_chunk, args=(i, total_chunks, chunks[i]))
            t.start()
            active_threads.append(t)
            i += 1
        for t in active_threads:
            t.join()

    end_time = time.time()
    print(f"File '{os.path.basename(file_path)}' sent successfully in {end_time - start_time:.2f}s")

if __name__ == "__main__":
    main()
