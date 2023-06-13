import backend.encryption.create_accounts as AccountCreator

def main():
    email_password = AccountCreator.initialize_account_creation()
    AccountCreator.create_accounts(email_password)

if __name__ == "__main__":
    main()
