
# Task -3 File Download with Integrity  


## GROUP MEMBERS
    Member 1:
    Name: ATISH KADAM
    Roll No: CS25MTECH14003

    Member 2:
    Name: AKARSH DUBEY
    Roll No: CS25MTECH14001


## CONTRIBUTION OF GROUP MEMBERS

    # Atish Kadam:
        Implemented server-side logic for handling the GET <filename> command.
        Designed and implemented file chunking  on the server.
        Implemented MAC generation for each chunk using the session key.
        creating readme.txt 

    # Akarsh Dubey:
        Implemented client-side logic for secure file download.
        Implemented chunk reception, MAC verification, and file reconstruction.
        Performed testing and debugging of the file download and integrity mechanism.
        Report Generation


1. A) Instruction for Running the code Server and client on the same PC

    To run the programs:
    
    Start the Server:
        Start Server:
        > export P=23
        > export G=5
        > python server.py

    Start Client (in a separate terminal):
        > export P=23
        > export G=5
        > python client.py
    Now it will ask for server ip:
    	> Server IP: 127.0.0.1
	> [+] Connected to 127.0.0.1:5555
	
   Now enter the Credentials:
	> Username: alice
	> Shared Secret: qwertyuiop
	
   Output:
	[+] Authentication successful
	[+] Session key established
    
    

   B) Instruction for Running the code Server and client on the Different PC

    Know the IP address of Server-
        Use run command on terminal ifconfig
        for example i have IP - 192.168.0.102
   To run the programs:
    
    Start the Server:
        Start Server:
        > export P=23
        > export G=5
        > python server.py

    Start Client (in a separate terminal):
        > export P=23
        > export G=5
        > python client.py
        
    Now it will ask for server ip:
    
    	> Server IP: 192.168.102.2
	> [+] Connected to 192.168.102.2:5555
	
    Now enter the Credentials:
	> Username: alice
	> Shared Secret: qwertyuiop
	
    Output:
	[+] Authentication successful
	[+] Session key established
	
 C) Capturing wireshark traces
   
   	Client and Server at Different PC
   	
	   	At server side:
			1  open wireshark
			2. Choose interface 
			3. In my case Server and client both are connected to same Wifi
			4. I choose wlan0 (as it is for WiFi)
			5. Start Capture
			6. Then perform all operations
			7. Keep Wireshark running while the server is active
			8. Observe packets appearing in Wireshark
			9. After all client operations are completed, click Stop Capture
			10. Save the capture file
			
			
	       At Client side:
	       		
	       		1  open wireshark
			2. Choose interface 
			3. In my case Server and client both are connected to same Wifi
			4. I choose wlan0 (as it is for WiFi)
			5. Start Capture
			6. Then perform all operations
			7. Keep Wireshark running while the client is active
			8. Observe packets appearing in Wireshark
			9. After all client operations are completed, click Stop Capture
			10. Save the capture file
	   
	Client and Server at Same PC

	      At server side:

			1. open wireshark
			2. Choose interface
			3. In my case Server and client both are running on same PC
			4. I choose lo (loopback) interface
			5. Start Capture
			6. Then perform all operations
			7. Keep Wireshark running while the server is active
			8. Observe packets appearing in Wireshark
			9. After all client operations are completed, click Stop Capture
			10. Save the capture file
			
       	     At Client side:
		
			1. open wireshark
			2. Choose interface
			3. In my case Server and client both are running on same PC
			4. I choose lo (loopback) interface
			5. Start Capture
			6. Then perform all operations
			7. Keep Wireshark running while the client is active
			8. Observe packets appearing in Wireshark
			9. After all client operations are completed, click Stop Capture
			10. Save the capture file    		
    	
2. Different commands/ operations 
   
   1. > LIST
	file2.txt file1.txt readme.md document.txt
	
   2. > INFO file1.txt
	Last Modified: 2026-02-11 22:39:45.635151, Created: 2026-02-11 22:39:57.400803, Permissions: -rw-rw-r--
	
   3. > GETSIZE file1.txt
	6395 bytes
	
   4. > GET file1.txt
	[*] File size: 6395 bytes
	[*] Downloading to: downloaded_file1.txt

	[+] Chunk 0 received. MAC verified.
	[*] Progress: 16.0% (1024/6395 bytes)
	[+] Chunk 1 received. MAC verified.
	[*] Progress: 32.0% (2048/6395 bytes)
	[+] Chunk 2 received. MAC verified.
	[*] Progress: 48.0% (3072/6395 bytes)
	[+] Chunk 3 received. MAC verified.
	[*] Progress: 64.1% (4096/6395 bytes)
	[+] Chunk 4 received. MAC verified.
	[*] Progress: 80.1% (5120/6395 bytes)
	[+] Chunk 5 received. MAC verified.
	[*] Progress: 96.1% (6144/6395 bytes)
	[+] Chunk 6 received. MAC verified.
	[*] Progress: 100.0% (6395/6395 bytes)
	[✓] Server confirmed transfer complete
	[✓] File downloaded successfully: downloaded_file1.txt
	[✓] Total chunks received: 7
	[✓] Total bytes: 6395/6395
	[✓] All MACs verified successfully
    


3. Environment Setup

	Requirements:

	1. Python 3.x installed
	2. No external libraries required
	3. Files must be stored inside:
		server_files/

	Example structure:

		Task-1/
		    server.py
		    client.py
		    server.log
		    credentials.txt
		    readme.md 
		    server_files/


4. Libraries used
	## No External Library is used 
	
	At server Side
		socket
		os
		threading
		datetime
		stat
		hashlib
		random
		struct
		
	At Client Side
		socket
		hashlib
		random
		os
		struct

    

6. References used

	The following resources were referred for conceptual
	understanding:

	    Python socket programming documentation
	    Operating system file metadata concepts
	    Lecture notes
	    GFG


	Discussions:
	    General debugging discussions with classmates

