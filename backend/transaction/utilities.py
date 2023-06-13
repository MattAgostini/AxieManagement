
import json
import pathlib
import logging
import requests
import concurrent.futures

from web3 import Web3, exceptions
from eth_account.messages import encode_defunct
from time import sleep
from enum import Enum

import backend.encryption.encryption_util as EncryptUtil
from backend.parse_accounts import Account

MAX_ATTEMPTS = 3
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1944.0 Safari/537.36"
AXIE_CONTRACT = "0x32950db2a7164ae833121501c797d79e7b79d74c"
AXS_CONTRACT = "0x97a9107c1793bc407d6f527b77e7fff4d812bece"
SLP_CONTRACT = "0xa8754b9fa15fc18bb59458815510e40a12cd2014"
WETH_CONTRACT = "0xc99a6a985ed2cac1ef41640596c5a5f9f4e19ef5"
REWARDS_CONTRACT = "0x1a35e7ed2a2476129a32612644c8426bf8e8730c"
RONIN_PROVIDER_FREE = "https://proxy.roninchain.com/free-gas-rpc"
RONIN_PROVIDER = "https://api.roninchain.com/rpc"

class ItemType(int, Enum):
    SLP = 1
    mAXS = 6

with open(pathlib.Path(__file__).parent.resolve() / "abis.json") as file:
    web3 = Web3(Web3.HTTPProvider(RONIN_PROVIDER_FREE, request_kwargs={"headers": {"content-type": "application/json", "user-agent": USER_AGENT}}))
    w3 = Web3(Web3.HTTPProvider(RONIN_PROVIDER, request_kwargs={"headers": {"content-type": "application/json", "user-agent": USER_AGENT}}))
    abis = json.load(file)
    nonces = {}

def get_contract(item_type: ItemType, is_payout: bool = False):
    if   item_type == ItemType.SLP: return get_slp_contract()
    elif item_type == ItemType.mAXS:
        if not is_payout:
            return get_rewards_contract()
        else:
            return get_axs_contract()

def get_axie_contract():
    axie_abi = abis['axie']
    axie_address = Web3.toChecksumAddress(AXIE_CONTRACT)
    axie_contract = web3.eth.contract(address=axie_address, abi=axie_abi)
    axie_contract_call = w3.eth.contract(address=axie_address, abi=axie_abi)
    return axie_contract, axie_contract_call

def get_slp_contract():
    slp_abi = abis['slp']
    slp_address = Web3.toChecksumAddress(SLP_CONTRACT)
    slp_contract = web3.eth.contract(address=slp_address, abi=slp_abi)
    slp_contract_call = w3.eth.contract(address=slp_address, abi=slp_abi)
    return slp_contract, slp_contract_call

def get_axs_contract():
    axs_abi = abis['axs']
    axs_address = Web3.toChecksumAddress(AXS_CONTRACT)
    axs_contract = web3.eth.contract(address=axs_address, abi=axs_abi)
    axs_contract_call = w3.eth.contract(address=axs_address, abi=axs_abi)
    return axs_contract, axs_contract_call

def get_rewards_contract():
    reward_abi = abis['reward']
    reward_address = Web3.toChecksumAddress(REWARDS_CONTRACT)
    reward_contract = web3.eth.contract(address=reward_address, abi=reward_abi)
    reward_contract_call = w3.eth.contract(address=reward_address, abi=reward_abi)
    return reward_contract, reward_contract_call

def check_balance(account: Account, token='slp'):
    if token == 'slp':
        _, contract = get_slp_contract()
    elif token == "axies":
        _, contract = get_axie_contract()
    elif token == "axs":
        _, contract = get_axs_contract()
    else:
        return 0

    balance = contract.functions.balanceOf(
        Web3.toChecksumAddress(account.public_addr.replace("ronin:", "0x"))
    ).call()
    return int(balance)

def get_nonce(account: Account):
    address = account.public_addr.replace("ronin:", "0x")
    try:
        nonce = nonces[address]
        nonces[address] = nonce + 1
    except:
        nonce = w3.eth.get_transaction_count(Web3.toChecksumAddress(address))
        nonces[address] = nonce + 1
    return nonce


class Transaction:
    def __init__(self):
        self.is_complete = False
        self.attempts = 0

    def increment_attempt(self):
        self.attempts += 1

    def get_attempt_count(self):
        return self.attempts

    def set_complete(self):
        self.is_complete = True

    def get_is_complete(self):
        return self.is_complete

    def set_transaction_hash(self, hash):
        self.transaction_hash = hash

    def get_transaction_hash(self):
        return self.transaction_hash

    def get_signed_transaction(self):
        pass

def process_transactions(transactions: list[Transaction], CONNECTIONS: int = 100, TIMEOUT: int = 10):

    def _send_transaction(txn: Transaction, timeout: int):
        signed_txn = txn.get_signed_transaction()
        attempts = 0
        while True:
            try:
                tx = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                receipt = w3.eth.wait_for_transaction_receipt(tx, timeout)
                if receipt["status"] == 1:
                    logging.debug("success\t" + w3.toHex(w3.keccak(signed_txn.rawTransaction)))
                else:
                    logging.error("fail\t" + w3.toHex(w3.keccak(signed_txn.rawTransaction)))
                break
            except Exception as e:
                if attempts >= MAX_ATTEMPTS:
                    break
                attempts += 1
                logging.warn(e)
        return w3.toHex(w3.keccak(signed_txn.rawTransaction)), txn

    completed_transactions:list[Transaction] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONNECTIONS) as executor:
        future_to_url = (executor.submit(_send_transaction, tx, TIMEOUT) for tx in transactions)
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                txHash, txn = future.result()
            except Exception as exc:
                txHash = None
                logging.info(f'{type(exc)}: {exc}')
            finally:
                txn.set_transaction_hash(txHash)
                completed_transactions.append(txn)

    if len(completed_transactions) != 0:
        logging.debug("Waiting 30 seconds")
        sleep(30)
        logging.debug("Start Checking")
        check_transactions(completed_transactions)

def check_transactions(transactions: list[Transaction]):
    while len(transactions) > 0:
        tx:Transaction = transactions.pop()
        signed_txn = tx.get_signed_transaction()
        if signed_txn is None:
            continue
        try:
            receipt = w3.eth.get_transaction_receipt(tx.get_transaction_hash())
            if receipt["status"] == 1:
                logging.info(f"Success: \t{str(tx)}:{tx.get_transaction_hash()}")
                tx.set_complete()
            else:
                raise Exception("success = false")
        except Exception as e:
            if tx.get_attempt_count() < 1:
                logging.info(e)
                logging.info(f'Attempt {tx.get_attempt_count()}')
                tx.increment_attempt()
                transactions.append(tx)
                success = send_signed_transaction(signed_txn)
                sleep(5)
                if success:
                    logging.info("Claims to have worked. Will check again to make sure.")
                else:
                    logging.info("Failed")
            else:
                logging.info(f"could not check tx {str(tx)}")


def log_failed_transactions(transactions: list[Transaction]) -> None:
    failed_transactions = [transaction for transaction in transactions if transaction.get_is_complete() == False]
    logging.info(f"Failures:")
    if len(failed_transactions) == 0: logging.info(f"\t\tNone")
    else:
        for failed_transfer in failed_transactions: logging.info(f"\t\t{str(failed_transfer)}")


def send_signed_transaction(signed_txn, timeout=0.025):
    tx = signed_txn.hash
    try:
        w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    except Exception as e:
        logging.warning(e)
    tries = 0
    success = False
    while tries < 1:
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx, timeout)
            if receipt["status"] == 1:
                success = True
            break
        except (exceptions.TransactionNotFound, exceptions.TimeExhausted):
            sleep(5 - 0.025)
            tries += 1
            logging.debug("Not found yet, waiting...")
    if success:
        if check_transaction(tx):
            logging.debug(f"Found tx hash on chain: {tx}")
            return True
    logging.warning(f"Failed to find tx on chain: {tx}")
    return False

def check_transaction(txHash):
    for a in range(20):
        try:
            w3.eth.get_transaction_receipt(txHash)
        except:
            return False
        sleep(3)
    return True


def run_in_parallel(function, args: list[list], threads: int = 100):
    function_return = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = (executor.submit(function, *call) for call in args)
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            function_return.append(result)
    return function_return


def generate_access_token(account: Account):
    random_message = _create_random_message()
    if random_message is None: 
        logging.critical(f"Failure generating random message")
        return None
    private_key = EncryptUtil.get_private_key(account.seed_id, account.seed_account_num)
    signed_message = w3.eth.account.sign_message(encode_defunct(text=random_message), private_key=private_key)
    token = _create_access_token(random_message, signed_message, account)
    if token is None: logging.critical(f"Failure generating token")
    return token

def _create_random_message(attempts: int = 0):
    payload = {
        "operationName": "CreateRandomMessage",
        "variables": {},
        "query": "mutation CreateRandomMessage{createRandomMessage}"
    }
    url = "https://graphql-gateway.axieinfinity.com/graphql"
    try:
        response = requests.request("POST", url, json=payload)
        if 200 <= response.status_code <= 299:
            return response.json()['data']['createRandomMessage']
        else: raise ValueError(f"Response had invalid status: {response}")
    except Exception as e:
        if attempts < MAX_ATTEMPTS:
            logging.debug(f"Error creating random msg, retrying: {e}")
            return _create_random_message(attempts + 1)
        else:
            logging.critical(f"Error creating random msg: {e}")
            return None

def _create_access_token(random_message, signed_message, account: Account, attempts: int = 0):
    hex_signature = signed_message['signature'].hex()
    payload = {
        "operationName": "CreateAccessTokenWithSignature",
        "variables": {
            "input": {
                "mainnet": "ronin",
                "owner": f"{account.public_addr.replace('ronin:', '0x')}",
                "message": f"{random_message}",
                "signature": f"{hex_signature}"
            }
        },
        "query": "mutation CreateAccessTokenWithSignature($input: SignatureInput!)"
        "{createAccessTokenWithSignature(input: $input) "
        "{newAccount result accessToken __typename}}"
    }
    url = "https://graphql-gateway.axieinfinity.com/graphql"
    try:
        response = requests.request("POST", url, headers={"User-Agent": USER_AGENT}, json=payload)
        json_data = response.json()
        return json_data['data']['createAccessTokenWithSignature']['accessToken']
    except Exception as e:
        if attempts < MAX_ATTEMPTS:
            logging.debug(f"Error generating access token, retrying: {e}")
            return _create_access_token(random_message, signed_message, account, attempts + 1)
        else:
            logging.critical(f"Error generating access token: {e}")
            return None
