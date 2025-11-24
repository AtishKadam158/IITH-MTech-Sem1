#!/usr/bin/env python3
import socket
import random
import time
import os

def receive_file(output_file='Recieced_files/received_file.pdf', port=9003, loss_prob=0.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))

    print(f"  Listening on UDP port {port}")
    print(f"Output file: {output_file}")
    print(f"Simulated packet loss: {loss_prob * 100:.1f}%\n")

    expected_seq = 0
    total_packets = 0
    dropped_packets = 0
    duplicate_packets = 0
    bytes_received = 0
    start_time = None

    with open(output_file, 'wb') as f:
        while True:
            packet, addr = sock.recvfrom(2048)

            if start_time is None:
                start_time = time.time()

            # EOF detection
            if packet == b'EOF':
                print("EOF received. File transfer complete.\n")
                break

            # Simulate random packet loss
            if random.random() < loss_prob:
                dropped_packets += 1
                print(f"Simulated packet loss (dropping packet)")
                continue

            seq = packet[0]
            data = packet[1:]

            # Correct sequence packet
            if seq == expected_seq:
                f.write(data)
                bytes_received += len(data)
                sock.sendto(seq.to_bytes(1, 'big'), addr)
                print(f"Received seq={seq}, sent ACK {seq}")
                expected_seq ^= 1
                total_packets += 1
            else:
                # Duplicate packet
                duplicate_packets += 1
                ack = (expected_seq ^ 1).to_bytes(1, 'big')
                sock.sendto(ack, addr)
                print(f"Duplicate seq={seq}, resent ACK {ack.hex()}")

    end_time = time.time()

    print("========================================================")
    print("            Transfer Summary: Server Side")
    print("========================================================")
    print(f"  File saved as: {output_file}")
    print(f"  Simulated packet loss: {loss_prob * 100:.1f}%")
    print(f"  File size received: {bytes_received} bytes")
    print(f"  Total packets received: {total_packets}")
    print(f"  Duplicates: {duplicate_packets}")
    print(f"  Dropped (simulated): {dropped_packets}")
    print(f"  Total time: {end_time - start_time:.2f} seconds")
    print("========================================================")

    # Confirm file integrity
    if os.path.exists(output_file):
        print(f"File '{output_file}' written successfully.")
    else:
        print(f"File not created. Check for errors.")

    sock.close()


if __name__ == "__main__":
    receive_file(loss_prob=0.3)
