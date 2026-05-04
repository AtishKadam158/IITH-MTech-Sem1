import string

ciphertext = "xa6903{i078953462i345o05i62vev0j73743hh}"  #<----- I copied my encrypted flag here
key = "VIGENERE"

alphabet = string.ascii_lowercase

plaintext = ""
key_index = 0

for char in ciphertext:
    if char.lower() in alphabet:
        shift = alphabet.index(key[key_index % len(key)].lower())
        char_index = alphabet.index(char.lower())
        decrypted_char = alphabet[(char_index - shift) % 26]
        plaintext += decrypted_char
        key_index += 1
    else:
        plaintext += char

print(plaintext)
