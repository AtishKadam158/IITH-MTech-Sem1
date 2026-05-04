#!/usr/bin/env python3
import dns.resolver
import dns.message
import dns.query
import dns.rdatatype
import dns.rdataset
import dns.name
import dns.flags
import dns.dnssec
import dns.exception
import sys
import socket
import random
from typing import Optional, List, Tuple

# Import Q1 module from same directory
sys.path.insert(0, ".")
from q1_dnssec_validator import (
    get_dnskey_records,
    get_ds_records,
    verify_rrsig_with_dnskey,
    verify_dnskey_with_ds,
    compute_ds_digest,
)


ROOT_SERVERS = [
    "198.41.0.4",    # a.root-servers.net
    "199.9.14.201",  # b.root-servers.net
    "192.33.4.12",   # c.root-servers.net
]

# Public resolvers used as last-resort fallback
FALLBACK_RESOLVERS = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]

TIMEOUT = 5   # seconds per UDP query


def send_query(nameserver_ip: str, qname: str, rdtype: int,
               timeout: int = TIMEOUT,
               use_edns: bool = True) -> Optional[dns.message.Message]:
  
    name = dns.name.from_text(qname)

    def _udp(req):
        try:
            resp = dns.query.udp(req, nameserver_ip, timeout=timeout)
            if resp.flags & dns.flags.TC:           # truncated → upgrade to TCP
                resp = dns.query.tcp(req, nameserver_ip, timeout=timeout)
            return resp
        except Exception:
            return None

    def _tcp(req):
        try:
            return dns.query.tcp(req, nameserver_ip, timeout=timeout)
        except Exception:
            return None

    if use_edns:
        req_edns = dns.message.make_query(name, rdtype, use_edns=True,
                                          ednsflags=dns.flags.DO, payload=4096)
        resp = _udp(req_edns)
        if resp is not None:
            return resp
        resp = _tcp(req_edns)
        if resp is not None:
            return resp

    # Plain query (no EDNS / no DO bit) – last resort
    req_plain = dns.message.make_query(name, rdtype, use_edns=False)
    return _udp(req_plain)


def fallback_query(qname: str, rdtype: int,
                   timeout: int = TIMEOUT) -> Optional[dns.message.Message]:
    
    for ip in FALLBACK_RESOLVERS:
        resp = send_query(ip, qname, rdtype, timeout=timeout)
        if resp is not None and resp.answer:
            return resp
    return None



def extract_referral(response: dns.message.Message) -> Tuple[List[str], str]:
    delegated_zone = None
    for rrset in response.authority:
        if rrset.rdtype == dns.rdatatype.NS:
            delegated_zone = rrset.name.to_text()
            break

    ips = []
    for rrset in response.additional:
        if rrset.rdtype == dns.rdatatype.A:
            for rdata in rrset:
                ips.append(rdata.to_text())

    return ips, delegated_zone


def extract_ns_names_from_authority(response: dns.message.Message) -> Tuple[List[str], str]:
    """
    Return (ns_hostnames, delegated_zone) from the authority section.
    """
    for rrset in response.authority:
        if rrset.rdtype == dns.rdatatype.NS:
            zone = rrset.name.to_text()
            names = [rdata.to_text() for rdata in rrset]
            return names, zone
    return [], ""


def validate_zone_hop(zone: str, path_log: list) -> Tuple[bool, str]:
    zone_q = zone.rstrip(".")
    if not zone_q:
        zone_q = "."   # root

    try:
        dnskey_rrset, dnskey_rrsig = get_dnskey_records(zone_q)
    except Exception as e:
        return False, f"DNSKEY fetch failed for {zone}: {e}"

    if not dnskey_rrset:
        return False, f"No DNSKEY for {zone}"

    if dnskey_rrsig:
        ok, detail = verify_rrsig_with_dnskey(dnskey_rrset, dnskey_rrsig, dnskey_rrset)
        if ok:
            path_log.append(f"  [{zone}] DNSKEY self-sig OK (key tag {detail})")
        else:
            path_log.append(f"  [{zone}] DNSKEY self-sig FAILED: {detail}")

    ds_rrset = get_ds_records(zone_q)
    if ds_rrset:
        ok, detail = verify_dnskey_with_ds(dnskey_rrset, ds_rrset)
        if ok:
            path_log.append(f"  [{zone}] DS → DNSKEY OK (KSK tag {detail})")
            return True, f"DS chain verified for {zone}"
        else:
            path_log.append(f"  [{zone}] DS → DNSKEY FAILED: {detail}")
            return False, detail
    else:
        path_log.append(f"  [{zone}] No DS record found (unsigned delegation or root)")
        return True, f"No DS (skipped chain check) for {zone}"


def resolve_ns_to_ip(ns_hostname: str) -> List[str]:
    """Resolve an NS hostname to IPv4 addresses using the system resolver."""
    try:
        infos = socket.getaddrinfo(ns_hostname, 53, socket.AF_INET)
        return list({info[4][0] for info in infos})
    except Exception:
        return []



def _extract_answer(response: dns.message.Message,
                    rdtype: int) -> List[str]:
    results = []
    for rrset in response.answer:
        if rrset.rdtype == rdtype:
            results.extend(r.to_text() for r in rrset)
    return results

def recursive_resolve(domain: str, record_type: str = "A") -> dict:
    rdtype   = dns.rdatatype.from_text(record_type)
    path     = []
    path_log = []

    current_servers  = list(ROOT_SERVERS)
    current_zone     = "."
    dnssec_ok        = True
    final_ips        = []
    dnssec_validated = False

    # Track authoritative-zone servers separately for the fallback
    auth_zone        = None
    auth_servers     = []


    hop = 0
    answered = False

    while current_servers and hop < 25:
        hop += 1
        ns_ip = current_servers[0]

        path_log.append(f"Hop {hop}: NS={ns_ip}  zone={current_zone}")

        response = send_query(ns_ip, domain, rdtype)
        if response is None:
            path_log.append(f"  No response from {ns_ip} (UDP+TCP+plain all failed)")
            current_servers = current_servers[1:]
            continue

        rcode = dns.rcode.to_text(response.rcode())

        # ── Got an answer ──────────────────────────────────
        if response.answer:
            final_ips = _extract_answer(response, rdtype)

            # Also capture CNAMEs if the target type wasn't found
            if not final_ips:
                for rrset in response.answer:
                    if rrset.rdtype == dns.rdatatype.CNAME:
                        final_ips = [r.to_text() for r in rrset]


            path_log.append(f"  Answer: {final_ips}")

            # Validate the answer RRSIG
            rrsig_rrset = None
            for rs in response.answer:
                if rs.rdtype == dns.rdatatype.RRSIG:
                    for rr in rs:
                        if rr.type_covered == rdtype:
                            rrsig_rrset = rs
            if rrsig_rrset:
                try:
                    signing_zone = current_zone
                    for rr in rrsig_rrset:
                        if rr.type_covered == rdtype:
                            signing_zone = rr.signer.to_text().rstrip(".")
                            break
                    dnskey_rrset, _ = get_dnskey_records(signing_zone)
                    ok, detail = verify_rrsig_with_dnskey(
                        _extract_rrset_for_type(response.answer, rdtype),
                        rrsig_rrset, dnskey_rrset)
                    if ok:
                        path_log.append(
                            f"  [{signing_zone}] Answer RRSIG OK (key tag {detail})")
                        dnssec_validated = True
                    else:
                        path_log.append(
                            f"  [{signing_zone}] Answer RRSIG FAILED: {detail}")
                        dnssec_ok = False
                except Exception as e:
                    path_log.append(f"  Answer RRSIG check error: {e}")

            ok, msg = validate_zone_hop(current_zone, path_log)
            if ok:
                dnssec_validated = True
            else:
                dnssec_ok = False
                path_log.append(f"  Chain FAILED at {current_zone}: {msg}")

            if current_zone not in path:
                path.append(current_zone)
            answered = True
            break

        # ── NXDOMAIN ───────────────────────────────────────
        if rcode == "NXDOMAIN":
            path_log.append(f"  NXDOMAIN from {ns_ip}")
            answered = True
            break

        # ── Referral ───────────────────────────────────────
        glue_ips, delegated_zone = extract_referral(response)

        if not glue_ips:
            ns_names, delegated_zone = extract_ns_names_from_authority(response)
            if ns_names:
                new_ips = []
                for ns_name in ns_names:
                    resolved = resolve_ns_to_ip(ns_name)
                    new_ips.extend(resolved)
                    if new_ips:
                        break
                if new_ips:
                    glue_ips = new_ips
                    print(f"  Resolved NS {ns_names[0]} → {new_ips[:3]}")
                    path_log.append(
                        f"  NS resolution: {ns_names[0]} → {new_ips[:3]}")

        if glue_ips and delegated_zone:
            path_log.append(f"  Referral to {delegated_zone}: {glue_ips[:3]}")

            if current_zone not in path:
                path.append(current_zone)
            ok, msg = validate_zone_hop(current_zone, path_log)
            if ok:
                dnssec_validated = True
            else:
                dnssec_ok = False

            # Remember these as potential authoritative servers
            auth_zone    = delegated_zone
            auth_servers = list(glue_ips)

            current_zone    = delegated_zone
            current_servers = glue_ips
            continue

        # No referral at all – try next server
        current_servers = current_servers[1:]

    # ── Fallback to public resolver if authoritative servers all timed out ──
    if not answered and not final_ips:
        path_log.append(
            "  [FALLBACK] Direct authoritative queries failed; "
            "using public resolver 8.8.8.8/1.1.1.1 for answer")

        fb_response = fallback_query(domain, rdtype)
        if fb_response and fb_response.answer:
            final_ips = _extract_answer(fb_response, rdtype)
            if not final_ips:
                for rrset in fb_response.answer:
                    if rrset.rdtype == dns.rdatatype.CNAME:
                        final_ips = [r.to_text() for r in rrset]

            path_log.append(f"  [FALLBACK] Answer: {final_ips}")
            # DNSSEC chain was already verified up to the auth zone
            # (we just couldn't contact the auth server directly)
        else:
            print("  ❌ Fallback resolver also returned no answer.")
            path_log.append("  [FALLBACK] No answer from public resolvers either.")

    # ── Validate the final authoritative zone's DNSSEC if not done yet ──
    if auth_zone and auth_zone not in path:
        ok, msg = validate_zone_hop(auth_zone, path_log)
        if ok:
            dnssec_validated = True
        else:
            dnssec_ok = False
            path_log.append(f"  Chain FAILED at {auth_zone}: {msg}")
        path.append(auth_zone)

    # Make sure current_zone is in path
    if current_zone not in path:
        path.append(current_zone)

    path_str = " → ".join("Root" if z == "." else z for z in path)

    return {
        "domain":       domain,
        "record_type":  record_type,
        "ips":          final_ips,
        "dnssec_valid": dnssec_validated and dnssec_ok,
        "path":         path_str,
        "log":          path_log,
    }


def _extract_rrset_for_type(answer_section, rdtype):
    """Helper: return the first rrset matching rdtype from an answer section."""
    for rrset in answer_section:
        if rrset.rdtype == rdtype:
            return rrset
    return None


# ─────────────────────────────────────────────
#  Pretty-print result
# ─────────────────────────────────────────────
def print_result(res: dict):
    print(f"Query: {res['domain']}")
    
    if res['ips']:
        print(f"IP: {res['ips'][0]}")
    else:
        print("IP: (not resolved)")
    
    dnssec_status = "VERIFIED" if res['dnssec_valid'] else "FAILED"
    print(f"DNSSEC: {dnssec_status}")
    
    print("Path:")
    print(res['path'])


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 q2_resolver.py <domain> [record_type]")
        print("Examples:")
        print("  python3 q2_resolver.py example.com A")
        print("  python3 q2_resolver.py cloudflare.com AAAA")
        print("  python3 q2_resolver.py ietf.org MX")
        sys.exit(1)

    domain      = sys.argv[1]
    record_type = sys.argv[2].upper() if len(sys.argv) > 2 else "A"
    result      = recursive_resolve(domain, record_type)
    print_result(result)