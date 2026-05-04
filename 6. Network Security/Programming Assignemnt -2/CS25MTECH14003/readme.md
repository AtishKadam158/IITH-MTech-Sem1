# DNSSEC Validator — Assignment 2

A Python-based DNSSEC validation toolkit covering recursive resolution, authenticated denial of existence, key lifecycle analysis, and tamper detection.

---

## Project Structure

```
.
├── q1_dnssec_validator.py   ← Core library (imported by all others)
├── q2_resolver.py           ← Recursive resolution + per-hop validation
├── q3_denial.py             ← NSEC/NSEC3 authenticated denial
├── q4_lifecycle.py          ← Key rollover & expiry analysis
└── q5_tamper.py             ← Tamper simulation & detection (SEED Lab)
```

> All modules depend on `q1_dnssec_validator.py`. Run it standalone to verify core validation works before testing others.

---

## Requirements

```bash
pip install dnspython
```

---

## Task 1 — Core DNSSEC Validator (`q1_dnssec_validator.py`)

Validates DNSSEC signatures for a given domain and record type. Fetches DNSKEY, verifies RRSIG, and checks the DS chain.

### Usage

```bash
python3 q1_dnssec_validator.py <domain> <record_type>
```

### Examples

```bash
python3 q1_dnssec_validator.py cloudflare.com A
python3 q1_dnssec_validator.py cloudflare.com AAAA
python3 q1_dnssec_validator.py google.com MX
python3 q1_dnssec_validator.py example.com A
```

### Expected Output

```
============================================================
  Domain : cloudflare.com   Type: A
  Result : ✅ VALID
  Steps  :
    • DNSKEY retrieved (3 keys)
    • RRSIG verified with key tag 2371
    • DS record matches KSK
============================================================
```

---

## Task 2 — Recursive Resolver (`q2_resolver.py`)

Performs iterative DNS resolution from the root, validating DNSSEC at each hop in the chain (root → TLD → authoritative).

### Usage

```bash
python3 q2_resolver.py <domain> <record_type>
```

### Examples

```bash
python3 q2_resolver.py example.com A
python3 q2_resolver.py cloudflare.com AAAA
python3 q2_resolver.py ietf.org MX
```

### Expected Output

```
============================================================
  Resolving: example.com  Type: A
============================================================
  [.] Root → com. (NS referral, DNSSEC OK)
  [.] com. → example.com. (NS referral, DNSSEC OK)
  [✅] example.com. → 93.184.216.34 (DNSSEC VALID)
------------------------------------------------------------
  Final Answer : 93.184.216.34
  Chain Status : ✅ FULLY VALIDATED
============================================================
```

---

## Task 3 — Authenticated Denial of Existence (`q3_denial.py`)

Detects NXDOMAIN / NODATA responses and validates NSEC or NSEC3 denial-of-existence proofs.

### Usage

```bash
python3 q3_denial.py <domain> <record_type>
```

### Examples

```bash
# NODATA — name exists but record type does not (NSEC proof)
python3 q3_denial.py nonexistent.example.com A

# NXDOMAIN — name does not exist (NSEC3 proof)
python3 q3_denial.py thisdomaindoesnotexist99999.com A

# EXISTS — record is present, no denial proof needed
python3 q3_denial.py example.com TXT
```

### Expected Output

```
============================================================
  Query  : thisdomaindoesnotexist99999.com A
  Result : DOES NOT EXIST (NXDOMAIN)
  Proof  : ✅ VALID (NSEC3)
  Steps:
    • Response RCODE: NXDOMAIN  Denial type: NXDOMAIN
    • DNSKEY retrieved for com
    • NSEC3 RRSIG verified for CK0POJMG874LJREF7EFN8430QVIT8BSM.com.
    • NSEC3 RRSIG verified for 6AJC3HAB4R417PL2KUS0U88HHUVQ23H3.com.
    • NSEC3 coverage: NSEC3 covers hash 6AJC53R42F1KH942…
============================================================
```

---

## Task 4 — Key Lifecycle Analysis (`q4_lifecycle.py`)

Detects KSK/ZSK rollover states, DS mismatches, key coexistence, and RRSIG expiry windows.

### Usage

```bash
python3 q4_lifecycle.py <domain> [domain2 ...]
```

### Examples

```bash
python3 q4_lifecycle.py cloudflare.com ietf.org
python3 q4_lifecycle.py example.com
```

### Expected Output

```
============================================================
  Domain      : cloudflare.com
  Status      : ZSK Rollover in Progress
  Observations:
    - Multiple ZSKs coexisting (tags: [9776, 34505, 36315]) – ZSK rollover in progress (pre-publish or double-signature phase)
    - Active ZSK: the one whose tag appears in answer RRSIGs; others are pre-published (new) or retiring (old)

  Keys (4 total):
    KSK  tag=2371  alg=ECDSA/P-256/SHA-256  ~512bit  flags=257
    ZSK  tag=9776  alg=ECDSA/P-256/SHA-256  ~512bit  flags=256
    ZSK  tag=34505  alg=ECDSA/P-256/SHA-256  ~512bit  flags=256
    ZSK  tag=36315  alg=ECDSA/P-256/SHA-256  ~512bit  flags=256

  DS Records (1 total):
    tag=2371  alg=ECDSA/P-256/SHA-256  dtype=2  [✅ matched]
============================================================
```

---

## Task 5 — Tamper Detection (`q5_tamper.py`) — SEED Lab

Uses the SEED Lab Docker environment to simulate a real DNS record tampering attack and verify that the DNSSEC validator correctly detects it.

### Lab Environment

| Component         | IP / Container             |
|-------------------|----------------------------|
| Local DNS Server  | `10.9.0.53` (`local-dns`)  |
| Authoritative NS  | `10.9.0.65` (`example-edu`)|
| Target record     | `www.example.edu A 1.2.3.5`|

---

### Step-by-Step Instructions

#### Step 1 — Start the Lab

```bash
cd ~/Desktop/NS_ASS2/seed-labs/category-network/DNSSEC/Labsetup
docker compose up -d
```

---

#### Step 2 — Query BEFORE Tampering

```bash
dig @10.9.0.53 www.example.edu A +dnssec +multiline
```


---

#### Step 3 — Validate BEFORE Tampering

```bash
cd ~/Desktop/NS_ASS2/New\ code
python3 q5_tamper.py before
```



---

#### Step 4 — Enter Container and Tamper the Zone File

```bash
docker exec -it example-edu-10.9.0.65 bash
nano /etc/bind/example.edu.db.signed
```

Use `Ctrl+W` → search `1.2.3.5` → change the A record:

```
# Before
www   259200   IN  A  1.2.3.5

# After
www   259200   IN  A  1.2.3.99
```

> Leave the RRSIG line completely untouched.

Save and exit:

```
Ctrl+O → Enter    (save)
Ctrl+X            (exit nano)
```

Reload BIND and exit the container:

```bash
rndc reload example.edu
exit
```

---

#### Step 5 — Flush DNS Cache

```bash
docker exec -it local-dns-10.9.0.53 bash
rndc flush
exit
```

---

#### Step 6 — Confirm Tamper Took Effect

```bash
dig @10.9.0.65 www.example.edu A
```


---

#### Step 7 — Query AFTER Tampering via Local DNS

```bash
dig @10.9.0.53 www.example.edu A +dnssec +multiline
```



---

#### Step 8 — Validate AFTER Tampering

```bash
cd ~/Desktop/NS_ASS2/New\ code
python3 q5_tamper.py after
```

> 📸 **Screenshot 5** — Expect `DNSSEC Validation: INVALID` with the failure point identified.

### Expected Output (after tampering)

```
============================================================
  Domain : www.example.edu   Type: A
  Result : ❌ INVALID
  Failure: RRSIG verification failed — record data does not match signature
  Steps  :
    • DNSKEY retrieved from 10.9.0.53
    • A record returned: 1.2.3.99
    • RRSIG present (covers A, key tag=XXXX)
    • ❌ Signature mismatch — data was tampered
============================================================
```

---

#### Step 9 — Restore the Zone

```bash
docker exec -it example-edu-10.9.0.65 bash
nano /etc/bind/example.edu.db.signed
```

Change `1.2.3.99` back to `1.2.3.5`, then reload:

```bash
rndc reload example.edu
exit
```

Flush cache:

```bash
docker exec -it local-dns-10.9.0.53 bash
rndc flush
exit
```

Verify restored:

```bash
dig @10.9.0.53 www.example.edu A +dnssec +multiline
```

---

## Quick Reference

| Task | Script | What it tests |
|------|--------|---------------|
| 1 | `q1_dnssec_validator.py` | Signature + DS chain validation |
| 2 | `q2_resolver.py` | Iterative resolution with per-hop DNSSEC |
| 3 | `q3_denial.py` | NSEC / NSEC3 denial-of-existence proofs |
| 4 | `q4_lifecycle.py` | KSK/ZSK rollover & RRSIG expiry |
| 5 | `q5_tamper.py` | Live tamper detection via SEED Lab |