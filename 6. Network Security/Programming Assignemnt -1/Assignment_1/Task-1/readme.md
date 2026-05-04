
# Task -1 Basic File Management Service 


## GROUP MEMBERS
    Member 1:
    Name: ATISH KADAM
    Roll No: CS25MTECH14003

    Member 2:
    Name: AKARSH DUBEY
    Roll No: CS25MTECH14001


## CONTRIBUTION OF GROUP MEMBERS

    # Atish Kadam:
        Implemented server-side socket logic
        Implemented command processing logic
        readme.md generation

    # Akarsh Dubey:
        Implemented client-side program
        Implemented testing and debugging
        report generation


1. A) Instruction for Running the code Server and client on the same PC

    To run the programs:
    
    Start the Server:
        Start Server:
        > python server.py

    Start Client (in a separate terminal):
        > python client.py
        
    Now it will ask for server ip:
    	> Server IP: 127.0.0.1
	> [+] Connected to 127.0.0.1:5555

    
    

   B) Instruction for Running the code Server and client on the Different PC

    Know the IP address of Server-
        Use run command on terminal ifconfig
        for example i have IP - 192.168.0.102 as server 
   To run the programs:
    
    Start the Server:
        Start Server:
        > python server.py

    Start Client (in a separate terminal):
        > python client.py
        

    	
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
		    readme.md 
		    server_files/


4. Libraries used
	## No External Library is used 
	
	At server Side
		socket
		os
		datetime
		stat
		
	At Client Side
		socket

6. References used

	The following resources were referred for conceptual
	understanding:

	    Python socket programming documentation
	    Operating system file metadata concepts
	    Lecture notes
	    GFG


	Discussions:
	    General debugging discussions with classmates
