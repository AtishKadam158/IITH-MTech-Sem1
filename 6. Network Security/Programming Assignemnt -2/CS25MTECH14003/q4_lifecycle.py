#!/usr/bin/env python3
"""
Q4: DNSSEC Key Lifecycle Analysis
Detects KSK/ZSK rollover states, DS mismatches, and key coexistence.
Uses Q1 module functions.
"""

import dns.resolver
import dns.rdatatype
import dns.name
import dns.flags
import dns.dnssec
import sys
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, ".")
from q1_dnssec_validator import (
    get_dnskey_records,
    get_ds_records,
    compute_ds_digest,
    verify_rrsig_with_dnskey,
    verify_dnskey_with_ds,
)

RESOLVER_IP = "8.8.8.8"


ALGORITHM_NAMES = {
    1:  "RSA/MD5",
    3:  "DSA/SHA1",
    5:  "RSA/SHA1",
    6:  "DSA-NSEC3-SHA1",
    7:  "RSASHA1-NSEC3-SHA1",
    8:  "RSA/SHA-256",
    10: "RSA/SHA-512",
    12: "GOST R 34.10-2001",
    13: "ECDSA/P-256/SHA-256",
    14: "ECDSA/P-384/SHA-384",
    15: "Ed25519",
    16: "Ed448",
}

def key_type(dnskey_rdata) -> str:
    return "KSK" if (dnskey_rdata.flags & 0x0001) else "ZSK"

def key_tag(dnskey_rdata) -> int:
    return dns.dnssec.key_id(dnskey_rdata)

def algorithm_name(alg: int) -> str:
    return ALGORITHM_NAMES.get(alg, f"Algorithm-{alg}")


def get_rrsig_expiry(zone: str) -> list:
    resolver = dns.resolver.Resolver()
    resolver.use_edns(0, dns.flags.DO, 4096)
    resolver.nameservers = [RESOLVER_IP]
    sigs = []
    try:
        answer = resolver.resolve(zone, dns.rdatatype.DNSKEY, raise_on_no_answer=False)
        for rrset in answer.response.answer:
            if rrset.rdtype == dns.rdatatype.RRSIG:
                for rr in rrset:
                    sigs.append({
                        "type_covered": dns.rdatatype.to_text(rr.type_covered),
                        "algorithm":    algorithm_name(rr.algorithm),
                        "key_tag":      rr.key_tag,
                        "inception":    datetime.fromtimestamp(rr.inception,  tz=timezone.utc),
                        "expiration":   datetime.fromtimestamp(rr.expiration, tz=timezone.utc),
                        "signer":       rr.signer.to_text(),
                    })
    except Exception:
        pass
    return sigs


def analyze_ds_matching(dnskey_rrset, ds_rrset, zone_name: dns.name.Name) -> dict:
    analysis = {}
    if not ds_rrset:
        return analysis

    for ds in ds_rrset:
        ds_tag  = ds.key_tag
        matched = False
        matched_ktype = None

        for dnskey in (dnskey_rrset or []):
            try:
                computed = compute_ds_digest(zone_name, dnskey, ds.digest_type)
                if computed == ds.digest:
                    matched       = True
                    matched_ktype = key_type(dnskey)
                    break
            except Exception:
                continue

        analysis[ds_tag] = {
            "matched":     matched,
            "algorithm":   algorithm_name(ds.algorithm),
            "digest_type": ds.digest_type,
            "key_type":    matched_ktype,
        }
    return analysis


def detect_rollover_state(keys_by_type: dict, ds_analysis: dict,
                          observations: list) -> str:
    ksks = keys_by_type.get("KSK", [])
    zsks = keys_by_type.get("ZSK", [])

    ds_matched_tags   = [t for t, i in ds_analysis.items() if i["matched"]]
    ds_unmatched_tags = [t for t, i in ds_analysis.items() if not i["matched"]]

    if len(ksks) > 1:
        observations.append(f"Old + new KSK present (tags: {ksks})")
        if ds_matched_tags and ds_unmatched_tags:
            observations.append(
                f"DS matches old KSK only (tag {ds_matched_tags[0]}); "
                f"new KSK (tag {ds_unmatched_tags[0]}) not yet in parent DS"
            )
            return "KSK Rollover in Progress"
        elif len(ds_matched_tags) > 1:
            observations.append(
                f"DS matches multiple KSKs (tags {ds_matched_tags}) – "
                "both old and new keys trusted by parent"
            )
            return "KSK Rollover in Progress (DS updated, old key still published)"
        elif not ds_matched_tags and ds_analysis:
            observations.append(
                "DS does not match any current KSK – "
                "parent DS may point to a retired key"
            )
            return "KSK Rollover – DS Mismatch"
        return "KSK Rollover in Progress"

    if ds_analysis and not ds_matched_tags:
        observations.append(
            "DS record in parent does NOT match the current KSK – "
            "possible incomplete rollover or misconfiguration"
        )
        return "DS Mismatch – parent DS does not match any current KSK"

    if len(zsks) > 1:
        observations.append(
            f"Multiple ZSKs coexisting (tags: {zsks}) – "
            "ZSK rollover in progress (pre-publish or double-signature phase)"
        )
        observations.append(
            "Active ZSK: the one whose tag appears in answer RRSIGs; "
            "others are pre-published (new) or retiring (old)"
        )
        return "ZSK Rollover in Progress"

    return "Stable – no active rollover detected"


def analyze_key_lifecycle(domain: str) -> dict:
    observations = []
    result = {
        "domain":       domain,
        "status":       "Unknown",
        "keys":         [],
        "ds_records":   [],
        "rrsig_info":   [],
        "ds_analysis":  {},
        "observations": observations,
    }

    zone_name = dns.name.from_text(domain)

    # ── 1. DNSKEY ─────────────────────────────────────────
    try:
        dnskey_rrset, dnskey_rrsig = get_dnskey_records(domain)
    except Exception as e:
        result["status"] = f"ERROR: {e}"
        print(f"ERROR: {e}")
        return result

    if not dnskey_rrset:
        result["status"] = "No DNSKEY records (unsigned zone)"
        observations.append("Zone is unsigned – no DNSSEC deployed")
        _print_lifecycle_summary(result)
        return result

    keys_by_type = {"KSK": [], "ZSK": []}
    for dnskey in dnskey_rrset:
        ktype = key_type(dnskey)
        ktag  = key_tag(dnskey)
        kalg  = algorithm_name(dnskey.algorithm)
        kbits = len(dnskey.key) * 8

        result["keys"].append({
            "tag":       ktag,
            "type":      ktype,
            "algorithm": kalg,
            "key_bits":  kbits,
            "flags":     dnskey.flags,
        })
        keys_by_type[ktype].append(ktag)

    if len(keys_by_type["KSK"]) == 0:
        observations.append("WARNING: No KSK (SEP flag) found in DNSKEY RRset")

    # ── 2. DS records ─────────────────────────────────────
    ds_rrset = get_ds_records(domain)
    if ds_rrset:
        for ds in ds_rrset:
            result["ds_records"].append({
                "key_tag":     ds.key_tag,
                "algorithm":   algorithm_name(ds.algorithm),
                "digest_type": ds.digest_type,
            })
    else:
        observations.append(
            "No DS record in parent – chain of trust not established from parent")

    # ── 3. RRSIG validity windows ─────────────────────────
    sigs = get_rrsig_expiry(domain)
    now  = datetime.now(tz=timezone.utc)

    for sig in sigs:
        result["rrsig_info"].append(sig)
        time_left = sig["expiration"] - now
        expired   = time_left.total_seconds() < 0
        soon      = 0 < time_left.total_seconds() < 7 * 86400

        if expired:
            observations.append(
                f"RRSIG({sig['type_covered']}) tag={sig['key_tag']} is EXPIRED – "
                "zone signatures need immediate renewal")
        elif soon:
            days = int(time_left.total_seconds() // 86400)
            observations.append(
                f"RRSIG({sig['type_covered']}) tag={sig['key_tag']} "
                f"expires in {days} day(s) – renewal imminent")

    # ── 4. DS → DNSKEY matching ───────────────────────────
    ds_analysis = analyze_ds_matching(dnskey_rrset, ds_rrset, zone_name)
    result["ds_analysis"] = ds_analysis

    for ds_tag, info in ds_analysis.items():
        if not info["matched"]:
            observations.append(
                f"DS tag={ds_tag} does not match any current DNSKEY "
                "– DS mismatch or pending update")

    # ── 5. Rollover status ────────────────────────────────
    status = detect_rollover_state(keys_by_type, ds_analysis, observations)
    result["status"] = status

    if not observations:
        observations.append(
            "No anomalies detected – zone appears normally configured")

    _print_lifecycle_summary(result)
    return result


def _print_lifecycle_summary(res: dict):
    print(f"\n{'='*60}")
    print(f"  Domain      : {res['domain']}")
    print(f"  Status      : {res['status']}")
    print(f"  Observations:")
    for obs in res["observations"]:
        print(f"    - {obs}")

    print(f"\n  Keys ({len(res['keys'])} total):")
    for k in res["keys"]:
        print(f"    {k['type']}  tag={k['tag']}  alg={k['algorithm']}"
              f"  ~{k['key_bits']}bit  flags={k['flags']}")

    print(f"\n  DS Records ({len(res['ds_records'])} total):")
    for ds in res["ds_records"]:
        matched = any(
            tag == ds["key_tag"] and info["matched"]
            for tag, info in res["ds_analysis"].items()
        )
        m = "✅ matched" if matched else "❌ unmatched"
        print(f"    tag={ds['key_tag']}  alg={ds['algorithm']}"
              f"  dtype={ds['digest_type']}  [{m}]")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    domains = (sys.argv[1:]
               if len(sys.argv) > 1
               else ["example.com", "cloudflare.com", "ietf.org"])

    for domain in domains:
        analyze_key_lifecycle(domain)
        print()