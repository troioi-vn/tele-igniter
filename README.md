# tele-igniter
This telegram bot provides a way to order food from your [TestyIgniter](https://github.com/tastyigniter/TastyIgniter) powered restaurant using Telegram.
Currently it is in development and it is not ready for production use. Further instructions will be added when the bot is ready for production use.

For now, you can use the bot to test the features and report bugs. Current features are:
- Base communication with the TestyIgniter API
- List menu items in categories for multiple locations
- The cart functionality
- Coupons plugin support

Final goal is to relese a bot that can be used by any restaurant that uses TestyIgniter as a backend. Including not only ordering, but also other user features like booking a table, etc. Plus hopefully admin functionality like managing orders, items and even some features that are not available in TestyIgniter like coupons generation after a certain amount of orders or something like that.

## Roadmap
### MVP List of stoppers
- Aply coupon to the item in the cart
- Filtr coupons by location
- Process delyvery fee
- Add user location to the order
- Add user comment to the order
- Add phone number to the order
- Place an order
- Notifications support

### Beta todo list
- Update setup.py, and test on a clean server
- Chat with admin from the bot
- Multi language support
- Get closest locatios when when the user shares his location
- Managing address book from the bot (wait for the [API to be ready](https://github.com/tastyigniter/ti-ext-api/issues/86))
- Replace the temporary location info parcer with the [API call](https://github.com/tastyigniter/ti-ext-api/issues/85)

### First release
- Support user matching between Telegram and Testyigniter
- Integrate TastyIgniter side plugin to move config and other stuff to the admin panel
- Update setup.py to install all dependencies and create a config file

## Installation
### Requirements
- [Testyigniter](https://testyigniter.com/) working on your server with the API plugin installed and enabled
- Telegram bot token ([@BotFather](https://t.me/BotFather))
- You need to install the following dependencies:
[codesyntax lang="bash"]
pip3 install PyYAML python-telegram-bot --upgrade
[/codesyntax]

### Automatic installation
clone this repo and run the following command:
[codesyntax lang="bash"]
python3 setup.py install
[/codesyntax]

### Manual installation
- Clone this repo
- Copy the config.yaml.example file to config.yaml
- Edit the config.yaml file and add your Testyigniter API key and Telegram bot token
- Run the following command to start the bot:
[codesyntax lang="bash"]
    python3 main.py
[/codesyntax]