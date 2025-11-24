ACN Tutorial: Reliable File Transfer over 
                    UDP
Stop-and-Wait Protocol with Timeout and Retransmission


# Environment 
    Language - Python
    Operating System - Windows 11
    IDE - VS Code


# Steps to Perform
    1. Open Repository in VScode 
    2. Open two different terminals
    3. On one terminal run "python server_udp.py"
    4. On another terminal run "python client_udp.py"

# How to change % packet loss
    In server_udp.py keep this main function
    # For 0% 
            if __name__ == "__main__":
                receive_file(loss_prob=0.0)
    
     # For 10% 
            if __name__ == "__main__":
                receive_file(loss_prob=0.1)
    
     # For 20% 
            if __name__ == "__main__":
                receive_file(loss_prob=0.2)

     # For 30% 
            if __name__ == "__main__":
                receive_file(loss_prob=0.3)


# To change timeout time 
    In client_udp.py keep this main function
        if __name__ == "__main__":
            send_file("input_file.pdf", timeout=0.01)  <---- You can change this as per you

