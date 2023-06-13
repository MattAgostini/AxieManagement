import secrets
import time
import requests
import getpass
import secrets
import string
from backend.parse_accounts import DEFAULT_ACCOUNT_NAME

import backend.encryption.encryption_util as EncryptUtil
import backend.database.database_util as DbUtil
import backend.transaction.utilities as utilities
import backend.parse_env as EnvVar
from backend.parse_accounts import Account
from backend.encryption.captcha_solver import solve_captcha
from backend.encryption.email_reader import fetch_verification_code, test_login_info

BASE_EMAIL = EnvVar.ACCOUNT_EMAIL_FORMAT.split('+')[0] + "@" + EnvVar.ACCOUNT_EMAIL_FORMAT.split('@')[-1]

def initialize_account_creation():
    print(f"\n----- Welcome to the account creation script -----")

    password = getpass.getpass("\nPlease enter your password: ").strip()
    EncryptUtil.key = EncryptUtil.generate_key_from_password(password)
    if not EncryptUtil.verify_password(): exit()

    print(
        f"\nYour base email is {BASE_EMAIL}\n"
        "If this is incorrect, please modify your .env file"
    )

    while True:
        try:
            email_password = getpass.getpass("\nPlease enter your password for this email address: ").strip()
            test_login_info(BASE_EMAIL, email_password)
            return email_password
        except Exception as e:
            print(
                f"\nThere was an error logging into that email address: {e}\n"
                "Please make sure you input the correct password\n"
                "and that you've enabled less secure apps / IMAP.\n"
                "https://stackoverflow.com/questions/33119667/reading-gmail-is-failing-with-imap"
            )


def create_accounts(email_password: str):
    print(f"\nYou have currently have {EncryptUtil.get_seed_count()} seeds:")

    account_entries = DbUtil.account_db.get_account_entrys()
    for i in range(EncryptUtil.get_seed_count()):
        seed_entries = [entry for entry in account_entries if entry.seed_id == i]
        print(f'\tSeed {i}: {len(seed_entries)} accounts')

    print(
        "\nWould you like add seeds or accounts? Please enter the number as input\n"
        "\t1. Seeds\n"
        "\t2. Accounts\n"
        "\t3. Quit"
    )

    while True:
        response = input()
        if response == '1':
            print("Adding seeds")
            EncryptUtil.add_seed(EncryptUtil.key)
            create_accounts(email_password)
            break
        elif response == '2':
            seed_id = int(input(f"\nAdding accounts. Which seed would you like to generate accounts for?\n"))
            account_entries = DbUtil.account_db.get_account_entrys()
            seed_entries = [entry for entry in account_entries if entry.seed_id == seed_id]
            num_new_accounts = int(input(f"That seed has {len(seed_entries)} accounts. How many would you like to create?\n"))

            print(f"\n----- Creating {num_new_accounts} new accounts for Seed {seed_id} -----\n")
            for account_num in range(len(seed_entries), len(seed_entries) + num_new_accounts, 1):
                create_seed_account(seed_id, account_num, email_password)
            print(f"\n----- Done creating accounts -----\n")

            create_accounts(email_password)
            break
        elif response == '3':
            print("Exiting.")
            exit()
        else: 
            print("Invalid input.")


def create_seed_account(seed_id: int, account_num: int, email_password: str, attempts: int = 0):
    try:
        ronin_addr = EncryptUtil.get_ronin_address(seed_id, account_num)

        captcha = get_captcha_challenge()
        if captcha is None: raise Exception
        challenge = captcha['challenge']
        captcha_key = captcha['gt']

        email_str = EnvVar.ACCOUNT_EMAIL_FORMAT.format(
            seed_id=seed_id, 
            seed_account_num=account_num,
        )
        new_password = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))
        print(f'email: {email_str}\tpassword: {new_password}')

        print("Solving captcha...")
        captcha = solve_captcha(captcha_key, challenge)
        if captcha is None: raise Exception
        
        account = Account(
            seed_id=seed_id,
            seed_account_num=account_num,
            account_name=DEFAULT_ACCOUNT_NAME,
            account_types=[],
            public_addr=ronin_addr,
            discord_id=None,
            payout_addr=None,
            payout_percentage=0,
            account_email=email_str,
            account_password=new_password
        )

        token = utilities.generate_access_token(account)
        if token is None: raise Exception

        if not verify_email(account.account_email, captcha['code'], token): raise Exception

        time.sleep(10) # Wait for server to send verification email
        verification_code = fetch_verification_code(BASE_EMAIL, email_password, email_str)
        if verification_code is None: raise Exception
        verification_code = int(verification_code)
        print(f"Verification code: {verification_code}")

        if not attach_email(verification_code, new_password, token): raise Exception

        DbUtil.initialize_account(account)
        print(f"Account {account_num} created")
    except Exception as e:
        if attempts < 3:
            create_seed_account(seed_id, account_num, email_password, attempts + 1)
        else:
            print(f"There was an error creating account {account_num}. Exiting")
            exit()


def get_captcha_challenge(attempts: int = 0):
    url = "https://captcha.axieinfinity.com/api/geetest/register"
    try:
        response = requests.request("GET", url, headers={"User-Agent": utilities.USER_AGENT})
        json_data = response.json() # 'success' 'challenge' 'gt'
        return json_data
    except Exception as e:
        if attempts < 3:
            return get_captcha_challenge(attempts + 1)
        else:
            print(f"Error getting captcha challenge: {e}")
            return None


def verify_email(email: str, captcha: str, token, attempts: int = 0) -> bool:
    headers={
        "User-Agent": utilities.USER_AGENT,
        "Authorization": 'Bearer ' + token,
        "content-type": "application/json",
        "captcha-token": captcha
    }
    payload = {
        "operationName": "VerifyEmail",
        "variables": {
            "email": email
        },
        "query": "mutation VerifyEmail($email: String!) {"
        "   verifyEmail(email: $email) {"
        "       result"
        "       __typename"
        "   }"
        "}"
    }
    url = "https://graphql-gateway.axieinfinity.com/graphql"
    try:
        response = requests.request("POST", url, headers=headers, json=payload)
        json_data = response.json()
        if not json_data['data']['verifyEmail']['result']: raise Exception
        return json_data['data']['verifyEmail']['result']
    except Exception as e:
        if attempts < 3:
            return verify_email(email, captcha, token, attempts + 1)
        else:
            print(f"Error verifying email: {e}")
            return False


def attach_email(code: int, password: str, token, attempts: int = 0) -> bool:
    headers={
        "User-Agent": utilities.USER_AGENT,
        "Authorization": 'Bearer ' + token,
        "content-type": "application/json"
    }

    payload = {
        "operationName": "AttachEmail",
        "variables": {
            "code": code,
            "password": password
        },
        "query": "mutation AttachEmail($code: Int!, $password: String!) {"
        "   attachEmail(code: $code, password: $password) {"    
        "       email"
        "       activated"
        "       __typename"
        "   }"
        "}"
    }
    url = "https://graphql-gateway.axieinfinity.com/graphql"
    try:
        response = requests.request("POST", url, headers=headers, json=payload)
        json_data = response.json()
        if not json_data['data']['attachEmail']['activated']: raise Exception
        return json_data['data']['attachEmail']['activated']
    except Exception as e:
        if attempts < 3:
            return attach_email(code, password, token, attempts + 1)
        else:
            print(f"Error attaching email: {e}")
            return False
