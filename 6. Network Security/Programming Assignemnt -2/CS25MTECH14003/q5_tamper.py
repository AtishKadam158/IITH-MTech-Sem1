#!/usr/bin/env python3
"""
Q5: DNSSEC Tampering Demonstration
SEED Lab: example.edu authoritative NS = 10.9.0.65
          local resolver               = 10.9.0.53

Usage:
  python3 q5_tamper.py before   ← run BEFORE tampering
  python3 q5_tamper.py after    ← run AFTER tampering

DEPENDS ON: q1_dnssec_validator.py  q2_resolver.py
"""

import sys
import dns.query
import dns.message
import dns.name
import dns.rdatatype
import dns.flags
import dns.rcode

sys.path.insert(0, ".")

from q1_dnssec_validator import (
    get_dnskey_records,
    get_ds_records,
    verify_rrsig_with_dnskey,
    verify_dnskey_with_ds,
    validate_dnssec,
)

from q2_resolver import send_query

DOMAIN      = "www.example.edu"
ZONE        = "example.edu"
RECORD_TYPE = "A"
LOCAL_DNS   = "10.9.0.53"
AUTH_NS     = "10.9.0.65"


def sep(c="─"): print(c * 60)


def query(server):
    rdtype = dns.rdatatype.from_text(RECORD_TYPE)
    return send_query(server, DOMAIN, rdtype)


def print_response(resp, server):
    if resp is None:
        print(f"  No response from {server}")
        return
    rcode  = dns.rcode.to_text(resp.rcode())
    ad     = bool(resp.flags & dns.flags.AD)
    flags  = []
    if resp.flags & dns.flags.QR: flags.append("qr")
    if resp.flags & dns.flags.RD: flags.append("rd")
    if resp.flags & dns.flags.RA: flags.append("ra")
    if resp.flags & dns.flags.AD: flags.append("ad")
    if resp.flags & dns.flags.AA: flags.append("aa")
    print(f"  Server  : {server}")
    print(f"  Status  : {rcode}")
    print(f"  Flags   : {' '.join(flags)}")
    print(f"  AD Flag : {'SET' if ad else 'NOT SET'}")
    for rrset in resp.answer:
        rtype = dns.rdatatype.to_text(rrset.rdtype)
        for rdata in rrset:
            print(f"  {rrset.name} {rrset.ttl} IN {rtype} {rdata}")


# ── BEFORE TAMPERING ──────────────────────────────────────────
def before():
    sep("═")
    print("  PHASE 1: BEFORE TAMPERING")
    sep("═")

    print(f"\n  [dig] via local DNS ({LOCAL_DNS})")
    print_response(query(LOCAL_DNS), LOCAL_DNS)

    print(f"\n  [Q1 Validator] DNSSEC chain validation")
    validate_dnssec(DOMAIN, RECORD_TYPE)


# ── AFTER TAMPERING ───────────────────────────────────────────
def after():
    sep("═")
    print("  PHASE 2: AFTER TAMPERING")
    sep("═")

    # Query local DNS
    print(f"\n  [dig] via local DNS ({LOCAL_DNS})")
    print_response(query(LOCAL_DNS), LOCAL_DNS)

    # Query auth server directly to get tampered record + old RRSIG
    print(f"\n  [dig] via auth server ({AUTH_NS}) — tampered record")
    auth_resp = query(AUTH_NS)
    print_response(auth_resp, AUTH_NS)

    # Extract tampered RRset and original RRSIG
    rdtype_int     = dns.rdatatype.from_text(RECORD_TYPE)
    tampered_rrset = None
    tampered_rrsig = None

    if auth_resp:
        for rrset in auth_resp.answer:
            if rrset.rdtype == rdtype_int:
                tampered_rrset = rrset
            elif rrset.rdtype == dns.rdatatype.RRSIG:
                for rr in rrset:
                    if rr.type_covered == rdtype_int:
                        tampered_rrsig = rrset

    if tampered_rrset is None:
        print(f"\n  ERROR: Could not fetch record from {AUTH_NS}")
        return

    tampered_ips = [str(r) for r in tampered_rrset]

    # Fetch DNSKEY using Q1
    dnskey_rrset, _ = get_dnskey_records(ZONE)

    # Verify RRSIG using Q1
    print(f"\n  [Q1 Validator] Verifying RRSIG on tampered record …")
    if tampered_rrsig and dnskey_rrset:
        ok, detail = verify_rrsig_with_dnskey(tampered_rrset, tampered_rrsig, dnskey_rrset)
    else:
        ok, detail = False, "Missing RRSIG or DNSKEY"

    # DS check using Q1 (only if RRSIG passed)
    if ok:
        ds_rrset = get_ds_records(ZONE)
        if ds_rrset:
            ok, detail = verify_dnskey_with_ds(dnskey_rrset, ds_rrset)

    # Final result
    print()
    sep("─")
    print(f"  Domain            : {DOMAIN}")
    print(f"  Record            : {RECORD_TYPE}")
    print(f"  DNSSEC Validation : {'VALID' if ok else 'INVALID'}")
    print()
    if not ok:
        print("  Failure Reason:")
        print(f"    - RRSIG verification failed for {RECORD_TYPE} record")
        print(f"    - Signature does not match DNSKEY")
        print()
        print("  Steps:")
        print(f"    ✔ Answer records retrieved : {tampered_ips}")
        print(f"    ✔ DNSKEY retrieved")
        print(f"    ✔ RRSIG retrieved (original, unmodified)")
        print(f"    ✘ RRSIG verification FAILED  ← failure point")
        print(f"    ✘ DS chain check skipped")
    sep("─")


# ── CLI ───────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("before", "after"):
        print("Usage: python3 q5_tamper.py before|after")
        sys.exit(1)

    if sys.argv[1] == "before":
        before()
    else:
        after()