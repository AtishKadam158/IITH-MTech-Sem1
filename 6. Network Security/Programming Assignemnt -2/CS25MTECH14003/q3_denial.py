#!/usr/bin/env python3
"""
Q3: DNSSEC Authenticated Denial of Existence
Detects NXDOMAIN / NODATA and validates NSEC / NSEC3 proofs using Q1 module.
"""

import dns.resolver
import dns.message
import dns.query
import dns.rdatatype
import dns.name
import dns.flags
import dns.dnssec
import hashlib
import sys

sys.path.insert(0, ".")
from q1_dnssec_validator import (
    get_dnskey_records,
    verify_rrsig_with_dnskey,
)

TIMEOUT     = 5
RESOLVER_IP = "8.8.8.8"


def query_with_dnssec(domain: str, rdtype_text: str,
                      nameserver: str = RESOLVER_IP) -> dns.message.Message:
    rdtype  = dns.rdatatype.from_text(rdtype_text)
    qname   = dns.name.from_text(domain)
    request = dns.message.make_query(
        qname, rdtype,
        use_edns=True,
        ednsflags=dns.flags.DO,
        payload=4096
    )
    request.flags |= dns.flags.CD

    try:
        response = dns.query.udp(request, nameserver, timeout=TIMEOUT)
        if response.flags & dns.flags.TC:
            response = dns.query.tcp(request, nameserver, timeout=TIMEOUT)
        return response
    except Exception as e:
        raise RuntimeError(f"Query failed: {e}")


def detect_denial_type(response: dns.message.Message,
                       domain: str, rdtype_text: str) -> str:
    rcode  = dns.rcode.to_text(response.rcode())
    rdtype = dns.rdatatype.from_text(rdtype_text)
    qname  = dns.name.from_text(domain)

    if rcode == "NXDOMAIN":
        return "NXDOMAIN"

    for rrset in response.answer:
        if rrset.name == qname and rrset.rdtype == rdtype:
            return "EXISTS"
    return "NODATA"


def rdtype_in_nsec_bitmap(nsec_rdata, rdtype: int) -> bool:
    for window_num, bitmap in nsec_rdata.windows:
        window_base = window_num * 256
        for byte_idx, byte_val in enumerate(bitmap):
            for bit in range(8):
                if byte_val & (0x80 >> bit):
                    if window_base + byte_idx * 8 + bit == rdtype:
                        return True
    return False


def extract_nsec(response: dns.message.Message):
    pairs     = []
    authority = response.authority
    for rrset in authority:
        if rrset.rdtype != dns.rdatatype.NSEC:
            continue
        rrsig_rrset = None
        for rs in authority:
            if rs.rdtype == dns.rdatatype.RRSIG and rs.name == rrset.name:
                for rr in rs:
                    if rr.type_covered == dns.rdatatype.NSEC:
                        rrsig_rrset = rs
                        break
        pairs.append((rrset, rrsig_rrset))
    return pairs


def extract_nsec3(response: dns.message.Message):
    pairs     = []
    authority = response.authority
    for rrset in authority:
        if rrset.rdtype != dns.rdatatype.NSEC3:
            continue
        rrsig_rrset = None
        for rs in authority:
            if rs.rdtype == dns.rdatatype.RRSIG and rs.name == rrset.name:
                for rr in rs:
                    if rr.type_covered == dns.rdatatype.NSEC3:
                        rrsig_rrset = rs
                        break
        pairs.append((rrset, rrsig_rrset))
    return pairs


def validate_nsec_coverage(nsec_rrset, qname: dns.name.Name,
                           rdtype_text: str, denial_type: str) -> tuple:
    rdtype = dns.rdatatype.from_text(rdtype_text)

    for nsec_rdata in nsec_rrset:
        owner     = nsec_rrset.name
        next_name = nsec_rdata.next

        if denial_type == "NXDOMAIN":
            covers = (owner < qname and
                      (next_name > qname or next_name == dns.name.root))
            if not covers and owner > next_name:
                covers = qname > owner or qname < next_name
            if covers:
                return True, f"NSEC [{owner} … {next_name}] covers {qname}"

        else:
            if owner == qname:
                if not rdtype_in_nsec_bitmap(nsec_rdata, rdtype):
                    return True, (f"NSEC covers {qname} "
                                  f"and type {rdtype_text} absent from bitmap")
                else:
                    return False, (f"NSEC covers {qname} "
                                   f"but type {rdtype_text} IS in bitmap (record exists?)")

    return False, "NSEC does not cover query name"


def nsec3_hash(name: dns.name.Name, salt: bytes, iterations: int) -> bytes:
    wire   = name.canonicalize().to_wire()
    digest = wire
    for _ in range(iterations + 1):
        digest = hashlib.sha1(digest + salt).digest()
    return digest


def b32_extended(data: bytes) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUV"
    result   = []
    acc, bits = 0, 0
    for byte in data:
        acc  = (acc << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            result.append(alphabet[(acc >> bits) & 0x1f])
    if bits > 0:
        result.append(alphabet[(acc << (5 - bits)) & 0x1f])
    return "".join(result)


def validate_nsec3_coverage(nsec3_pairs, qname: dns.name.Name, zone: str) -> tuple:
    if not nsec3_pairs:
        return False, "No NSEC3 records found"

    first_rrset, _ = nsec3_pairs[0]
    for nsec3_rdata in first_rrset:
        iterations = nsec3_rdata.iterations
        salt       = nsec3_rdata.salt
        qhash_b32  = b32_extended(nsec3_hash(qname, salt, iterations)).upper()

        for rrset, _ in nsec3_pairs:
            owner_label = rrset.name.labels[0].decode().upper()
            for rdata in rrset:
                next_hash_b32 = b32_extended(rdata.next).upper()
                if owner_label <= qhash_b32 < next_hash_b32:
                    return True, f"NSEC3 covers hash {qhash_b32[:16]}…"
                if owner_label > next_hash_b32:
                    if qhash_b32 > owner_label or qhash_b32 < next_hash_b32:
                        return True, f"NSEC3 (wrap) covers hash {qhash_b32[:16]}…"
        break

    return False, "No NSEC3 covers query name hash"


def validate_denial(domain: str, record_type: str) -> dict:
    steps  = []
    result = {"exists": None, "proof_type": None, "proof_valid": False,
              "steps": steps, "error": None}

    try:
        response = query_with_dnssec(domain, record_type)
    except Exception as e:
        result["error"] = str(e)
        print(f"ERROR: {e}")
        return result

    denial_type = detect_denial_type(response, domain, record_type)
    rcode       = dns.rcode.to_text(response.rcode())
    steps.append(f"Response RCODE: {rcode}  Denial type: {denial_type}")

    if denial_type == "EXISTS":
        result["exists"] = True
        steps.append("Record exists – denial check not applicable")
        _print_denial_summary(domain, record_type, "EXISTS", None, False, steps)
        return result

    result["exists"] = False

    qname = dns.name.from_text(domain)
    zone  = None

    for rrset in response.authority:
        if rrset.rdtype == dns.rdatatype.SOA:
            zone = rrset.name.to_text().rstrip(".")
            break
    if not zone:
        for rrset in response.authority:
            if rrset.rdtype in (dns.rdatatype.NSEC, dns.rdatatype.NSEC3):
                z = rrset.name.to_text().rstrip(".")
                if zone is None or len(z.split(".")) < len(zone.split(".")):
                    zone = z
    if not zone:
        parts = domain.rstrip(".").split(".")
        zone  = ".".join(parts[-2:]) if len(parts) >= 2 else domain

    try:
        dnskey_rrset, _ = get_dnskey_records(zone)
    except Exception as e:
        result["error"] = f"DNSKEY fetch failed: {e}"
        print(f"ERROR: DNSKEY fetch failed: {e}")
        return result

    if not dnskey_rrset:
        result["error"] = "No DNSKEY found"
        print("ERROR: No DNSKEY found")
        return result
    steps.append(f"DNSKEY retrieved for {zone}")

    nsec_pairs  = extract_nsec(response)
    nsec3_pairs = extract_nsec3(response)

    if nsec_pairs:
        result["proof_type"] = "NSEC"
        all_sigs_ok = True
        any_covers  = False

        for nsec_rrset, rrsig_rrset in nsec_pairs:
            owner = nsec_rrset.name
            if rrsig_rrset:
                ok, detail = verify_rrsig_with_dnskey(
                    nsec_rrset, rrsig_rrset, dnskey_rrset)
                if ok:
                    steps.append(f"NSEC RRSIG verified for {owner}")
                else:
                    steps.append(f"NSEC RRSIG FAILED for {owner}: {detail}")
                    all_sigs_ok = False
            else:
                steps.append(f"WARNING: No RRSIG for NSEC at {owner}")

            ok, reason = validate_nsec_coverage(
                nsec_rrset, qname, record_type, denial_type)
            if ok:
                any_covers = True
                steps.append(f"NSEC coverage: {reason}")
            else:
                steps.append(f"NSEC coverage (no match): {reason}")

        result["proof_valid"] = all_sigs_ok and any_covers

    elif nsec3_pairs:
        result["proof_type"] = "NSEC3"
        all_sigs_ok = True

        for nsec3_rrset, rrsig_rrset in nsec3_pairs:
            owner = nsec3_rrset.name
            if rrsig_rrset:
                ok, detail = verify_rrsig_with_dnskey(
                    nsec3_rrset, rrsig_rrset, dnskey_rrset)
                if ok:
                    steps.append(f"NSEC3 RRSIG verified for {owner}")
                else:
                    steps.append(f"NSEC3 RRSIG FAILED: {detail}")
                    all_sigs_ok = False
            else:
                steps.append(f"WARNING: No RRSIG for NSEC3 at {owner}")

        ok, reason = validate_nsec3_coverage(nsec3_pairs, qname, zone)
        steps.append(f"NSEC3 coverage: {reason}")
        result["proof_valid"] = all_sigs_ok and ok

    else:
        steps.append("No NSEC/NSEC3 denial proof in response")
        result["proof_type"] = "NONE"

    _print_denial_summary(domain, record_type, denial_type,
                          result["proof_type"], result["proof_valid"], steps)
    return result


def _print_denial_summary(domain, record_type, denial_type,
                          proof_type, proof_valid, steps):
    print(f"\n{'='*60}")
    print(f"  Query  : {domain} {record_type}")
    if denial_type == "EXISTS":
        print("  Result : EXISTS")
    else:
        print(f"  Result : DOES NOT EXIST ({denial_type})")
        if proof_type and proof_type != "NONE":
            status = "✅ VALID" if proof_valid else "❌ INVALID"
            print(f"  Proof  : {status} ({proof_type})")
        else:
            print("  Proof  : NONE")
    print("  Steps:")
    for s in steps:
        print(f"    • {s}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 q3_denial.py <domain> <record_type>")
        print("Examples:")
        print("  python3 q3_denial.py mail.example.com TXT")
        print("  python3 q3_denial.py nonexistent.example.com A")
        print("  python3 q3_denial.py example.com TXT")
        print("  python3 q3_denial.py thisdomaindoesnotexist99999.com A")
        sys.exit(1)

    domain      = sys.argv[1]
    record_type = sys.argv[2].upper()
    validate_denial(domain, record_type)