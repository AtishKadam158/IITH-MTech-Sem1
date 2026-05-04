# Task - 4. Encryption of Communication  


## GROUP MEMBERS
    Member 1:
    Name: ATISH KADAM
    Roll No: CS25MTECH14003

    Member 2:
    Name: AKARSH DUBEY
    Roll No: CS25MTECH14001


## CONTRIBUTION OF GROUP MEMBERS

    # Atish Kadam:
        Implemented server-side AES encryption and decryption of commands, responses, and file chunks.
        Implemented MAC verification before decryption.
        Integrated encryption with existing integrity and session-key mechanisms.
        readme.md generation 

    # Akarsh Dubey:
        Implemented client-side AES encryption and decryption logic.
        Implemented encrypted command transmission and encrypted file reception.
        Displayed ciphertext and corresponding plaintext at the client side for demonstration.
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
	[Cipher]: d792565775020e5da26f080ae98e471b279d0576b2bda35554d0ae5eab55f1fda2b08932d8e4c31cfccaf2795be2873d8c9404880ad1b3e4897ab0548631b95a
	[Plain]: file2.txt file1.txt readme.md document.txt
	
   2. > INFO file1.txt
	[Cipher]: 7f0f61eabb5673443e28b575715de33f79e81894b610a96ea8ac33851a0c93636b46b9831f8fa2dfd4fad1be49a3b129cd863a7878005f8f4aee47b53a3778470bbf7e2c59a483350ec8f9bc3b18004414cbeb0b5e7cc624fada45395654fe2a7ba4e4ff1178ff71bc77b760bdb11a372d3db576fe4709f6edc4de008950c4d7
	[Plain]: Last Modified: 2026-02-12 03:48:00.174662, Created: 2026-02-12 03:48:00.174662, Permissions: -rw-rw-r--
	
   3. > GETSIZE file1.txt
	[Cipher]: 0b05dd825bccddb0e4d6893ecc2a8c52e168a18f144887d531835f6ded54e928
	[Plain]: 4988 bytes
	
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
	
   5. > GET file1.txt
	[*] File Size: 4988 bytes
	[*] Downloading to: downloaded_file1.txt
	--------------------------------------------------
	[*] Chunk 0:
		[Cipher]: <cipher text>
		[Plain]: <plain text> 

	[*] Chunk 1:
		[Cipher]: <cipher text>
		[Plain]: <plain text> 

	[*] Chunk 2:
		[Cipher]: <cipher text>
		[Plain]: <plain text> 

	[*] Chunk 3:
		[Cipher]: <cipher text>
		[Plain]: <plain text> 

	[*] Chunk 4:
		[Cipher]: <cipher text>
		[Plain]: <plain text> 
	--------------------------------------------------
	[✓] Transfer Complete.
	[*] Total chunks received: 5


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
	
	At server Side
		socket
		os
		threading
		datetime
		stat
		hashlib
		random
		struct
		
		## External Library
			from Crypto.Cipher import AES
			from Crypto.Util.Padding import pad, unpad
		
	At Client Side
		socket
		hashlib
		random
		os
		struct
		
		## External Library
			from Crypto.Cipher import AES
			from Crypto.Util.Padding import pad, unpad

    

6. References used

	The following resources were referred for conceptual
	understanding:

	    Python socket programming documentation
	    Operating system file metadata concepts
	    Lecture notes
	    GFG


	Discussions:
	    General debugging discussions with classmates
