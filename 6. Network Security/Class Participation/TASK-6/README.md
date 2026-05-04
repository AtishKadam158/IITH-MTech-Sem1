# TCP SYN Scanner (Scapy)

> Submitted by - Atish Kadam (CS25MTECH14003)

> I have not given any presenatation in class.  
> Submitting this as part of Class Participation.

A simple TCP SYN port scanner written in Python using **Scapy**.


## Features

- Sends TCP SYN packets to detect open ports
- Identifies:
  - `open` ports from SYN-ACK replies
  - `closed` ports from RST replies
  - `filtered` ports when there is no response
- Multithreaded scanning for better speed
- Optional display of closed ports
- Common service name hints for popular ports


## Requirements

- Kali Linux - used by me
- Python 3
- `pip3`
- Root privileges (required for raw packet crafting with Scapy)

## Install Dependencies on Kali Linux

Open a terminal and run:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

Install Scapy:

```bash
sudo pip3 install scapy
```

If you prefer a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install scapy
```

## Save the Script

Save your Python code as:

```bash
tcp_syn_scanner.py
```

Make it executable if you want:

```bash
chmod +x tcp_syn_scanner.py
```

## Run the Scanner
Before running find IP address of your network which you want scan
For example i have tested on router
Find out IP address of your router using 
```bash
ip route | grep default
```

Because Scapy sends raw packets, run it with `sudo`:

```bash
sudo python3 tcp_syn_scanner.py 192.168.0.1
```

## Examples

Scan the default range (`1-1024`):

```bash
sudo python3 tcp_syn_scanner.py 192.168.0.1
```

Scan a custom range:

```bash
sudo python3 tcp_syn_scanner.py 192.168.0.1 -p 1-1024
```

Scan selected ports:

```bash
sudo python3 tcp_syn_scanner.py 192.168.0.1 -p 22,80,443,3306
```

Scan a larger range with more threads:

```bash
sudo python3 tcp_syn_scanner.py 192.168.0.1 -p 1-65535 -t 200
```

Show closed ports too:

```bash
sudo python3 tcp_syn_scanner.py 192.168.0.1 -p 22,80,443 --show-closed
```

Adjust timeout per port:

```bash
sudo python3 tcp_syn_scanner.py 192.168.0.1 -p 1-1024 --timeout 2
```

## Usage Options

- `target`  
  Target IP address to scan

- `-p`, `--ports`  
  Port list or range  
  Examples: `80,443`, `1-1024`, `22,80,443,8000-9000`

- `-t`, `--threads`  
  Maximum number of concurrent threads

- `--timeout`  
  Seconds to wait for a reply on each port

- `--show-closed`  
  Print closed ports as well



## Troubleshooting

### `ModuleNotFoundError: No module named 'scapy'`

Install Scapy:

```bash
sudo pip3 install scapy
```

### `PermissionError` or no replies

Run with `sudo`:

```bash
sudo python3 tcp_syn_scanner.py <target-ip>
```

## Acknowledgement

I would like to acknowledge the resources and support that contributed to the development of this TCP SYN Scanner.

The implementation is based on concepts from the Scapy documentation and standard TCP/IP networking principles, particularly the SYN scanning technique. I referred to general computer networking materials, online tutorials, and publicly available documentation to better understand packet crafting and response analysis. 

I confirm that:

- The code has been developed based on my own understanding.  
- External resources were used strictly for learning and reference purposes.  
- i have done discussion limited to high-level conceptual understanding with my friends.

## References

- Scapy Documentation — https://scapy.readthedocs.io/
- Linux manual pages (man pages) — https://man7.org/linux/man-pages/
- Various online tutorials and educational resources on TCP SYN scanning and port scanning techniques