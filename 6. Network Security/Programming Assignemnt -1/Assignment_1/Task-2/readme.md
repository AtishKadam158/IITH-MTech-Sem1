
# Task - 2 Authentication with Multiple Clients and Session Key Establishment  


## GROUP MEMBERS
    Member 1:
    Name: ATISH KADAM
    Roll No: CS25MTECH14003

    Member 2:
    Name: AKARSH DUBEY
    Roll No: CS25MTECH14001


## CONTRIBUTION OF GROUP MEMBERS

    # Atish Kadam:
        Implemented Multiple Client requirement 
        Implemented Account Lockout Policy 
        readme.md file generation

    # Akarsh Dubey:
        Implemented Authentication Protocol Diffie Hellman at both server and Client side
        Implemented testing and debugging
        Report generation

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
	
   4. > QUIT
  	[*] Connection closed
    
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
		
	At Client Side
		socket
		hashlib
		random
		os

    

6. References used

	The following resources were referred for conceptual
	understanding:

	    Python socket programming documentation
	    Operating system file metadata concepts
	    Lecture notes
	    GFG


	Discussions:
	    General debugging discussions with classmates


