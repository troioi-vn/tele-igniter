#!/usr/bin/env python3
''' Telegram food ordering bot.
This bot provides a frontend for online food ordering on Telegram using Testignighter as a backend.
GitHub https://github.com/troioi-vn/tele-igniter
'''

import os, yaml, logging, requests, json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

# Set up the logger
logging.basicConfig(
	level=logging.INFO, # INFO | DEBUG | WARNING | ERROR
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

# Check configuration file. If there is no .config.yml file run a sepup.py script
if not os.path.isfile(".config.yml"):
	logger.warning("Configuration file .config.yml not found")
	logger.info("Running setup.py script...")
	# Run setup.py script
	import setup
	setup.run()
	
# Load configuration file
try:
	config = yaml.safe_load(open(".config.yml"))
except Exception:
	# Log this error to logger
	logger.error("Configuration file is invalid")
	logger.info("Please check your configuration file")
	# Offer to run setup.py script
	logger.info("Do you want to run setup.py script? (y/n)")
	# Get user input and check if it is "y" or "Y"
	choice = input()
	if choice == "y" or choice == "Y":
		# Run setup.py script
		import setup
		setup.run()
	else:
		exit(0)
else:
	logger.info("Configuration file loaded")
 
# Create Bearer authorization header
headers =  {"Content-Type":"application/json", "Authorization": f"Bearer {config['ti-token']}"}

# Active dialogues
dialogues = {}

# Load active locations (and check connection)
active_locations = []
logger.info("Loading active locations from Tastyigniter API")
try:
	request = f"locations?location_status=true"
	logger.info(f"Request: {request}")
	response = requests.get(f"{config['ti-url']}/{request}", headers=headers)
except Exception:
	# Log this error to logger
	logger.info("Error while connecting to Tastyigniter API")
	logger.info("1. Check API URL and API token in your configuration file")
	logger.info("2. Check if Tastyigniter API is running")
	logger.info("3. Check if Tastyigniter API is accessible from this machine")
	logger.info("4. Check if /locations endpoint is enabled in Tastyigniter API for this token")
	# Exit the program
	exit(0)
else:
	logger.info("Connection to Tastyigniter API is successful")
	# Check if there are any locations 
	if len(response.json()['data']) == 0:
		logger.error("There are no locations on Tastyigniter side")
		logger.info("Please create location on Teastyigniter side and check your configuration file")
		# TODO: offer to create location
		# Exit the program
		exit(0)

# Check if location_ids list from config matches any location_id from Tastyigniter API response
for location in response.json()['data']:
	if int(location['id']) in config['location_ids']:
		active_locations.append(location)
		logger.info(f"Active: {location['id']} {location['attributes']['location_name']}")
	else:
		logger.info(f"Inactive: {location['id']} {location['attributes']['location_name']}")

# Check if there are any active locations
if len(active_locations) == 0:
	logger.error("There are no active locations because location_ids list from config doesn't match any location_id from Tastyigniter API response")
	logger.info("Please set correct location ID in your configuration file")
	exit(1)
else:
	logger.info("Active locations are loaded")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Send a message when the command /start is issued."""
	# Get user info
	user = update.message.from_user
	logger.info(f"User {user['id']} {user['first_name']} {user['last_name']} started the conversation")
 
	# Create a new dialogue
	dialogues[user['id']] = {}
	dialogues[user['id']]['location'] = None
 
	# Send start message
	replay_text = config['start-message']
	keyboard = []
 
	# Select location if there are more than one	
	if len(active_locations) > 1:
		replay_text += "\n\n"
		replay_text += "Please select a location"
		for location in active_locations:
			keyboard.append([InlineKeyboardButton(location['attributes']['location_name'], callback_data="location-"+str(location['id']))])
		reply_markup = InlineKeyboardMarkup(keyboard)
		await update.message.reply_text(replay_text, reply_markup=reply_markup)
	# If there is only one location, skip location selection and go to category selection
	else:
		# Retrieve menu categories
		try:
			request = f"categories?location={active_locations[0]['id']}&pageLimit=100"
			logger.info(f"Request: {request}")
			response = requests.get(f"{config['ti-url']}/{request}", headers=headers)
		except Exception:
			# Log this error to logger
			logger.error("Error while connecting to Tastyigniter API")
			logger.error(f"Status code: {response.status_code}")
			replay_text = "Error while connecting to Tastyigniter API"
			# Send retry button
			keyboard = [[InlineKeyboardButton("Retry", callback_data="retry")]]
			reply_markup = InlineKeyboardMarkup(keyboard)
			await update.message.reply_text(replay_text, reply_markup=reply_markup)
		else:
			if response.status_code == 200:
				# Save location ID to dialogue
				dialogues[user['id']]['location'] = active_locations[0]['id']
    
				keyboard = []
				replay_text = "Please select a category"
				for category in response.json()['data']:
					keyboard.append([InlineKeyboardButton(category['attributes']['name'], callback_data="category-"+str(category['id']))])
				
		reply_markup = InlineKeyboardMarkup(keyboard)
		await update.message.reply_text(replay_text, reply_markup=reply_markup)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Parses the CallbackQuery and updates the message text."""
	query = update.callback_query
	replay_text = "None"
	keyboard = []
 
	# Log this event to logger
	logger.info(f"User {query.from_user['id']} {query.from_user['first_name']} {query.from_user['last_name']} pressed button {query.data}")
 
	# Handle location selection
	if query.data.startswith("location-"):
		location_id = query.data.split("-")[1]
  
		# Check if location is active
		if int(location_id) not in config['location_ids']:
			replay_text = "This location is not active"
			return

		# Save location ID to dialogue
		dialogues[query.from_user['id']]['location'] = location_id
  
		# Retrieve menu categories
		try:
			response = requests.get(f"{config['ti-url']}/categories?location={location_id}&pageLimit=100", headers=headers)
		except Exception:
			logger.error("Error while connecting to Tastyigniter API")
		else:
			if response.status_code == 200:
				replay_text += "Please select a category"
				for category in response.json()['data']:
					keyboard.append([InlineKeyboardButton(category['attributes']['name'], callback_data="category-"+str(category['id']))])
    
    # Handle category selection
	elif query.data.startswith("category-"):
		category_id = query.data.split("-")[1]
		# Retrieve menu items
		try:
			request = f"menus?location={dialogues[query.from_user['id']]['location']}&category={category_id}&pageLimit=100"
			print(f"Request: {request}")
			response = requests.get(f"{config['ti-url']}/{request}", headers=headers)
		except Exception:
			logger.error(f"Error while retrieving menu items for location")
		else:
			if response.status_code == 200:
				keyboard = []
				replay_text = "Please select an item"
				for item in response.json()['data']:
					print(item['attributes']['menu_name'])
					keyboard.append([InlineKeyboardButton(item['attributes']['menu_name'], callback_data="item-"+str(item['id']))])
    
    # Answer the query
	await query.answer()
	# Update the message text and reply markup
	reply_markup = InlineKeyboardMarkup(keyboard)
	await query.edit_message_text(text=replay_text, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Displays info on how to use the bot."""
	await update.message.reply_text("Use /start to test this bot.")


def main() -> None:
	"""Run the telegram bot."""
	# Create the Application and pass it your bot's token.
	application = Application.builder().token(config['tg-token']).build()
 
	# Add handlers for start and help commands
	application.add_handler(CommandHandler("start", start))
	application.add_handler(CommandHandler("help", help_command))
 
	# Add a handler for callback query
	application.add_handler(CallbackQueryHandler(button))

	# Run the bot until the user presses Ctrl-C
	application.run_polling()


if __name__ == "__main__":
	main()