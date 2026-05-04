import socket
import hashlib
import random
import os
import struct

CHUNK_SIZE = 1024
MAC_SIZE = 32

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

            # Diffie–Hellman (Task - 2 Specific Task)
            p = int(os.environ["P"])
            g = int(os.environ["G"])
            a = random.randint(2, p - 2)
            A = pow(g, a, p)

            B = int(self.socket.recv(1024).decode())
            self.socket.send(str(A).encode())

            shared_secret = pow(B, a, p)
    
            self.session_key = hashlib.sha256(str(shared_secret).encode()).digest()
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

    # Task 3: File download with integrity verification
    def download_file(self, filename):
        """Download file from server with MAC verification"""
        header = self.socket.recv(1024).decode()

        if header == "FILE NOT AVAILABLE":
            print("[!] File not available on server")
            return

        if not header.startswith("FILE_SIZE:"):
            print(f"[!] Unexpected response: {header}")
            return

        file_size = int(header.split(":")[1])
        print(f"[*] File size: {file_size} bytes")
        
        # Send READY signal
        self.socket.send(b"READY")

        expected_seq = 0
        received_bytes = 0
        output_file = "downloaded_" + filename

        print(f"[*] Downloading to: {output_file}")

        with open(output_file, "wb") as f:
            while received_bytes < file_size:
                try:
                    # Calculate expected packet size
                    remaining = file_size - received_bytes
                    expected_data_size = min(CHUNK_SIZE, remaining)
                    packet_size = 4 + expected_data_size + MAC_SIZE
                    
                    # Set timeout for receiving
                    self.socket.settimeout(5.0)
                    
                    # Receive entire packet
                    packet = self.recv_exact(packet_size)
                    
                    # Parse packet: [SEQ(4)][DATA(variable)][MAC(32)]
                    seq_no = struct.unpack("!I", packet[:4])[0]
                    data = packet[4:-MAC_SIZE]
                    mac = packet[-MAC_SIZE:]

                except socket.timeout:
                    print("\n[!] Timeout waiting for data")
                    return
                except Exception as e:
                    print(f"\n[!] Reception error: {e}")
                    return

                # Verify sequence number
                if seq_no != expected_seq:
                    print(f"\n[!] Sequence error: expected {expected_seq}, got {seq_no}")
                    self.socket.send(b"ERROR: OUT OF ORDER")
                    return

                # Verify MAC = HASH(DATA || SEQ_NO || SESSION_KEY)
                expected_mac = hashlib.sha256(
                    data + struct.pack("!I", seq_no) + self.session_key
                ).digest()

                if mac != expected_mac:
                    print(f"\n[!] MAC verification failed for chunk {seq_no}")
                    self.socket.send(b"ERROR: MAC MISMATCH")
                    return

                # ✅ ONLY LINE ADDED BELOW
                print(f"\n[+] Chunk {seq_no} received. MAC verified.")

                # Write verified data
                f.write(data)
                received_bytes += len(data)
                
                # Send acknowledgment
                self.socket.send(f"ACK:{seq_no}".encode())

                # Progress indicator
                progress = (received_bytes / file_size) * 100
                print(f"\r[*] Progress: {progress:.1f}% ({received_bytes}/{file_size} bytes)", end='', flush=True)

                expected_seq += 1

        print() 
        
        # Receive completion signal
        try:
            self.socket.settimeout(1.0)
            completion = self.socket.recv(1024).decode()
            if "COMPLETE" in completion:
                print(f"[✓] Server confirmed transfer complete")
        except socket.timeout:
            pass
        finally:
            self.socket.settimeout(None)
        
        print(f"[✓] File downloaded successfully: {output_file}")
        print(f"[✓] Total chunks received: {expected_seq}")
        print(f"[✓] Total bytes: {received_bytes}/{file_size}")
        print(f"[✓] All MACs verified successfully")

    def recv_exact(self, n):
        data = b""
        while len(data) < n:
            packet = self.socket.recv(n - len(data))
            if not packet:
                raise ConnectionError("Connection closed")
            data += packet
        return data

    def run(self):
        if not self.connect():
            self.socket.close()
            return
        try:
            while True:
                command = input("\n> ").strip()
                if not command:
                    continue
                
                # Task 3: Handle GET command separately
                cmd_parts = command.split(maxsplit=1)
                if len(cmd_parts) >= 2 and cmd_parts[0].upper() == "GET":
                    filename = cmd_parts[1]
                    self.socket.send(command.encode())
                    self.download_file(filename)
                else:
                    response = self.send_command(command)
                    print(response)
                    if command.upper() == "QUIT":
                        break
        except KeyboardInterrupt:
            print("\n[*] Exiting...")
        finally:
            self.socket.close()
            print("[*] Connection closed")

if __name__ == "__main__":
    server_ip = input("Server IP: ").strip()
    FileManagementClient(server_ip).run()