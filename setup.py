'''Setup wizard for creating .config.yml file'''
# This file will be run if there is no .config.yml file by setup.run() or manually by user

import os

# read .config.yml.default file
default_config = open(".config.yml.default", "r").readlines()

print("Welcome to Tastyigniter Telegram Bot setup wizard")
print("This wizard will help you to create .config.yml file")
print("If you want to cancel setup press Ctrl+C")

# Check if .config.yml file exists
if os.path.isfile(".config.yml"):
    print("Configuration file .config.yml already exists do you want to overwrite it? (y/n)")
    answer = input()
    if answer == "n":
        print("Setup canceled")
        exit(0)
    else:
        print("Configuration file will overwritten")

# Ask user enter Telegram bot API key (token)
enterd_token = ""
while enterd_token == "":
    print("Please enter Telegram bot API key")
    enterd_token = input()

# Ask user for Tastyigniter API URL (ti-url)
entered_ti_url = ""
while entered_ti_url == "":
    print("Please enter Tastyigniter API URL")
    entered_ti_url = input()

# Ask user for Tastyigniter API key (ti-token)
entered_ti_token = ""
while entered_ti_token == "":
    print("Please enter Tastyigniter API key")
    entered_ti_token = input()

# Back up old .config.yml file if exists to .config.yml.bak
if os.path.isfile(".config.yml"):
    # Default backup file name
    backup_file = ".config.yml.bak"
    # If .config.yml.bak already exists use other name like .config.yml.bak.N
    if os.path.isfile(backup_file):
        i = 1
        while os.path.isfile(f"{backup_file}.{i}"):
            i += 1
        backup_file = f"{backup_file}.{i}" # .config.yml.bak.1

    # Back up old .config.yml file to backup_file
    try:
        os.rename(".config.yml", backup_file)
    except Exception as e:
        print(f"Error while backing to {backup_file} file")
        print(e)
    else:
        print(f"Old .config.yml file backed up to {backup_file}")

# Create new configuration file
config = open(".config.yml", "w")

# Write configuration to .config.yml line by line
for line in default_config:
    # Check if line contains telegram-token, ti-url or ti-token
    if "telegram-token:" in line:
        config.write(f"token: {enterd_token}")
    elif "ti-url:" in line:
        config.write(f"ti-url: {entered_ti_url}")
    elif "ti-token:" in line:
        config.write(f"ti-token: {entered_ti_token}")
    else:
        config.write(f"{line}")
config.close()

print("Configuration file created successfully")

print("Do you want to run bot now? (y/n)")
answer = input()
if answer == "y":
    import main
    main.run()
else:
    print("Setup finished")
    print("To run bot type 'python main.py'")
    print("To run setup wizard type 'python setup.py")
    exit(0)