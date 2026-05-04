#!/usr/bin/env python3
import dns.resolver
import dns.dnssec
import dns.name
import dns.rdatatype
import dns.rdataset
import dns.rrset
import dns.rdata
import hashlib
import struct
import base64
import sys
from datetime import datetime, timezone
from typing import Optional

def compute_ds_digest(owner_name: dns.name.Name, dnskey_rdata, digest_type: int) -> bytes:
    owner_wire = owner_name.canonicalize().to_wire()

    flags     = struct.pack("!H", dnskey_rdata.flags)
    protocol  = struct.pack("!B", dnskey_rdata.protocol)
    algorithm = struct.pack("!B", dnskey_rdata.algorithm)
    pubkey    = dnskey_rdata.key

    data = owner_wire + flags + protocol + algorithm + pubkey

    if digest_type == 1:
        return hashlib.sha1(data).digest()
    elif digest_type == 2:
        return hashlib.sha256(data).digest()
    elif digest_type == 4:
        return hashlib.sha384(data).digest()
    else:
        raise ValueError(f"Unsupported DS digest type: {digest_type}")


#  Step 1: Retrieve answer records + RRSIG
def get_answer_records(domain: str, record_type: str):
    resolver = dns.resolver.Resolver()
    resolver.use_edns(0, dns.flags.DO, 4096)
    resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

    rdtype = dns.rdatatype.from_text(record_type)
    answer = resolver.resolve(domain, rdtype, raise_on_no_answer=False)

    target_rrset = None
    rrsig_rrset  = None

    for rrset in answer.response.answer:
        if rrset.rdtype == rdtype and rrset.name == dns.name.from_text(domain):
            target_rrset = rrset
        if rrset.rdtype == dns.rdatatype.RRSIG and rrset.name == dns.name.from_text(domain):
            for rrsig in rrset:
                if rrsig.type_covered == rdtype:
                    rrsig_rrset = rrset
                    break

    return target_rrset, rrsig_rrset


# Helper: extract the signing zone from an rrsig_rrset
def get_signing_zone(rrsig_rrset, rdtype) -> Optional[str]:
    if not rrsig_rrset:
        return None
    for rr in rrsig_rrset:
        if rr.type_covered == rdtype:
            return rr.signer.to_text().rstrip(".")
    return None

#  Step 2: Retrieve DNSKEY records for a zone
def get_dnskey_records(zone: str):
    resolver = dns.resolver.Resolver()
    resolver.use_edns(0, dns.flags.DO, 4096)
    resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

    dnskey_rrset = None
    rrsig_rrset  = None

    try:
        answer = resolver.resolve(zone, dns.rdatatype.DNSKEY, raise_on_no_answer=False)
        for rrset in answer.response.answer:
            if rrset.rdtype == dns.rdatatype.DNSKEY:
                dnskey_rrset = rrset
            if rrset.rdtype == dns.rdatatype.RRSIG:
                for rrsig in rrset:
                    if rrsig.type_covered == dns.rdatatype.DNSKEY:
                        rrsig_rrset = rrset
                        break
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, Exception):
        pass   # unsigned zone — callers check for None

    return dnskey_rrset, rrsig_rrset


#  Step 3: Retrieve DS record from parent zone
def get_ds_records(domain: str):
    resolver = dns.resolver.Resolver()
    resolver.use_edns(0, dns.flags.DO, 4096)
    resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

    try:
        answer = resolver.resolve(domain, dns.rdatatype.DS, raise_on_no_answer=False)
        for rrset in answer.response.answer:
            if rrset.rdtype == dns.rdatatype.DS:
                return rrset
        for rrset in answer.response.authority:
            if rrset.rdtype == dns.rdatatype.DS:
                return rrset
    except Exception:
        pass
    return None


#  Step 4: Verify RRSIG using DNSKEY (ZSK)
def verify_rrsig_with_dnskey(rrset, rrsig_rrset, dnskey_rrset):
    if not rrset or not rrsig_rrset or not dnskey_rrset:
        return False, "Missing rrset, rrsig, or dnskey"

    zone_name = dnskey_rrset.name

    for rrsig in rrsig_rrset:
        if rrsig.signer != zone_name:
            continue
        for dnskey in dnskey_rrset:
            try:
                dns.dnssec.validate_rrsig(
                    rrset, rrsig, {zone_name: dnskey_rrset})
                key_tag_val = dns.dnssec.key_id(dnskey)
                ktype = "KSK" if (dnskey.flags & 0x0001) else "ZSK"
                return True, f"{key_tag_val} ({ktype})"
            except (dns.dnssec.ValidationFailure, Exception):
                continue

    # Last-resort: let dnspython pick the key itself
    try:
        dns.dnssec.validate(rrset, rrsig_rrset, {zone_name: dnskey_rrset})
        return True, "auto-selected key"
    except Exception:
        pass

    return False, "No matching DNSKEY validated the RRSIG"


#  Step 5: Verify DNSKEY using DS
def verify_dnskey_with_ds(dnskey_rrset, ds_rrset):
    if not dnskey_rrset or not ds_rrset:
        return False, "Missing DNSKEY or DS records"

    zone_name = dnskey_rrset.name

    # First pass: prefer KSKs (SEP bit, flags & 0x0001)
    for ds in ds_rrset:
        for dnskey in dnskey_rrset:
            if not (dnskey.flags & 0x0001):
                continue
            try:
                computed = compute_ds_digest(zone_name, dnskey, ds.digest_type)
                if computed == ds.digest:
                    return True, dns.dnssec.key_id(dnskey)
            except Exception:
                continue

    # Second pass: try all keys (some zones publish ZSK-only DS)
    for ds in ds_rrset:
        for dnskey in dnskey_rrset:
            try:
                computed = compute_ds_digest(zone_name, dnskey, ds.digest_type)
                if computed == ds.digest:
                    ktag  = dns.dnssec.key_id(dnskey)
                    ktype = "KSK" if (dnskey.flags & 0x0001) else "ZSK"
                    return True, f"{ktag} ({ktype})"
            except Exception:
                continue

    # Third pass: key_tag / algorithm pre-filter then digest check
    for ds in ds_rrset:
        for dnskey in dnskey_rrset:
            if (dns.dnssec.key_id(dnskey) == ds.key_tag
                    and dnskey.algorithm == ds.algorithm):
                try:
                    computed = compute_ds_digest(zone_name, dnskey, ds.digest_type)
                    if computed == ds.digest:
                        return True, dns.dnssec.key_id(dnskey)
                except Exception:
                    continue

    return False, "No DS record matched any DNSKEY in RRset"


#  Main validation orchestration

def validate_dnssec(domain: str, record_type: str, verbose: bool = True) -> dict:
    steps  = []
    result = {"valid": False, "signed": True, "steps": steps, "error": None}

    # ── 1. Answer records ──────────────────────────────────
    #[1] Querying answer records …"
    try:
        answer_rrset, answer_rrsig = get_answer_records(domain, record_type)
    except Exception as e:
        result["error"] = f"Failed to query {record_type} records: {e}"
        print(f"    ERROR: {result['error']}")
        return result

    if answer_rrset:
        ips = [r.to_text() for r in answer_rrset]
        steps.append(f"Answer {record_type} records retrieved: {ips}")
    else:
        print("    No answer records found (NXDOMAIN or NODATA).")
        steps.append(f"No {record_type} records found")

    if answer_rrsig:
        steps.append("RRSIG for answer record retrieved")
    else:
        steps.append("INFO: No RRSIG for answer record (possible unsigned zone)")

    # ── 2. DNSKEY ─────────────────────────────────────────
    rdtype_int   = dns.rdatatype.from_text(record_type)
    signing_zone = get_signing_zone(answer_rrsig, rdtype_int) or domain
    if signing_zone != domain:
        print(f"[2] RRSIG signer zone: {signing_zone} (differs from queried domain)")
    #[2] Retrieving DNSKEY records …

    try:
        dnskey_rrset, dnskey_rrsig = get_dnskey_records(signing_zone)
    except Exception as e:
        result["error"] = f"Failed to retrieve DNSKEY: {e}"
        print(f"    ERROR: {result['error']}")
        return result

    if dnskey_rrset:
        key_count = len(list(dnskey_rrset))
        steps.append(f"DNSKEY retrieved ({key_count} key(s))")
    else:
        # ── Unsigned zone: exit gracefully ─────────────────
        result["signed"] = False
        result["valid"]  = False
        msg = "No DNSKEY found — zone is unsigned / DNSSEC not deployed."
        result["error"] = msg
        print(f"    INFO: {msg}")
        steps.append(f"INFO: {msg}")
        _print_summary(domain, record_type, False, steps, signed=False)
        return result

    # ── 3. DS record ──────────────────────────────────────
    #[3] Retrieving DS record from parent …"
    ds_rrset = get_ds_records(signing_zone)
    if ds_rrset:
        steps.append(f"DS record retrieved from parent ({len(list(ds_rrset))} entry(s))")
    else:
        print("    INFO: No DS record found (unsigned delegation or root).")
        steps.append("INFO: No DS record in parent (unsigned delegation)")

    # ── 4. Verify RRSIG over answer using DNSKEY ──────────
    # [4] Verifying RRSIG over answer using DNSKEY (ZSK) …
    if answer_rrset and answer_rrsig and dnskey_rrset:
        ok, detail = verify_rrsig_with_dnskey(answer_rrset, answer_rrsig, dnskey_rrset)
        if ok:
            steps.append(f"RRSIG verified using ZSK (key tag: {detail})")
        else:
            result["error"] = f"RRSIG verification failed: {detail}"
            print(f"    FAIL: {result['error']}")
            steps.append(f"RRSIG verification FAILED: {detail}")
            _print_summary(domain, record_type, False, steps)
            return result
    else:
        msg = "Skipped RRSIG verification (missing RRSIG or DNSKEY)."
        print(f"    {msg}")
        steps.append(msg)

    # ── 5. Verify DNSKEY against DS (KSK chain) ───────────
    # [5] Verifying DNSKEY against DS record (KSK chain) …
    if dnskey_rrset and ds_rrset:
        ok, detail = verify_dnskey_with_ds(dnskey_rrset, ds_rrset)
        if ok:
            steps.append(f"DS matched parent (KSK key tag: {detail})")
        else:
            result["error"] = f"DS/DNSKEY mismatch: {detail}"
            print(f"    FAIL: {result['error']}")
            steps.append(f"DS/DNSKEY verification FAILED: {detail}")
            _print_summary(domain, record_type, False, steps)
            return result
    else:
        steps.append("DS chain verification skipped (no DS record found)")

    # ── All checks passed ─────────────────────────────────
    result["valid"] = True
    _print_summary(domain, record_type, True, steps)
    return result


def _print_summary(domain, record_type, valid, steps, signed=True):
    print(f"\n{'─'*55}")
    print(f"  Domain : {domain}")
    print(f"  Record : {record_type}")
    if not signed:
        status = "⚠️  NOT SIGNED (unsigned zone)"
    else:
        status = "✅ VALID" if valid else "❌ INVALID"
    print(f"  DNSSEC Validation: {status}")
    print("  Steps:")
    for s in steps:
        print(f"    • {s}")
    print(f"{'─'*55}\n")


#  CLI entry-point
if __name__ == "__main__":
    domain      = sys.argv[1]
    record_type = sys.argv[2].upper()
    validate_dnssec(domain, record_type)