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
	level=logging.INFO,
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


# Create a dictionary for storing user dialogs
dialogues = {}

# Create a list for storing active Tastyigniter locations
active_locations = []

# TODO: Move this function to 
def request_api(uri: str, attempt: int = 1) -> dict:
	'''Request API and return JSON response.'''
 
	# Max number of attempts
	max_attempts = 5
 
	# Log request
	logger.info(f"Request to API ({attempt}): {uri}")
 
	# Filtrate request
	if uri.startswith("/"):
		request = uri[1:]
	else:
		request = uri

	# Create Bearer authorization header
	headers =  {"Content-Type":"application/json", "Authorization": f"Bearer {config['ti-token']}"}

	# Request API
	try:
		response = requests.get(f"{config['ti-url']}/{request}", headers=headers)
	except Exception as e:
		logger.error(f"Error {response.status_code} while connecting to Tastyigniter API")
		
		# Repeat request if there are less than 5 errors
		if attempt < max_attempts:
			attempt += 1
			return request_api(uri, attempt)
		# Exit the program if there are more than 5 errors
		else:
			logger.error("There are more than 5 errors while connecting to Tastyigniter API")
			logger.info("1. Check API URL and API token in your configuration file")
			logger.info("2. Check if Tastyigniter API is running")
			logger.info("3. Check if Tastyigniter API is accessible from this machine")
			logger.info(f"4. Check if {uri} endpoint is enabled in Tastyigniter API for this token")
			logger.error(f"Error: {e}")
			exit(1) 
	else:
		if response.status_code == 200:
			return response.json()
		elif response.status_code == 401:
			logger.error("Error: 401 Unauthorized")
		elif response.status_code == 404:
			logger.error("Error: 404 Not Found")
		else:
			logger.error(f"Error while retrieving {uri}")
			return {}


# Load active locations (and check connection)
logger.info("Loading active locations from Tastyigniter API...")
response = request_api(f"locations?location_status=true")
if response == {}:
	logger.error("Empty response from Tastyigniter API")
	exit(1)

logger.info("Connection to Tastyigniter API is successful")
# Check if there are any locations 
if len(response['data']) == 0:
	logger.error("There are no locations on Tastyigniter side")
	logger.info("Please create location on Teastyigniter side and check your configuration file")
	# TODO: offer to create location
	# Exit the program
	exit(0)

# Check if location_ids list from config matches any location_id from Tastyigniter API response
for location in response['data']:
	if int(location['id']) in config['location_ids']:
		active_locations.append(location)
		# print active locations coloring them green
		logger.info(f"[Active] {location['id']} {location['attributes']['location_name']}")
	else:
		logger.info(f"[Inactive] {location['id']} {location['attributes']['location_name']}")

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
		response = request_api(f"categories?location={active_locations[0]['id']}&pageLimit=100")
		# Save location ID to dialogue
		dialogues[user['id']]['location'] = active_locations[0]['id']
		keyboard = []
		replay_text = "Please select a category"
		for category in response['data']:
			keyboard.append([InlineKeyboardButton(category['attributes']['name'], callback_data="category-"+str(category['id']))])
				
		reply_markup = InlineKeyboardMarkup(keyboard)
		# Send message in a parse_mode: 'MarkdownV2'
		await update.message.reply_markdown_v2(replay_text, reply_markup=reply_markup)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Parses the CallbackQuery and updates the message text."""
	query = update.callback_query
	image = None
	replay_text = ''
	keyboard = []
 
	# Check if user is in the dialogue and create a new dialogue if not
	if query.from_user['id'] not in dialogues:
		dialogues[query.from_user['id']] = {}
		dialogues[query.from_user['id']]['location'] = None
 
	# Log this event to logger
	logger.info(f"User {query.from_user['id']} {query.from_user['first_name']} {query.from_user['last_name']} pressed button {query.data}")
 
	# Handle location selection
	if query.data.startswith("location-"):
		location_id = query.data.split("-")[1]
  
		# Save location ID to dialogue
		dialogues[query.from_user['id']]['location'] = location_id
  
		# Request menu categories
		response = request_api(f"categories?location={location_id}&pageLimit=100")
		replay_text += "Please select a category"
		for category in response['data']:
			keyboard.append([InlineKeyboardButton(category['attributes']['name'], callback_data="category-"+str(category['id']))])		
    
    # Handle category selection
	elif query.data.startswith("category-"):
		category_id = query.data.split("-")[1]
  	
		# Request category details
		response = request_api(f"categories/{category_id}?include=menus")
		replay_text = ''
		keyboard = []
		
		# Request menu items contained in response['included']
		replay_text += "\n\n"
		replay_text += "Please select an item"
		for item in response['included']:
			if item['type'] == 'menus':
				keyboard.append([InlineKeyboardButton(item['attributes']['menu_name'], callback_data="item-"+str(item['id']))])
    
    # Handle item info 
	elif query.data.startswith("item-"):
		item_id = query.data.split("-")[1]

		# Request item details
		response = request_api(f"menus/{item_id}?include=media")
		
		# Check is there image in response['included']
		for item in response['included']:
			if item['type'] == 'media':
				image = item['attributes']['path']
    
		# Set item name as message text
		replay_text = response['data']['attributes']['menu_name']
  
		# Set item description as message text
		if response['data']['attributes']['menu_description'] is not None:
			replay_text += "\n\n"
			replay_text += response['data']['attributes']['menu_description']
		
		# Set item price as message text
		if response['data']['attributes']['menu_price'] is not None:
			replay_text += "\n\n"
			price = str(response['data']['attributes']['menu_price'])
   			# Separate thousands with space
			for i in range(len(price)-3, 0, -3):
				price = price[:i] + " " + price[i:]
			replay_text += "Price: " + str(price)

		''' TODO: Check. Auto-generated by Copilot
		# Set item options as message text
		if response['data']['attributes']['menu_options'] is not None:
			replay_text += "\n\n"
			replay_text += "Options: " + str(response['data']['attributes']['menu_options'])
		
		# Set item ingredients as message text
		if response['data']['attributes']['menu_ingredients'] is not None:
			replay_text += "\n\n"
			replay_text += "Ingredients: " + str(response['data']['attributes']['menu_ingredients'])
		
		# Set item allergens as message text
		if response['data']['attributes']['menu_allergens'] is not None:
			replay_text += "\n\n"
			replay_text += "Allergens: " + str(response['data']['attributes']['menu_allergens'])
		'''
    # Answer the query
	await query.answer()

	# Update the message text and reply markup
	# If there is no keyboard, remove it
	if len(keyboard) == 0:
		reply_markup = None
	else:
		reply_markup = InlineKeyboardMarkup(keyboard)
  
	# If there is no text, set it to '...'
	if replay_text == '':
		replay_text = '.'
		logger.warning("Sending empty message")
  
	# Check is image valid URL and send image if it is
	if image is not None:
		# Add image to message text by putting marcdown link to it from the first string in replay_text
		replay_text = f"[{replay_text.splitlines()[0]}]({image})" + "\n\n" + "\n".join(replay_text.splitlines()[1:])
  		
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