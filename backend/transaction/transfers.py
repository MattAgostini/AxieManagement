import logging
from web3 import Web3

import backend.encryption.encryption_util as EncryptUtil
import backend.database.database_util as DbUtil
import backend.transaction.utilities as utilities
from backend.parse_accounts import Account


class Transfer(utilities.Transaction):
    def __init__(self, from_acc: Account, to_acc: Account, axie_id: int):
        self.from_account = from_acc
        self.from_ronin = from_acc.public_addr.replace("ronin:", "0x")
        self.to_account = to_acc
        self.to_ronin = to_acc.public_addr.replace("ronin:", "0x")
        self.axie_id = axie_id
        self._build_signed_transfer_tx()
        super().__init__()

    def get_signed_transaction(self):
        return self.signed_transfer_tx

    def _build_signed_transfer_tx(self):
        self.nonce = utilities.get_nonce(self.from_account)
        _, axie_contract_call = utilities.get_axie_contract()
        transfer_tx = axie_contract_call.functions.safeTransferFrom(
            Web3.toChecksumAddress(self.from_ronin),
            Web3.toChecksumAddress(self.to_ronin),
            self.axie_id
        ).buildTransaction({
            'gas': 300000,
            "gasPrice": Web3.toWei(1, "gwei"),
            "from": Web3.toChecksumAddress(self.from_ronin),
            "nonce": self.nonce
        })
        sender_private_key = EncryptUtil.get_private_key(self.from_account.seed_id, self.from_account.seed_account_num)
        self.signed_transfer_tx = utilities.w3.eth.account.sign_transaction(transfer_tx, sender_private_key)

    def __str__(self):
        return (f"Axie Transfer of axie ({self.axie_id}) from account ({str(self.from_account)}) to account ({str(self.to_account)})")


def prepare_and_execute_transfer(transfer_list: dict) -> list[Account]:
    refresh_list:list[Account] = []
    transfers = []
    for receiver_addr in transfer_list:
        receiver_account = DbUtil.account_db.get_account_entry(receiver_addr).account
        axies_to_send = transfer_list[receiver_addr]
        for axie_to_send in axies_to_send:
            sender_account = DbUtil.axie_db.get_axie_entry(axie_to_send).owner_account
            logging.info(f"Sending axie {axie_to_send} from ({str(sender_account)}) to ({str(receiver_account)})")
            transfers.append(Transfer(sender_account, receiver_account, int(axie_to_send)))

            if sender_account in refresh_list: continue
            refresh_list.append(sender_account)
        if receiver_account in refresh_list: continue
        refresh_list.append(receiver_account)

    utilities.process_transactions(transfers)
    utilities.log_failed_transactions(transfers)

    return refresh_list
