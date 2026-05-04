#!/usr/bin/env python3
from scapy.all import IP, TCP, sr1, conf
import threading
import argparse
import ipaddress
import logging
import time
from datetime import datetime

conf.verb = 0
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)


results = {
    "open":     [],   # SYN-ACK received
    "closed":   [],   # RST received
    "filtered": [],   # No response / ICMP unreachable
}
results_lock = threading.Lock()

#  Core scan function (one port)
def syn_scan_port(target_ip: str, port: int, timeout: float = 1.0) -> str:
    # Build SYN packet
    ip_layer  = IP(dst=target_ip)
    tcp_layer = TCP(dport=port, flags="S")  # SYN flag only
    packet    = ip_layer / tcp_layer

    # Send & wait for one reply
    response = sr1(packet, timeout=timeout, verbose=0)

    if response is None:
        status = "filtered"

    elif response.haslayer(TCP):
        tcp_flags = response[TCP].flags

        if tcp_flags == 0x12:          # SYN-ACK  (0x12 = SYN + ACK)
            # Send RST to cleanly tear down the half-open connection
            rst = ip_layer / TCP(dport=port, flags="R",
                                 seq=response[TCP].ack)
            sr1(rst, timeout=1, verbose=0)
            status = "open"

        elif tcp_flags & 0x04:         # RST bit set
            status = "closed"
        else:
            status = "filtered"

    else:
        # ICMP port-unreachable or other non-TCP reply
        status = "filtered"

    return status

#  Worker thread
def worker(target_ip: str, port: int, timeout: float,
           semaphore: threading.Semaphore, show_closed: bool):
    """Thread worker: scan one port and record result."""
    with semaphore:
        status = syn_scan_port(target_ip, port, timeout)

    with results_lock:
        results[status].append(port)

    # Live output
    if status == "open":
        print(f"  [OPEN]     Port {port:>5}/tcp")
    elif status == "closed" and show_closed:
        print(f"  [CLOSED]   Port {port:>5}/tcp")
    elif status == "filtered":
        pass   # Filtered ports are summarised at the end



#  Main scanner
def run_scan(target: str, ports: list[int], timeout: float,
             max_threads: int, show_closed: bool):

    # Validate target IP
    try:
        ipaddress.ip_address(target)
    except ValueError:
        print(f"[!] Invalid IP address: {target}")
        return

    total   = len(ports)
    banner  = "=" * 55
    print(banner)
    print(f"  TCP SYN Scanner")
    print(banner)
    print(f"  Target  : {target}")
    print(f"  Ports   : {total} ports")
    print(f"  Threads : {max_threads}")
    print(f"  Timeout : {timeout}s per port")
    print(f"  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(banner)
    print()

    # Semaphore limits concurrent threads
    semaphore = threading.Semaphore(max_threads)
    threads   = []
    start     = time.time()

    for port in ports:
        t = threading.Thread(
            target=worker,
            args=(target, port, timeout, semaphore, show_closed),
            daemon=True,
        )
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join()

    elapsed = time.time() - start

    # Summary 
    print()
    print(banner)
    print("  SCAN SUMMARY")
    print(banner)
    print(f"  Scan completed in : {elapsed:.2f} seconds")
    print(f"  Total ports scanned: {total}")

    open_ports     = sorted(results["open"])
    closed_ports   = sorted(results["closed"])
    filtered_ports = sorted(results["filtered"])

    print(f"\n  OPEN     ({len(open_ports)} ports)")
    if open_ports:
        for p in open_ports:
            svc = COMMON_SERVICES.get(p, "unknown")
            print(f"    {p:>5}/tcp  →  {svc}")
    else:
        print("    None found")

    if show_closed:
        print(f"\n  CLOSED   ({len(closed_ports)} ports)")
        for p in closed_ports[:20]:           # cap display at 20
            print(f"    {p:>5}/tcp")
        if len(closed_ports) > 20:
            print(f"    ... and {len(closed_ports)-20} more")

    print(f"\n  FILTERED ({len(filtered_ports)} ports) — no response")
    print(banner)


#  Common service names for open-port display
COMMON_SERVICES = {
    20: "FTP-data",   21: "FTP",       22: "SSH",
    23: "Telnet",     25: "SMTP",      53: "DNS",
    67: "DHCP",       68: "DHCP",      69: "TFTP",
    80: "HTTP",       110: "POP3",     119: "NNTP",
    123: "NTP",       135: "MS-RPC",   137: "NetBIOS",
    138: "NetBIOS",   139: "NetBIOS",  143: "IMAP",
    161: "SNMP",      194: "IRC",      389: "LDAP",
    443: "HTTPS",     445: "SMB",      465: "SMTPS",
    514: "Syslog",    587: "SMTP",     636: "LDAPS",
    993: "IMAPS",     995: "POP3S",    1080: "SOCKS",
    1433: "MSSQL",    1521: "Oracle",  3306: "MySQL",
    3389: "RDP",      5432: "PostgreSQL", 5900: "VNC",
    6379: "Redis",    8080: "HTTP-Alt", 8443: "HTTPS-Alt",
    27017: "MongoDB",
}



#  Port-range parser helper
def parse_ports(port_str: str) -> list[int]:
    """
    Accept formats like:
      80,443,8080          → specific ports
      1-1024               → range
      22,80,443,8000-9000  → mixed
    """
    ports = set()
    for part in port_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            ports.update(range(int(start), int(end) + 1))
        else:
            ports.add(int(part))
    return sorted(ports)

def main():
    parser = argparse.ArgumentParser(
        description="TCP SYN Scanner (Scapy) — run as root",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 tcp_syn_scanner.py 192.168.1.1
  sudo python3 tcp_syn_scanner.py 192.168.1.1 -p 1-1024
  sudo python3 tcp_syn_scanner.py 10.0.0.5 -p 22,80,443,3306 -t 50
  sudo python3 tcp_syn_scanner.py 10.0.0.5 -p 1-65535 -t 200 --show-closed
        """
    )
    parser.add_argument("target",
        help="Target IP address (e.g. 192.168.1.1)")
    parser.add_argument("-p", "--ports", default="1-1024",
        help="Port range/list (default: 1-1024)")
    parser.add_argument("-t", "--threads", type=int, default=100,
        help="Max concurrent threads (default: 100)")
    parser.add_argument("--timeout", type=float, default=1.0,
        help="Seconds to wait per port (default: 1.0)")
    parser.add_argument("--show-closed", action="store_true",
        help="Also print closed ports (noisy, useful for debugging)")

    args = parser.parse_args()

    try:
        ports = parse_ports(args.ports)
    except ValueError:
        print("[!] Invalid port specification. Use formats like: 80,443 or 1-1024")
        return

    run_scan(
        target=args.target,
        ports=ports,
        timeout=args.timeout,
        max_threads=args.threads,
        show_closed=args.show_closed,
    )


if __name__ == "__main__":
    main()
