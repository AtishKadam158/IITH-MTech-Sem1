# Importing required Modules
import socket
import os
from datetime import datetime
import stat


class FileManagementServer:
    def __init__(self, host='0.0.0.0', port=5555, files_directory='server_files'):
        self.host = host
        self.port = port
        self.files_directory = files_directory
        self.log_file = "server.log"

        if not os.path.exists(self.files_directory):
            os.makedirs(self.files_directory)

    # Adding log message to server.log file and printing it on console
    def log_message(self, msg_type, message):   
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        entry = f"[{timestamp}] {msg_type}: {message}"

        with open(self.log_file, 'a') as f:
            f.write(entry + "\n")

        print(entry)

    # Listing all files in server_file folder
    def handle_list(self):
        files = [
            f for f in os.listdir(self.files_directory)
            if os.path.isfile(os.path.join(self.files_directory, f))
        ]
        return " ".join(files) if files else "No files found"

    # Info about required file
    def handle_info(self, filename):
        filename = filename.strip() 
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
        filename = filename.strip()
        path = os.path.join(self.files_directory, filename)

        if not os.path.isfile(path):
            return "ERROR: File not found"

        return f"{os.path.getsize(path)} bytes"

    
    # We suport three commands LIST, INFO <filename>, GETSIZE <filename> and QUIT 
    # This Function calls those function which is required
    def process_command(self, command):
        parts = command.split(maxsplit=1)
        cmd = parts[0]

        if cmd == "LIST":
            return self.handle_list()

        elif cmd == "INFO" and len(parts) == 2:
            return self.handle_info(parts[1].strip()) 

        elif cmd == "GETSIZE" and len(parts) == 2:
            return self.handle_getsize(parts[1].strip()) 

        elif cmd == "QUIT":
            return "QUIT"

        else:
            return "ERROR: Invalid command"


    # Server get request and provide resopnse
    # we these add log to server.log file
    def handle_client(self, client_socket):
        try:
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
            client_socket.close()


    def start(self):
        #Creating a TCP socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Binding and listening
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)

        print("[*] Server listening...")

        try:
            while True:
                client_socket, _ = server_socket.accept()
                self.handle_client(client_socket)

        except KeyboardInterrupt:
            print("\n[!] Server shutting down...")

        finally:
            server_socket.close()

# Satring point
if __name__ == "__main__":
    FileManagementServer().start()
