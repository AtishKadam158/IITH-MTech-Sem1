# ARP Spoof Detector (Scapy)
> Submitted by - Atish Kadam (CS25MTECH14003)

> I have not given any presentation in class.  
> Submitting this as part of Class Participation.

A real-time ARP spoof detection tool written in Python using **Scapy**.


## Features

- Monitors live ARP traffic on a network interface
- Detects:
  - `MAC CHANGE` — an IP suddenly claims a different MAC address
  - `GATEWAY IMPERSONATION` — a non-gateway MAC claims the gateway's IP
  - `BROADCAST REPLY` — ARP replies sent to `ff:ff:ff:ff:ff:ff` (abnormal)
  - `GRATUITOUS ARP FLOOD` — same IP sends ≥5 gratuitous ARPs within 10 seconds
- Auto-detects the default gateway IP and MAC
- Raises colour-coded real-time alerts on the console
- Logs all suspicious events to a `.log` file
- Exports alerts to a `.csv` file for post-analysis
- Displays a session summary with the full learned ARP table on exit


## Requirements

- Kali Linux — used by me
- Python 3
- `pip3`
- Root privileges (required for raw packet sniffing with Scapy)


## Install Dependencies on Kali Linux

Open a terminal and run:

```bash
sudo apt update
sudo apt install -y python3 python3-pip dsniff
```

Install Scapy for root (required because the script runs with `sudo`):

```bash
sudo pip3 install scapy --break-system-packages
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
arp_spoof_detector.py
```

Make it executable if you want:

```bash
chmod +x arp_spoof_detector.py
```


## Run the Detector

Before running, find your active network interface:

```bash
ip link show
```

Look for an interface in `state UP` — commonly `wlan0` (Wi-Fi) or `eth0` (Ethernet).

Because Scapy sniffs raw packets, run it with `sudo`:

```bash
sudo python3 arp_spoof_detector.py -i wlan0
```


## Examples

Run with auto-detected interface and gateway:

```bash
sudo python3 arp_spoof_detector.py
```

Specify interface manually:

```bash
sudo python3 arp_spoof_detector.py -i wlan0
```

Verbose mode — print every ARP packet seen:

```bash
sudo python3 arp_spoof_detector.py -i wlan0 -v
```

Pin gateway manually (skip auto-detection):

```bash
sudo python3 arp_spoof_detector.py -i wlan0 -g 192.168.0.1 -m 28:87:ba:d8:07:2c
```

Custom log and CSV file paths:

```bash
sudo python3 arp_spoof_detector.py -i wlan0 -l /var/log/arp.log -c /var/log/arp_alerts.csv
```

Simulate an attack for testing (run in a second terminal):

```bash
sudo arpspoof -i wlan0 192.168.0.1
```



## Troubleshooting

### `ModuleNotFoundError: No module named 'scapy'`

Install Scapy for root, not just the current user:

```bash
sudo pip3 install scapy --break-system-packages
```

### `PermissionError` or no packets captured

Run with `sudo`:

```bash
sudo python3 arp_spoof_detector.py -i wlan0
```

### Gateway MAC not detected

Specify the interface explicitly so Scapy can probe the gateway:

```bash
sudo python3 arp_spoof_detector.py -i wlan0
```

Or set it manually:

```bash
sudo python3 arp_spoof_detector.py -i wlan0 -g 192.168.0.1 -m 28:87:ba:d8:07:2c
```


## Acknowledgement

I would like to acknowledge the resources and support that contributed to the development of this ARP Spoof Detector.

The implementation is based on concepts from the Scapy documentation and standard ARP protocol behaviour, particularly the gratuitous ARP and ARP cache poisoning techniques. I referred to general computer networking materials, online tutorials, and publicly available documentation to better understand ARP packet structure and detection strategies.

I confirm that:

- The code has been developed based on my own understanding.  
- External resources were used strictly for learning and reference purposes.  
- Discussion was limited to high-level conceptual understanding with my friends.


## References

- Scapy Documentation — https://scapy.readthedocs.io/
- RFC 826 — An Ethernet Address Resolution Protocol — https://datatracker.ietf.org/doc/html/rfc826
- Linux manual pages (man pages) — https://man7.org/linux/man-pages/
- Various online tutorials and educational resources on ARP spoofing, ARP cache poisoning, and network security monitoring