import os
import sys
import json
import shutil
import pathlib
from datetime import datetime, timedelta

import backend.parse_env as EnvVar

# Parameterize build with fee
if len(sys.argv) != 2:
    print("Please input a developer fee")
    exit()
developer_fee = sys.argv[1]
distribution_folder = f"dist/{developer_fee}"

payments_file = open('backend/transaction/payments.py', 'r')
replacement = ""
for line in payments_file.readlines():
    if "DEVELOPER_FEE =" in line:
        line = line.strip()
        changes = line.replace(line, f"DEVELOPER_FEE = {developer_fee} # Percent")
        replacement = replacement + changes + "\n"
    else:
        replacement = replacement + line

payments_file.close()
payments_file = open('backend/transaction/payments.py', "w")
payments_file.write(replacement)
payments_file.close()
payments_file.close()

# Remove previous dist
shutil.rmtree("dist/", ignore_errors=True)

# Generate license for expiry
now = datetime.now()
expiry = now + timedelta(days=365)
date_format_string = "%Y-%m-%d"
expiry_formatted = datetime.strftime(expiry, date_format_string)
os.system(f"pyarmor l --expired {expiry_formatted} r001")
license_name = "licenses/r001/license.lic"

# Opening JSON file
armor_config = open('.pyarmor_config')
armor_config_json = json.load(armor_config)
armor_config.close()
try:
    del armor_config_json['build_time'] # Have to clear this to rebuild
except:
    pass
armor_config_json['license_file'] = license_name
armor_config_json['output'] = distribution_folder
with open('.pyarmor_config', 'w', encoding='utf-8') as f:
    json.dump(armor_config_json, f, ensure_ascii=False, indent=4)

# Build with pyarmor
os.system("pyarmor build")

# Delete license folder
shutil.rmtree('licenses/', ignore_errors=True)

# Move static files over
shutil.copytree("webserver/static/", f"{distribution_folder}/webserver/static")
shutil.copytree("webserver/templates/", f"{distribution_folder}/webserver/templates")
for root, dirs, files in os.walk(".", topdown=False):
    if "dist" in root: continue
    for name in files:
        if ".json" in name or ".txt" in name:
            print(os.path.join(root, name))
            shutil.copyfile(os.path.join(root, name), pathlib.Path(distribution_folder) / os.path.join(root, name))

# Copy and modify .env file
EnvVar.create_default_env_file(pathlib.Path(__file__).parent.resolve() / ".env", pathlib.Path(distribution_folder) / ".env")
