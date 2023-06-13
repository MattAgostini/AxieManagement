import logging
import openpyxl
import re
from dataclasses import dataclass
from enum import Enum

import backend.parse_env as EnvVar

DEFAULT_ACCOUNT_NAME = "---"

class AccountType(str, Enum):
    Owner = "Owner"
    Manager = "Manager"
    Scholar = "Scholar"
    Vault = "Vault"
    Developer = "Developer"

@dataclass(frozen=False)
class Account:
    seed_id: int
    seed_account_num: int
    account_name: str
    discord_id: str
    account_types: list[AccountType]
    public_addr: str
    account_email: str
    account_password: str
    payout_addr: str
    payout_percentage: float

    def __str__(self):
        return EnvVar.ACCOUNT_NAME_FORMAT.format(
            seed_id=self.seed_id, 
            seed_account_num=self.seed_account_num, 
            account_name=self.account_name
        )


def parse_ronin_string(ronin: str):
    pattern = 'ronin:[0-9A-Fa-f]{40}'
    return re.fullmatch(pattern, ronin)


def parse_account_file_row(row: list) -> Account:
    ''' Expected row format: Name, DiscordId, AccountType, AccountAddress, ScholarPayoutAddress, PayoutPercentage '''
    none_entries = [entry is None for entry in row[:8]]
    if all(none_entries): return None

    error_string = "Error parsing accounts file:"

    seed_id = int(row[0])
    assert seed_id is not None, f"{error_string} Missing seed id"
    seed_account_num = int(row[1])
    assert seed_account_num is not None, f"{error_string} {seed_id} Seed ID {seed_id} had an empty account number"

    account_name = row[2]
    if account_name is None:
        logging.warning(f"Seed ID {seed_id} Account {seed_account_num} has no name")
        account_name = DEFAULT_ACCOUNT_NAME

    discord_id = row[3]
    if discord_id is None: logging.warning(f"Seed ID {seed_id} Account {seed_account_num} is missing discord information")

    account_types = []
    if row[4] is not None:
        for type in AccountType:
            if type in row[4]: account_types.append(type)

    public_addr = row[5]
    assert parse_ronin_string(public_addr) is not None, f"{error_string} Seed ID {seed_id} Account {seed_account_num} has a malformed ronin address"

    account_email = row[6]
    account_password = row[7]
    if account_email is None or account_password is None: logging.warning(f"Seed ID {seed_id} Account {seed_account_num} is missing email information")

    payout_address = row[8]
    if payout_address is None: logging.warning(f"Seed ID {seed_id} Account {seed_account_num} is missing payout address")
    else: assert parse_ronin_string(payout_address) is not None, f"{error_string} Seed ID {seed_id} Account {seed_account_num} has a malformed payout address"

    payout_percentage = row[9]
    if payout_percentage is None: payout_percentage = 0

    return Account(
        seed_id=seed_id,
        seed_account_num=seed_account_num,
        account_name=account_name,
        account_types=account_types,
        public_addr=public_addr,
        account_email=account_email,
        account_password=account_password,
        discord_id=discord_id,
        payout_addr=payout_address,
        payout_percentage=payout_percentage
    )


def parse_account_file(accountsList: list[Account], filename: str = "accounts.xlsx"):
    ''' Reads an excel sheet filled with account information '''

    wb = openpyxl.load_workbook(filename)
    ws = wb.active

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0: continue
        account = parse_account_file_row(row)
        if account is not None: accountsList.append(account)
    owner_accounts = [account for account in accountsList if AccountType.Owner in account.account_types]
    assert len(owner_accounts) == 1, "Account file must have 1 'Owner' type account"
