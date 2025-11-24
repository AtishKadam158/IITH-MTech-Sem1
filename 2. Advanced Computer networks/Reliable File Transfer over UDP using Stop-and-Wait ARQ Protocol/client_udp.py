#!/usr/bin/env python3
import socket
import time
import os

def send_file(filename, server_ip='127.0.0.1', server_port=9003, timeout=1.0):
    if not os.path.exists(filename):
        print(f"File '{filename}' not found.")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)

    file_size = os.path.getsize(filename)
    print(f"Preparing to send file: {filename}")
    print(f"File size: {file_size} bytes\n")

    seq = 0  # sequence number (0 or 1)
    retransmissions = 0
    total_packets = 0
    start_time = time.time()

    with open(filename, 'rb') as f:
        chunk_size = 1024
        while True:
            data = f.read(chunk_size)
            if not data:
                break  # end of file

            packet = seq.to_bytes(1, 'big') + data  # prepend 1-byte seq number

            while True:
                try:
                    sock.sendto(packet, (server_ip, server_port))
                    print(f"Sent packet seq={seq} ({len(data)} bytes)")

                    ack, _ = sock.recvfrom(1024)
                    if ack == seq.to_bytes(1, 'big'):
                        print(f"ACK {seq} received\n")
                        seq ^= 1  # toggle sequence number
                        total_packets += 1
                        break
                    else:
                        print(f"Wrong ACK received. Retrying...")
                        retransmissions += 1

                except socket.timeout:
                    print(f"Timeout waiting for ACK. Resending seq={seq}")
                    retransmissions += 1

    # Send EOF to indicate completion
    sock.sendto(b'EOF', (server_ip, server_port))
    end_time = time.time()
    print("========================================================")
    print("           Transfer Summary - Client Side")
    print("========================================================")
    print("File sent successfully.")
    print(f"File name: {filename}")
    print(f"File size: {file_size} bytes")
    print(f"Total packets sent: {total_packets}")
    print(f"Retransmissions: {retransmissions}")
    print(f"Total transfer time: {end_time - start_time:.2f} seconds")
    print("========================================================")
    
    sock.close()


if __name__ == "__main__":
    send_file("input_file.pdf", timeout=0.01)

