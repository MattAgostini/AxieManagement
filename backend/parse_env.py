import os
import dotenv
import shutil
from pathlib import Path

dotenv.load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

OPEN_BOT_CHANNEL = str(os.getenv('OPEN_BOT_CHANNEL'))
ADMIN_BOT_CHANNEL = str(os.getenv('ADMIN_BOT_CHANNEL'))
OPEN_ALERT_CHANNEL = str(os.getenv('OPEN_ALERT_CHANNEL'))
ADMIN_ALERT_CHANNEL = str(os.getenv('ADMIN_ALERT_CHANNEL'))

ACCOUNT_NAME_FORMAT = str(os.getenv('ACCOUNT_NAME_FORMAT'))
ACCOUNT_EMAIL_FORMAT = str(os.getenv('ACCOUNT_EMAIL_FORMAT'))

PASSWORD_SALT = os.getenv('PASSWORD_SALT')

BOT_WEB3_ENABLED = os.getenv("ENABLE_BOT_WEB3", 'False').lower() in ('true', '1', 't')
CLEAR_PAYOUT_ADDR_ON_REMOVAL = os.getenv("CLEAR_PAYOUT_ADDR_ON_REMOVAL", 'False').lower() in ('true', '1', 't')


def create_default_env_file(old_file: Path, new_file: Path):
    new_env_file = shutil.copyfile(old_file, new_file)
    dotenv.load_dotenv(new_env_file)

    os.environ["DISCORD_TOKEN"] = ""
    dotenv.set_key(new_env_file, "DISCORD_TOKEN", os.environ["DISCORD_TOKEN"])

    os.environ["OPEN_BOT_CHANNEL"] = ""
    dotenv.set_key(new_env_file, "OPEN_BOT_CHANNEL", os.environ["OPEN_BOT_CHANNEL"])

    os.environ["ADMIN_BOT_CHANNEL"] = ""
    dotenv.set_key(new_env_file, "ADMIN_BOT_CHANNEL", os.environ["ADMIN_BOT_CHANNEL"])

    os.environ["OPEN_ALERT_CHANNEL"] = ""
    dotenv.set_key(new_env_file, "OPEN_ALERT_CHANNEL", os.environ["OPEN_ALERT_CHANNEL"])

    os.environ["ADMIN_ALERT_CHANNEL"] = ""
    dotenv.set_key(new_env_file, "ADMIN_ALERT_CHANNEL", os.environ["ADMIN_ALERT_CHANNEL"])

    os.environ["ACCOUNT_NAME_FORMAT"] = "Prefix | {seed_id} {seed_account_num} | {account_name}"
    dotenv.set_key(new_env_file, "ACCOUNT_NAME_FORMAT", os.environ["ACCOUNT_NAME_FORMAT"])

    os.environ["ACCOUNT_EMAIL_FORMAT"] = "base+{seed_id}_{seed_account_num}@domain.com"
    dotenv.set_key(new_env_file, "ACCOUNT_EMAIL_FORMAT", os.environ["ACCOUNT_EMAIL_FORMAT"])

    os.environ["PASSWORD_SALT"] = ""
    dotenv.set_key(new_env_file, "PASSWORD_SALT", os.environ["PASSWORD_SALT"])

    os.environ["ENABLE_BOT_WEB3"] = "False"
    dotenv.set_key(new_env_file, "ENABLE_BOT_WEB3", os.environ["ENABLE_BOT_WEB3"])

    os.environ["CLEAR_PAYOUT_ADDR_ON_REMOVAL"] = "False"
    dotenv.set_key(new_env_file, "CLEAR_PAYOUT_ADDR_ON_REMOVAL", os.environ["CLEAR_PAYOUT_ADDR_ON_REMOVAL"])