#!/usr/bin/env python3
''' Telegram food ordering bot.
This bot provides a frontend for online food ordering on Telegram using Testignighter as a backend.
https://github.com/troioi-vn/tele-igniter
'''

# Set up the logger
import logging
logging.basicConfig(
	level=logging.INFO, # INFO | DEBUG
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

# Check configuration file
# If there is no .config.yml file run a sepup.py script
import os
if not os.path.isfile(".config.yml"):
	print("Configuration file .config.yml not found")
	print("Running setup.py script... ")
	# Run setup.py script
	import setup
	setup.run()
	
# Load configuration file
import yaml
try:
	config = yaml.safe_load(open(".config.yml"))
except Exception:
	# Log this error to logger
	logger.error("Configuration file is invalid")
	print("Please check your configuration file")
	# Offer to run setup.py script
	print("Do you want to run setup.py script? (y/n)")
	# Get user input and check if it is "y" or "Y"
	choice = input()
	if choice == "y" or choice == "Y":
		# Run setup.py script
		import setup
		setup.run()
	else:
		exit(0)
else:
	print("Configuration file loaded")

# Connecting to Tastyigniter API and loading data
import requests

# Create Bearer authorization header
headers =  {"Content-Type":"application/json", "Authorization": f"Bearer {config['ti-token']}"}

# Load locations (and check connection)
active_location = None
try:
	response = requests.get(f"{config['ti-url']}/locations", headers=headers)
except Exception:
	# Log this error to logger
	logger.error("Error while connecting to Tastyigniter API")
	print("1. Check API URL and API token in your configuration file")
	print("2. Check if Tastyigniter API is running")
	print("3. Check if Tastyigniter API is accessible from this machine")
	print("4. Check if /locations endpoint is enabled in Tastyigniter API for this token")
	# Exit the program
	exit(0)
else:
	print("Connection to Tastyigniter API is successful")
	print("Loading locations...")
 
# Check if there are any locations 
if len(response.json()['data']) == 0:
	print("There are no locations on Tastyigniter side")
	print("Please create location on Teastyigniter side and check your configuration file")
	# Exit the program
	exit(0)

# Check if location_id from config matches any location_id from Tastyigniter API
valid = False
for location in response.json()['data']:
	if int(location['id']) == config['location_id']:
		valid = True
		break
if valid == False:
	print(f"Location ID ({config['location_id']}) is invalid")
	print("Please set correct location ID in your configuration file")
	# Exit the program
	exit(0)
else:
	print(location['id'], location['attributes']['location_name'])
	active_location = location
 
# Load menu
menu_items = []
try:
	response = requests.get(f"{config['ti-url']}/menus", headers=headers)
except Exception:
	# Log this error to logger
	logger.error("Error while connecting to Tastyigniter API")
else:

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
	Application,
	CallbackQueryHandler,
	CommandHandler,
	ContextTypes,
	ConversationHandler,
)


# Stages
START_ROUTES, END_ROUTES = range(2)
# Callback data
ONE, TWO, THREE, FOUR = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Send main menu on `/start`."""
	# Get user that sent /start and log his name
	user = update.message.from_user
	logger.info("User %s started the conversation.", user.first_name)
	keyboard = [
		[
			InlineKeyboardButton("1", callback_data=str(ONE)),
			InlineKeyboardButton("2", callback_data=str(TWO)),
		]
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	# Send message with text and appended InlineKeyboard
	await update.message.reply_text("Start handler, Choose a route", reply_markup=reply_markup)
	# Tell ConversationHandler that we're in state `FIRST` now
	return START_ROUTES


async def start_over(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Prompt same text & keyboard as `start` does but not as new message"""
	# Get CallbackQuery from Update
	query = update.callback_query
	# CallbackQueries need to be answered, even if no notification to the user is needed
	# Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
	await query.answer()
	keyboard = [
		[
			InlineKeyboardButton("1", callback_data=str(ONE)),
			InlineKeyboardButton("2", callback_data=str(TWO)),
		]
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	# Instead of sending a new message, edit the message that
	# originated the CallbackQuery. This gives the feeling of an
	# interactive menu.
	await query.edit_message_text(text="Start handler, Choose a route", reply_markup=reply_markup)
	return START_ROUTES


async def one(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Show new choice of buttons"""
	query = update.callback_query
	await query.answer()
	keyboard = [
		[
			InlineKeyboardButton("3", callback_data=str(THREE)),
			InlineKeyboardButton("4", callback_data=str(FOUR)),
		]
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	await query.edit_message_text(
		text="First CallbackQueryHandler, Choose a route", reply_markup=reply_markup
	)
	return START_ROUTES


async def two(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Show new choice of buttons"""
	query = update.callback_query
	await query.answer()
	keyboard = [
		[
			InlineKeyboardButton("1", callback_data=str(ONE)),
			InlineKeyboardButton("3", callback_data=str(THREE)),
		]
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	await query.edit_message_text(
		text="Second CallbackQueryHandler, Choose a route", reply_markup=reply_markup
	)
	return START_ROUTES


async def three(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Show new choice of buttons. This is the end point of the conversation."""
	query = update.callback_query
	await query.answer()
	keyboard = [
		[
			InlineKeyboardButton("Yes, let's do it again!", callback_data=str(ONE)),
			InlineKeyboardButton("Nah, I've had enough ...", callback_data=str(TWO)),
		]
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	await query.edit_message_text(
		text="Third CallbackQueryHandler. Do want to start over?", reply_markup=reply_markup
	)
	# Transfer to conversation state `SECOND`
	return END_ROUTES


async def four(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Show new choice of buttons"""
	query = update.callback_query
	await query.answer()
	keyboard = [
		[
			InlineKeyboardButton("2", callback_data=str(TWO)),
			InlineKeyboardButton("3", callback_data=str(THREE)),
		]
	]
	reply_markup = InlineKeyboardMarkup(keyboard)
	await query.edit_message_text(
		text="Fourth CallbackQueryHandler, Choose a route", reply_markup=reply_markup
	)
	return START_ROUTES


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
	"""Returns `ConversationHandler.END`, which tells the
	ConversationHandler that the conversation is over.
	"""
	query = update.callback_query
	await query.answer()
	await query.edit_message_text(text="See you next time!")
	return ConversationHandler.END


def main() -> None:
	"""Run the bot."""
	application = Application.builder().token(config['telegram-token']).build()

	# Setup conversation handler with the states FIRST and SECOND
	# Use the pattern parameter to pass CallbackQueries with specific
	# data pattern to the corresponding handlers.
	# ^ means "start of line/string"
	# $ means "end of line/string"
	# So ^ABC$ will only allow 'ABC'
	conv_handler = ConversationHandler(
		entry_points=[CommandHandler("start", start)],
		states={
			START_ROUTES: [
				CallbackQueryHandler(one, pattern="^" + str(ONE) + "$"),
				CallbackQueryHandler(two, pattern="^" + str(TWO) + "$"),
				CallbackQueryHandler(three, pattern="^" + str(THREE) + "$"),
				CallbackQueryHandler(four, pattern="^" + str(FOUR) + "$"),
			],
			END_ROUTES: [
				CallbackQueryHandler(start_over, pattern="^" + str(ONE) + "$"),
				CallbackQueryHandler(end, pattern="^" + str(TWO) + "$"),
			],
		},
		fallbacks=[CommandHandler("start", start)],
	)

	# Add ConversationHandler to application that will be used for handling updates
	application.add_handler(conv_handler)

	# Run the bot until the user presses Ctrl-C
	application.run_polling()


if __name__ == "__main__":
	main()