def calculate_public_key(base, private_key, prime):
    return pow(base, private_key) % prime


def decrypt():
    prime      = 101
    base       = 37
    alice_key  = 100
    bob_key    = 32

    alice_public = calculate_public_key(base, alice_key, prime)
    bob_public   = calculate_public_key(base, bob_key,   prime)
    shared_key   = calculate_public_key(bob_public, alice_key, prime)

    cipher = [
        2337, 10332, 9348, 8118, 10332, 738, 10701, 11316, 8487, 8118, 9963, 9963, 1599, 10455, 7995, 7995, 861, 861, 1353, 492, 8487, 8364, 861, 10701, 11070, 9963, 2706, 8610, 10209, 10332, 1476, 10701, 2214, 984, 10578, 10209, 10701, 10209, 861, 1968
    ]

    step1_chars = []
    for number in cipher:
        original_ord = number // (shared_key * 123)
        step1_chars.append(chr(original_ord))
    step1_text = "".join(step1_chars)

    xor_key    = "netsec"
    key_length = len(xor_key)

    xored_back = ""
    for i, char in enumerate(step1_text):
        key_char    = xor_key[i % key_length]
        plain_char  = chr(ord(char) ^ ord(key_char))
        xored_back += plain_char

    final_flag = xored_back[::-1]

    print(f"Shared Key : {shared_key}")
    print(f"Flag       : {final_flag}")


decrypt()
