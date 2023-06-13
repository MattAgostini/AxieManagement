import logging
import requests

from web3 import Web3

import backend.encryption.encryption_util as EncryptUtil
import backend.transaction.utilities as utilities
from backend.parse_accounts import Account, AccountType
from backend.transaction.payments import Payment


class Claim(utilities.Transaction):
    def __init__(self, account: Account, item_type: utilities.ItemType = utilities.ItemType.SLP):
        self.account = account
        self.ronin = account.public_addr.replace("ronin:", "0x")
        self.item_type = item_type
        self.amount = 0
        self.signed_claim_tx = None
        self._build_signed_claim_tx()
        super().__init__()

    def get_signed_transaction(self):
        return self.signed_claim_tx

    def _build_signed_claim_tx(self):
        token = utilities.generate_access_token(self.account)
        if not token:
            logging.critical(f"Skipping claiming, we could not get the access token for account {str(self.account)}")
            return None
        headers = {
            "User-Agent": utilities.USER_AGENT,
            "authorization": f"Bearer {token}"
        }
        if self.item_type == utilities.ItemType.mAXS:
            request_type = "GET"
            url = f"https://game-api-pre.skymavis.com/v1/players/{self.ronin}/items/{self.item_type}"
        else:
            request_type = "POST"
            url = f"https://game-api-pre.skymavis.com/v1/players/me/items/{self.item_type}/claim"
        try:
            response = requests.request(request_type, url, headers=headers)
            print(response)
            response_json = response.json()
            print(response_json)
            signature = response_json["blockchainRelated"].get("signature")

            if not signature or not signature["signature"]:
                logging.critical(f"Account {str(self.account)} had no signature in blockchainRelated")
                return None
            if not response_json['clientID'] or response_json['clientID'] != self.ronin:
                logging.info(f"Claim for account ({str(self.account)}) had to be skipped")
                return None

        except Exception as e:
            logging.critical(f"Error executing token claim for account {str(self.account)}: {e}")
            return None

        self.amount = response_json['rawTotal'] - response_json['rawClaimableTotal']
        self.nonce = utilities.get_nonce(self.account)
        _, contract_call = utilities.get_contract(self.item_type)

        if self.item_type == utilities.ItemType.mAXS:
            claim_tx = contract_call.functions.claim(
                Web3.toChecksumAddress(self.ronin),
                self.item_type,
                signature['amount'],
                signature['timestamp'],
                signature['signature']
            ).buildTransaction({
                'gas': 300000,
                "gasPrice": Web3.toWei(1, "gwei"),
                'nonce': self.nonce
            })
        else:
            claim_tx = contract_call.functions.checkpoint(
                Web3.toChecksumAddress(self.ronin),
                signature['amount'],
                signature['timestamp'],
                signature['signature']
            ).buildTransaction({
                'gas': 300000,
                "gasPrice": Web3.toWei(1, "gwei"),
                'nonce': self.nonce
            })
        private_key = EncryptUtil.get_private_key(self.account.seed_id, self.account.seed_account_num)
        self.signed_claim_tx = utilities.w3.eth.account.sign_transaction(claim_tx, private_key)

    def __str__(self):
        return f"Claim from ({str(self.account)}) for {self.amount} {self.item_type.name}"


def prepare_and_execute_claim(accounts: list[Account], item_type: utilities.ItemType = utilities.ItemType.SLP):
    claims = []
    for account in accounts:
        claim = Claim(account, item_type)
        if claim.get_signed_transaction() is None: continue
        claims.append(claim)
    utilities.process_transactions(claims)
    utilities.log_failed_transactions(claims)


def get_slp_data(account: Account, item_type: utilities.ItemType = utilities.ItemType.SLP, attempts: int = 0) -> dict:
    url = f"https://game-api-pre.skymavis.com/v1/players/{account.public_addr.replace('ronin:', '0x')}/items/{item_type}"
    try:
        response = requests.request("GET", url, headers={"User-Agent": utilities.USER_AGENT})
        response_json = response.json()
        if not response_json['clientID'] or response_json['clientID'] != (account.public_addr.replace('ronin:', '0x')): raise Exception
        return response_json
    except Exception:
        if attempts < 3:
            return get_slp_data(account, attempts + 1)
        else:
            logging.critical(f"Failed to get SLP data for {str(account)}")
            return None

def get_token_data(account: Account, item_type: utilities.ItemType = utilities.ItemType.SLP, attempts: int = 0) -> dict:
    url = f"https://game-api-pre.skymavis.com/v1/players/{account.public_addr.replace('ronin:', '0x')}/items/{item_type}"
    try:
        response = requests.request("GET", url, headers={"User-Agent": utilities.USER_AGENT})
        response_json = response.json()
        if not response_json['clientID'] or response_json['clientID'] != (account.public_addr.replace('ronin:', '0x')): raise Exception
        return response_json
    except Exception:
        if attempts < 3:
            return get_slp_data(account, attempts + 1)
        else:
            logging.critical(f"Failed to get {item_type.name} data for {str(account)}")
            return None