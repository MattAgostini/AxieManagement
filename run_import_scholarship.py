import sys
import logging
from pathlib import Path
import backend.database.database_util as DbUtil
import backend.encryption.encryption_util as EncryptUtil

path = Path("log/")
path.mkdir(parents=True, exist_ok=True)
logging.root.handlers = []
logging.basicConfig(
    level=logging.WARNING,
    format="[%(levelname)s]  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)


def main():
    print(
        "\n----- Welcome to the Axie Management import scholarship script -----\n\n"
        "This script will walk you through the process of setting up the internals\n"
        "required to run the webserver, and discord bot.\n\n"

        "Please ensure that your accounts.xlsx spreadsheet is formatted correctly.\n"
        "If you have any questions about the proper format of this spreadsheet, \n"
        "please contact a customer representative\n\n"

        "Disclaimer: This script will ask you for the seed codes associated with the\n"
        "accounts in the accounts.xlsx spreadsheet. It will also ask you for a password,\n"
        "which will be used to run the software once your seeds are encrypted.\n\n"
        "Make sure to run this script on a secure computer, possibly even with the internet disabled.\n"
        "Please keep your password and datafiles safe.\n"

        "Are you ready to continue? (y/N)"
    )

    while True:
        response = input()
        if response.lower() == 'y': break
        elif response.lower() == 'n':
            print("Exiting.")
            exit()
        else: 
            print("Invalid input.")


    print(
        "\nRunning the import will overwrite the existing database with new data!\n"
        "Are you sure you want to continue? (y/N)"
    )

    while True:
        response = input()
        if response.lower() == 'y': break
        if response.lower() == 'n':
            print("Exiting.")
            exit()

    print("\n----- Importing scholarship from Excel and populating databases! -----\n")

    DbUtil.clear_database()
    DbUtil.initialize_database()

    print("\n----- Finished populating database! -----\n")
 
    print("\n----- Beginning seed code encryption phase! -----\n")

    print(
        "This process will overwrite your existing iv.dat and SeedStorage.py files if they exist.\n"
        "Are you sure you want to continue? (y/N)\n"
    )

    while True:
        response = input()
        if response.lower() == 'y': break
        if response.lower() == 'n':
            print("Exiting.")
            exit()

    EncryptUtil.key = EncryptUtil.set_password()
    EncryptUtil.encrypt_seeds(EncryptUtil.key)


if __name__ == "__main__":
    main()
