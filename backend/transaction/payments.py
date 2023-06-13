import logging
from web3 import Web3

import backend.encryption.encryption_util as EncryptUtil
import backend.transaction.utilities as utilities
import backend.database.database_util as DbUtil
from backend.parse_accounts import AccountType, Account


DEVELOPER_ADDR = "ronin:2556901910f285f1bd4bf7720392a7d45a5f355d"
DEVELOPER_FEE = 1 # Percent


class Payment(utilities.Transaction):
    def __init__(self, from_acc: Account, to_ronin: str, to_acc_type: str, amount: int, item_type: utilities.ItemType):
        self.from_account = from_acc
        self.from_ronin = from_acc.public_addr.replace("ronin:", "0x")
        self.to_ronin = to_ronin.replace("ronin:", "0x")
        self.to_acc_type = to_acc_type
        self.amount = amount
        self.item_type = item_type
        super().__init__()

    def get_destination_account_type(self):
        return self.to_acc_type

    def get_amount(self):
        return self.amount

    def get_signed_transaction(self):
        return self.signed_payment_tx

    def build_signed_payment_tx(self):
        self.nonce = utilities.get_nonce(self.from_account)
        _, contract_call = utilities.get_contract(self.item_type, True)
        payment_tx = contract_call.functions.transfer(
            Web3.toChecksumAddress(self.to_ronin),
            self.amount
        ).buildTransaction({
            'gas': 300000,
            "gasPrice": Web3.toWei(1, "gwei"),
            "nonce": self.nonce
        })
        sender_private_key = EncryptUtil.get_private_key(self.from_account.seed_id, self.from_account.seed_account_num)
        self.signed_payment_tx = utilities.w3.eth.account.sign_transaction(payment_tx, sender_private_key)

    def __str__(self):
        return f"({str(self.from_account)}) to ({self.to_acc_type}:{str(self.to_ronin)}) for the amount of {self.amount} SLP"


def prepare_and_execute_payout(scholars: list[Account], item_type: utilities.ItemType):
    payment_list:list[Payment] = []
    for scholar in scholars:
        vault_account = DbUtil.account_db.get_seed_vault_account(scholar.seed_id, enable_assertion=True)
        scholar_payments = _build_scholar_payments(scholar, vault_account.public_addr, item_type)
        if scholar_payments is None: continue
        payment_list.extend(scholar_payments)

    payout_stats = {'Total': 0, AccountType.Scholar: 0, AccountType.Developer: 0, AccountType.Vault: 0}
    for payment in payment_list:
        payment_amount = payment.get_amount()
        payout_stats['Total'] += payment_amount
        payout_stats[payment.get_destination_account_type()] += payment_amount

    logging.info(f"Initial Payment Statistics: {_get_payout_stats(payment_list)}")
    _payout_account_type(payment_list, AccountType.Vault)
    _payout_account_type(payment_list, AccountType.Scholar)
    _payout_account_type(payment_list, AccountType.Developer)
    logging.info(f"Final Payment Statistics: {_get_payout_stats(payment_list, successful_only=True)}")


def _payout_account_type(payment_list: list[Payment], account_type: AccountType):
    payments = [payment for payment in payment_list if payment.get_destination_account_type() == account_type]
    for payment in payments: payment.build_signed_payment_tx()
    logging.info(f"Paying out {len(payments)} payments to {account_type}")
    utilities.process_transactions(payments)
    utilities.log_failed_transactions(payments)


def _get_payout_stats(payment_list: list[Payment], successful_only: bool = False) -> dict:
    payout_stats = {'Total': 0, AccountType.Scholar: 0, AccountType.Developer: 0, AccountType.Vault: 0}
    for payment in payment_list:
        if successful_only and not payment.get_is_complete(): continue
        payment_amount = payment.get_amount()
        payout_stats['Total'] += payment_amount
        payout_stats[payment.get_destination_account_type()] += payment_amount
    return payout_stats


def _build_scholar_payments(scholar: Account, vault_addr: str, item_type: utilities.ItemType) -> list[Payment]:
    acc_balance = utilities.check_balance(scholar)
    if item_type == utilities.ItemType.mAXS: acc_balance = utilities.check_balance(scholar, 'axs')

    if acc_balance == 0:
        logging.warning(f"Scholar {str(scholar)} has 0 account balance. Skipping") 
        return

    payment_list = []
    total_payments = 0

    # Scholar Payment
    scholar_amount = acc_balance * (scholar.payout_percentage / 100.0)
    scholar_amount = round(scholar_amount)
    total_payments += scholar_amount
    if scholar.payout_percentage > 0:
        if scholar.payout_addr is None: 
            logging.warning(f"Scholar {str(scholar)} has no payout address. Skipping")
            return
        elif scholar.payout_addr == scholar.public_addr:
            logging.warning(f"Scholar {str(scholar)} payout address is the same as the ronin address. Please fix.")
            return
        else: 
            payment_list.append(Payment(
                scholar,
                scholar.payout_addr,
                AccountType.Scholar,
                scholar_amount,
                item_type
            ))

    # Developer Payment
    dev_amount = acc_balance * (DEVELOPER_FEE / 100.0)
    dev_amount = round(dev_amount)
    if dev_amount > 0:
        payment_list.append(Payment(
            scholar,
            DEVELOPER_ADDR,
            AccountType.Developer,
            dev_amount,
            item_type
        ))
        total_payments += dev_amount
    else:
        logging.warning("Skipping developer payout as it resulted in 0 SLP.")
    
    # Vault Payment
    vault_amount = acc_balance - total_payments
    if vault_amount > 0:
        payment_list.append(Payment(
            scholar,
            vault_addr,
            AccountType.Vault,
            vault_amount,
            item_type
        ))
        total_payments += vault_amount
    else:
        logging.warning("Skipping vault payout as it resulted in 0 SLP.")

    for p in payment_list: logging.info(f"\t{str(p)}")
    return payment_list
