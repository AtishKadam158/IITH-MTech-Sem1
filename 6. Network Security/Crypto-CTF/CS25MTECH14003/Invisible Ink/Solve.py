def decode_invisible_ink(filename):
    message = ""

    with open(filename, "r") as f:
        for line in f:
            binary = ""

            for char in line:
                if char == " ":
                    binary += "0"
                elif char == "\t":
                    binary += "1"

            if len(binary) > 4:
                ascii_value = int(binary, 2)
                message += chr(ascii_value)

    return message


flag = decode_invisible_ink("flag.enc")
print(flag)
