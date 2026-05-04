#!/usr/bin/env python3
import argparse
import csv
import logging
import os
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime

try:
    from scapy.all import ARP, Ether, sniff, conf, srp
except ImportError:
    print("Scapy not found. Install it with: sudo pip install scapy --break-system-packages")
    sys.exit(1)


def banner():
    print("=" * 54)
    print("         ARP SPOOF DETECTOR ")
    print("  Monitors ARP replies for inconsistencies")
    print("=" * 54)
    print()


def setup_logger(logfile: str) -> logging.Logger:
    logger = logging.getLogger("arp_detector")

    # Reset completely
    logger.handlers = []
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    # FILE HANDLER
    try:
        fh = logging.FileHandler(logfile, mode='a', delay=False)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        # FIX 1: Disable buffering on the file handler stream
        fh.stream.reconfigure(line_buffering=True)
        logger.addHandler(fh)
    except Exception as e:
        print(f"[LOG ERROR] FileHandler failed: {e}")

    # CONSOLE HANDLER
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    print(f"[DEBUG] Logging to: {os.path.abspath(logfile)}")
    return logger


# CSV event log
class EventLogger:
    """Appends suspicious events to a CSV file for easy post-analysis."""

    FIELDS = ["timestamp", "alert_type", "src_ip", "claimed_mac", "known_mac", "interface"]

    def __init__(self, csvfile: str):
        self.csvfile = csvfile
        self._closed = False
        self._init_csv()

    def _init_csv(self):
        write_header = not os.path.exists(self.csvfile) or os.path.getsize(self.csvfile) == 0
        self._fh = open(self.csvfile, "a", newline="", buffering=1)
        self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDS)
        if write_header:
            self._writer.writeheader()
            self._fh.flush()

    def log(self, alert_type, src_ip, claimed_mac, known_mac, iface):
        if self._closed:
            return
        row = {
            "timestamp"   : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "alert_type"  : alert_type,
            "src_ip"      : src_ip,
            "claimed_mac" : claimed_mac,
            "known_mac"   : known_mac,
            "interface"   : iface,
        }
        self._writer.writerow(row)
        self._fh.flush()  
    def close(self):
        if not self._closed:
            self._closed = True
            self._fh.flush()
            self._fh.close()


# core detector
class ARPSpoofDetector:

    GRATUITOUS_WINDOW = 10  # seconds
    GRATUITOUS_THRESH = 5   # replies per window before alerting

    def __init__(self, iface, gateway_ip, gateway_mac, logger, event_logger, verbose=False):
        self.iface         = iface
        self.gateway_ip    = gateway_ip
        self.gateway_mac   = gateway_mac.lower() if gateway_mac else ""
        self.logger        = logger
        self.event_logger  = event_logger
        self.verbose       = verbose
        self.arp_table     = {}
        self.gratuitous_ts = defaultdict(list)
        self.packets_seen  = 0
        self.alerts_raised = 0

        if self.gateway_ip and self.gateway_mac:
            self.arp_table[self.gateway_ip] = self.gateway_mac
            print(f"Gateway pre-loaded: {gateway_ip} -> {gateway_mac}")

    def _alert(self, alert_type, msg, src_ip="", claimed_mac="", known_mac=""):
        self.alerts_raised += 1
        ts = datetime.now().strftime("%H:%M:%S")

        print(f"\n{'=' * 60}")
        print(f"  !! ALERT #{self.alerts_raised}  [{ts}]  {alert_type}")
        print(f"{'=' * 60}")
        print(f"  {msg}")
        if src_ip:      print(f"  Source IP   : {src_ip}")
        if claimed_mac: print(f"  Claimed MAC : {claimed_mac}")
        if known_mac:   print(f"  Known MAC   : {known_mac}")
        print()

        self.logger.warning(f"[{alert_type}] {msg} | src={src_ip} claimed={claimed_mac} known={known_mac}")
        self.event_logger.log(alert_type, src_ip, claimed_mac, known_mac, self.iface)

    def process_packet(self, pkt):
        if not pkt.haslayer(ARP):
            return

        arp     = pkt[ARP]
        eth     = pkt[Ether] if pkt.haslayer(Ether) else None
        op      = arp.op
        src_ip  = arp.psrc
        src_mac = arp.hwsrc.lower()
        dst_ip  = arp.pdst
        eth_src = eth.src.lower() if eth else src_mac

        self.packets_seen += 1

        if self.verbose:
            op_str = "reply" if op == 2 else "request"
            print(f"[PKT #{self.packets_seen}] ARP {op_str}: {src_ip} -> {dst_ip}  MAC {src_mac}")

        if op != 2:
            if op == 1 and src_ip == dst_ip:
                self._check_gratuitous(src_ip, src_mac)
            return

        # Check 1: Ethernet MAC != ARP sender MAC
        if eth and eth_src != src_mac:
            self._alert(
                "LAYER MISMATCH",
                "Ethernet source MAC differs from ARP sender MAC -- possible spoofing",
                src_ip, src_mac, eth_src
            )

        # Check 2: Gratuitous ARP flood
        if src_ip == dst_ip or dst_ip in ("0.0.0.0", ""):
            self._check_gratuitous(src_ip, src_mac)

        # Check 3: Broadcast reply
        if eth and eth.dst.lower() == "ff:ff:ff:ff:ff:ff":
            self._alert(
                "BROADCAST REPLY",
                "ARP reply sent to broadcast address -- uncommon, may indicate spoofing",
                src_ip, src_mac, ""
            )

        # Check 4: Gateway impersonation
        if (self.gateway_ip and self.gateway_mac
                and src_ip == self.gateway_ip
                and src_mac != self.gateway_mac):
            self._alert(
                "GATEWAY IMPERSONATION",
                f"Someone is claiming to be the gateway ({self.gateway_ip})!",
                src_ip, src_mac, self.gateway_mac
            )

        # Check 5: MAC change
        if src_ip in self.arp_table:
            known_mac = self.arp_table[src_ip]
            if known_mac != src_mac:
                self._alert(
                    "MAC CHANGE",
                    f"IP {src_ip} has changed its MAC address -- ARP spoofing suspected!",
                    src_ip, src_mac, known_mac
                )
                self.arp_table[src_ip] = src_mac
        else:
            self.arp_table[src_ip] = src_mac
            self.logger.info(f"Learned: {src_ip} -> {src_mac}")
            if self.verbose:
                print(f"  Learned {src_ip} -> {src_mac}")

    def _check_gratuitous(self, src_ip, src_mac):
        now = time.time()
        ts_list = self.gratuitous_ts[src_ip]
        ts_list[:] = [t for t in ts_list if now - t < self.GRATUITOUS_WINDOW]
        ts_list.append(now)

        if len(ts_list) >= self.GRATUITOUS_THRESH:
            self._alert(
                "GRATUITOUS ARP FLOOD",
                f"{src_ip} sent {len(ts_list)} gratuitous ARPs in {self.GRATUITOUS_WINDOW}s -- possible ARP cache poisoning",
                src_ip, src_mac, self.arp_table.get(src_ip, "unknown")
            )
            self.gratuitous_ts[src_ip] = []

    def start(self):
        print(f"Sniffing ARP on interface: {self.iface}")
        print(f"Press Ctrl+C to stop.\n")
        try:
            sniff(iface=self.iface, filter="arp", prn=self.process_packet, store=False)
        except KeyboardInterrupt:
            pass

    def summary(self):
        print(f"\n{'─' * 50}")
        print("  SESSION SUMMARY")
        print(f"{'─' * 50}")
        print(f"  Packets seen  : {self.packets_seen}")
        print(f"  Alerts raised : {self.alerts_raised}")
        print(f"  IPs in table  : {len(self.arp_table)}")
        print(f"\n  Current ARP Table:")
        for ip, mac in sorted(self.arp_table.items()):
            marker = " <- GATEWAY" if ip == self.gateway_ip else ""
            print(f"    {ip:18s} -> {mac}{marker}")
        print()


# helpers
def get_gateway_info():
    """Try to auto-detect the default gateway IP and MAC."""
    import subprocess, re

    gw_ip = ""
    try:
        out = subprocess.check_output(["ip", "route"], text=True)
        m = re.search(r"default via (\S+)", out)
        if m:
            gw_ip = m.group(1)
    except Exception:
        pass

    gw_mac = ""
    if gw_ip:
        try:
            answered, _ = srp(
                Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=gw_ip),
                timeout=2, verbose=False
            )
            if answered:
                gw_mac = answered[0][1][ARP].hwsrc.lower()
        except Exception:
            pass

    return gw_ip, gw_mac


# CLI
def parse_args():
    parser = argparse.ArgumentParser(
        description="ARP Spoof Detector -- monitors ARP replies for inconsistencies"
    )
    parser.add_argument("-i", "--interface",   default=conf.iface,          help="Network interface to monitor (default: auto)")
    parser.add_argument("-g", "--gateway",     default="",                  help="Gateway IP (auto-detected if omitted)")
    parser.add_argument("-m", "--gateway-mac", default="",                  help="Gateway MAC (auto-detected if omitted)")
    parser.add_argument("-l", "--logfile",     default="arp_detector.log",  help="Log file path")
    parser.add_argument("-c", "--csvfile",     default="arp_alerts.csv",    help="CSV event file path")
    parser.add_argument("-v", "--verbose",     action="store_true",         help="Print every ARP packet seen")
    return parser.parse_args()


# main
def main():
    if os.geteuid() != 0:
        print("[!] This script must be run as root (sudo).")
        sys.exit(1)

    banner()
    args = parse_args()

    gw_ip  = args.gateway
    gw_mac = args.gateway_mac

    if not gw_ip or not gw_mac:
        print("Auto-detecting gateway ...")
        detected_ip, detected_mac = get_gateway_info()
        gw_ip  = gw_ip  or detected_ip
        gw_mac = gw_mac or detected_mac
        if gw_ip:  print(f"[+] Gateway IP  : {gw_ip}")
        if gw_mac: print(f"[+] Gateway MAC : {gw_mac}")
        if not gw_ip:
            print("[!] Could not detect gateway. Use -g <IP> to set manually.")

    logger       = setup_logger(args.logfile)
    event_logger = EventLogger(args.csvfile)

    print(f"\nLogging events to : {args.logfile}")
    print(f"CSV alerts to     : {args.csvfile}\n")

    logger.info(f"Detector started on {args.interface} | gateway={gw_ip} mac={gw_mac}")

    detector = ARPSpoofDetector(
        iface        = args.interface,
        gateway_ip   = gw_ip,
        gateway_mac  = gw_mac,
        logger       = logger,
        event_logger = event_logger,
        verbose      = args.verbose
    )

    _shutting_down = [False]

    def _shutdown(sig, frame):
        if _shutting_down[0]:
            return
        _shutting_down[0] = True
        print("\nStopping detector ...")
        detector.summary()
        logger.info("Detector stopped by user")
        event_logger.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    detector.start()

    if not _shutting_down[0]:
        _shutting_down[0] = True
        detector.summary()
        logger.info("Detector stopped normally")
        event_logger.close()


if __name__ == "__main__":
    main()