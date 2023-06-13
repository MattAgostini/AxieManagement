import binascii
import getpass
import pathlib

from Cryptodome import Random
from Cryptodome.Cipher import AES
from Cryptodome.Protocol.KDF import PBKDF2
from Cryptodome.Util import Counter
from eth_account import Account as ETHAccount
from web3 import Web3

import backend.parse_env as EnvVar

ETHAccount.enable_unaudited_hdwallet_features()


key = None
key_bytes = 32
block_size = AES.block_size


def encrypt(key, plaintext, iv=None):
    assert len(key) == key_bytes

    # create random IV if one not provided
    if iv is None:
        iv = Random.new().read(block_size)

    # convert IV to integer
    iv_int = int(binascii.hexlify(iv), 16)

    # create counter using the IV
    ctr = Counter.new(block_size * 8, initial_value=iv_int)

    # create cipher object
    aes = AES.new(key, AES.MODE_CTR, counter=ctr)

    # encrypt the string and return the IV/ciphertext
    ciphertext = aes.encrypt(plaintext)
    return iv, ciphertext


def decrypt(key, iv, ciphertext):
    assert len(key) == key_bytes

    # convert IV to integer and create counter using the IV
    iv_int = int(binascii.hexlify(iv), 16)
    ctr = Counter.new(block_size * 8, initial_value=iv_int)

    # create cipher object
    aes = AES.new(key, AES.MODE_CTR, counter=ctr)

    # decrypt ciphertext and return the decrypted binary string
    plaintext = aes.decrypt(ciphertext)
    return plaintext


def check_password_salt():
    if EnvVar.PASSWORD_SALT == "" or len(EnvVar.PASSWORD_SALT) > 1024:
        print("Invaid password salt detected. Please check your .env file\n")


def generate_key_from_password(password: str) -> bytes:
    check_password_salt()
    return PBKDF2(password.encode("utf8"), EnvVar.PASSWORD_SALT, key_bytes)


def set_password(first_attempt: bool = False) -> bytes:
    check_password_salt()

    if first_attempt:
        print(
            "Please enter the password you will use to launch the software.\n"
            "Note, the password field is hidden so it will not display what you type."
        )
    password = getpass.getpass("Password to encrypt your seeds: ").strip()
    password2 = getpass.getpass("Confirm password: ").strip()

    # check that password entry matches
    if password != password2:
        print("Passwords do not match.\n")
        set_password(True)

    print("\nGenerating key...\n")
    return generate_key_from_password(password)


def login():
    global key
    password = getpass.getpass("Please enter your password: ").strip()
    key = generate_key_from_password(password)
    if not verify_password(): exit()

def verify_password() -> bool:
    try:
        import backend.encryption.seeds as seeds
        with open(pathlib.Path(__file__).parent.resolve() / "iv.dat", "rb") as f:
            iv = f.read()
        decrypt(key, iv, seeds.seed_list[0]).decode("utf8")
        return True
    except ModuleNotFoundError:
        print("Could not find seeds\n")
    except FileNotFoundError:
        print("Could not find iv.dat file\n")
    except UnicodeDecodeError:
        print("Could not verify password\n")
    return False


def write_seeds_to_file(encrypted_seeds: list[bytes]):
    with open(pathlib.Path(__file__).parent.resolve() / "seeds.py", "w") as f:
        f.write("seed_list: list[str] = [\n")
        for i in range(0, len(encrypted_seeds)):
            if i < len(encrypted_seeds) - 1: f.write(f"\t{encrypted_seeds[i]},\n")
            else: f.write(f"\t{encrypted_seeds[i]}\n")
        f.write("]")


def add_seed(key: bytes):
    import backend.encryption.seeds as seeds

    words = {}
    with open(pathlib.Path(__file__).parent.resolve() / "english.txt") as f:
        for a in f:
            a = a.replace("\n", "")
            words[a] = a

    while True:
        seedIn = input(f"Input seed phrase: ")
        if not seedIn.replace(" ", "").isalpha():
            print("Invalid Characters detected. Please try entering again.")
            continue
        if len(seedIn.split(" ")) != 12:
            print("Seed phrases are supposed to be 12 words long. Yours is " + str(len(seedIn.split(" "))) + " words long. Please try entering again.")
            continue
        if not seedIn.replace(" ", "").islower():
            print("Seed phrases are supposed to be all lowercase. Yours is not. Please try entering again.")
            continue
        validWord = True
        for a in seedIn.split(" "):
            if a not in words:
                print(a + " is not a valid word for bip39 keys. Please try entering again.")
                validWord = False
        if not validWord:
            continue
        break

    with open(pathlib.Path(__file__).parent.resolve() / "iv.dat", "rb") as f:
        iv = f.read()

    _, ciphertext = encrypt(key, seedIn.encode("utf8"), iv)
    assert seedIn == decrypt(key, iv, ciphertext).decode("utf8"), "Failure encrypting seeds. IV data mismatch"
    seeds.seed_list.append(ciphertext)
    write_seeds_to_file(seeds.seed_list)
    print("Seeds saved successfully\n")

def encrypt_seeds(key: bytes):
    words = {}
    with open(pathlib.Path(__file__).parent.resolve() / "english.txt") as f:
        for a in f:
            a = a.replace("\n", "")
            words[a] = a

    count = 0
    seeds = []
    print(
        "Enter the seeds in the order you reference them for scholars (seed_id '0' first).\n"
        "Your seeds will be in memory for the brief duration of encryption and verification,\n"
        "then they will only be stored encrypted on disk.\n\n"

        "Each line should be 12 words separated by a single space.\n"
        "When you've entered your last seed phrase, press enter on a blank input to continue.\n"
    )
    while True:
        seedIn = input(f"Input seed phrase {count}: ")
        seedIn = seedIn.strip()

        if seedIn == "":
            print("\nDetected blank input, moving on to seed encryption.\n")
            break
        if not seedIn.replace(" ", "").isalpha():
            print("Invalid Characters detected. Not adding to the list. Please try entering again.")
            continue
        if len(seedIn.split(" ")) != 12:
            print("Seed phrases are supposed to be 12 words long. Yours is " + str(len(seedIn.split(" "))) + " words long. Not adding to the list. Please try entering again.")
            continue
        if not seedIn.replace(" ", "").islower():
            print("Seed phrases are supposed to be all lowercase. Yours is not. Not adding to the list. Please try entering again.")
            continue
        validWord = True
        for a in seedIn.split(" "):
            if a not in words:
                print(a + " is not a valid word for bip39 keys. Not adding to the list. Please try entering again.")
                validWord = False
        if not validWord:
            continue
        seeds.append(seedIn)
        count += 1

    # generate IV data
    iv = Random.new().read(AES.block_size)
    encSeeds = []

    for i in range(0, len(seeds)):
        (iv, ciphertext) = encrypt(key, seeds[i].encode("utf8"), iv)
        encSeeds.append(ciphertext)

    print(
        "Writing IV (Initialization Vector) data to file iv.dat. This file is used in the encryption process.\n"
        "If you lose this file or your password you will need to re-run this script to newly encrypt your seeds."
    )
    with open(pathlib.Path(__file__).parent.resolve() / "iv.dat", "wb") as f:
        f.write(iv)

    print("Testing decryption on each seed to insure proper encryption.\n")
    with open(pathlib.Path(__file__).parent.resolve() / "iv.dat", "rb") as f:
        iv = f.read()

        for i in range(0, len(encSeeds)):
            out = decrypt(key, iv, encSeeds[i]).decode("utf8")
            if out == seeds[i]:
                print(f"Verified encryption of seed {i}.")
            else:
                print(f"Failed to verify encryption of seed {i}. Something is wrong with the password or IV data.")
                exit()

    print("Writing encrypted seeds to seeds.py file.\n")
    write_seeds_to_file(encSeeds)
    
    print("Encryption process complete!")


def get_private_key(seed_id: int, account_num: int) -> str:
    _, private_key = get_secrets(seed_id, account_num)
    return private_key

def get_ronin_address(seed_id: int, account_num: int) -> str:
    ronin_address, _ = get_secrets(seed_id, account_num)
    return ronin_address

def get_secrets(seed_id: int, account_num: int):
    import backend.encryption.seeds as seeds

    with open(pathlib.Path(__file__).parent.resolve() / "iv.dat", "rb") as f:
        iv = f.read()
    seed = decrypt(key, iv, seeds.seed_list[seed_id]).decode("utf8")
    account = get_eth_account_from_mnemonic(seed, account_num)
    return str(account.address.lower()).replace("0x", "ronin:"), Web3.toHex(account.key)

def get_eth_account_from_mnemonic(seed: str, account_num: int):
    return ETHAccount.from_mnemonic(seed, "", "m/44'/60'/0'/0/" + str(int(account_num)))

def get_seed_count() -> int:
    import backend.encryption.seeds as seeds
    return len(seeds.seed_list)
