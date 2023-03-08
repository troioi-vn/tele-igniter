#!/usr/bin/env python3
''' Telegram food ordering bot.
This bot provides a frontend for online food ordering on Telegram using Testignighter as a backend.
GitHub https://github.com/troioi-vn/tele-igniter
'''

import os, yaml, logging, requests, json, time, hashlib, random, string
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler
from telegram.constants import ParseMode

from telegram.ext import filters

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

# Chek if cache is enabled
if config['ti-api-cache']:
	logger.info("Tastyigniter API cache is enabled")
	# Create cache directory if it doesn't exist and 
	if not os.path.exists("cache"):
		os.mkdir("cache")
		logger.info("Cache directory created")
else:
	logger.info("Tastyigniter API cache is disabled")

# Create a dictionary for storing user dialogs
dialogues = {}


class Dialogue:
	'''Class for storing user dialogs.'''
	def __init__(self, user_id):
		'''Initialize Dialogue class.'''
		self.user_id = user_id # Telegram user ID
		self.user = {
			'first_name': None,
			'last_name': None,
			'phone': None,
			'location': None,
			'address': None,
			'coupon': None,
			# Tastyigniter user ID for future use in full integration with Tastyigniter user system...
			'ti_user_id': None
		}
		# Navigation
		self.nav = {
			'current_location': None,
			'current_category': None,
			'current_menu_item': None,
			'current_menu_item_options': None,
			'requested': {
				'user_location': False, # Had user requested to send his location?
				'user_phone': False, # Had user requested to send his phone number?
			},
			'text_requested_for': None,
			'after_request_screen': None,
		}
		self.cart = []

		# Load user dialog from json file
		self.load()

	def save(self):
		'''Save user dialog to json file.'''
		# Create a dictionary for storing user dialog
		dialogue = {
			'user_id': self.user_id,
			'nav': self.nav,
			'cart': self.cart,
			'user': self.user
		}
		# Save user dialog to json file
		with open(f"cache/{int(self.user_id)}.json", "w") as file:
			json.dump(dialogue, file)
		file.close()
		
	def load(self):
		'''Load user dialog from json file.'''
		# Check if user dialog file exists
		if not os.path.isfile(f"cache/{int(self.user_id)}.json"):
			logger.info(f"User dialog file {int(self.user_id)}.json not found")
			return

		# Load user dialog from json file
		with open(f"cache/{int(self.user_id)}.json", "r") as file:
			dialogue = json.load(file)
		# Update user dialog
		self.user_id = dialogue['user_id']
		self.nav = dialogue['nav']
		self.cart = dialogue['cart']
		self.user = dialogue['user']
		
	def update_cart(self, cart):
		'''Update user cart.'''
		self.cart = cart
		self.save()
  
	def update_nav(self, key: str, value: str | dict):
		'''Update user navigation.'''
		self.nav[key] = value
		self.save()
  
	def update_name(self, first_name, last_name):
		'''Update user first_name and last_name.'''
		self.user['first_name'] = first_name
		self.user['last_name'] = last_name
		self.save()

	def update_coupon(self, coupon: dict | None) -> None:
		'''Update user coupon.'''
		self.user['coupon'] = coupon
		self.save()

	def cart_append(self, item_id: int, quantity: int) -> str:
		'''Append item to user cart.'''
		# Generate unique ID for this item in cart
		uid = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
  
		# Check quantity is in reasonable range
		if quantity < 1 or quantity > config['max-quantity']:
			quantity = 1
			logging.warning(f"Quantity {quantity} is out of range")
  
		self.cart.append({
			'uid': uid,
			'id': item_id,
			'quantity': quantity,
			'options': [],
		})
		self.save()
		return uid

	def cart_remove(self, uid) -> None:
		'''Remove item from user cart.'''
		for item in self.cart:
			if item['uid'] == uid:
				self.cart.remove(item)
				self.save()

	def cart_set_quantity(self, uid, quantity) -> None:
		'''Update item quantity in user cart.'''
		for item in self.cart:
			if item['uid'] == uid:
				item['quantity'] = quantity
				self.save()
	
	def cart_set_option(self, uid, option) -> None:
		'''Update item option in user cart.'''
		for item in self.cart:
			if item['uid'] == uid:
				item['options'].append(option)
				self.save()
 
	def cart_clear(self) -> None:
		'''Clear user cart.'''
		self.cart = []
		self.save()

	def cart_count(self) -> int:
		'''Count items in user cart.'''
		count = 0
		for item in self.cart:
			count += item['quantity']
		return count

	def cart_options_count(self, uid) -> int:
		'''Count options in user cart.'''
		count = 0
		for item in self.cart:
			if item['uid'] == uid:
				count = len(item['options'])
		return count

	def cart_get_item(self, uid) -> dict:
		'''Get item from user cart.'''
		item_in_cart = None
		for item in self.cart:
			if item['uid'] == uid:
				item_in_cart = item
		return item_in_cart
	
	def nav_reset(self) -> None:
		'''Clear user navigation.'''
		for key in self.nav:
			self.nav[key] = None
		self.save()


class TastyIgniter:
	'''API class for Tastyigniter API requests.'''
	def __init__(self):
		'''Initialize API class.'''
		self.token = config['ti-token'] # Tastyigniter API token
		self.url = config['ti-url'] # Tastyigniter API URL
		self.attempts = 0 # Number of attempts to connect to API
  
		self.active_locations = [] # Locations list
		self.locations = {} # Locations dictionary by location_id
		self.menus = {} # Menus dictionary by ['location_id']['category_id']
  
		self.categories = {} # Categories dictionary by category ID
		self.menu_items = {} # Menu items dictionary by menu item ID
		self.menu_options = {} # Menu options dictionary by menu option ID
		self.currencies = {} #Currencies dictionary by currency ID
		self.coupons = {} # Coupons dictionary by coupon ID

		self.api_request_counter = 0 # Number of API requests
 
		# Connect to Tastyigniter API
		logger.info("Connecting to Tastyigniter API...")
  
		# Get active locations for connection check
		response = self.request(f"locations?location_status=true")['data']

		# Check if there are any locations 
		if len(response) == 0:
			logger.error("There are no locations on Tastyigniter side")
			logger.info("Please create location on Teastyigniter side and check your configuration file")
			# TODO: offer to create location through bot and add it to config
			exit(0)
		# Check if location-ids list from config matches any location_id from Tastyigniter API response
		for location in response:
			if int(location['id']) in config['location-ids']:
				self.active_locations.append(location)
				# print active locations coloring them green
				logger.info(f"[Active] {location['id']} {location['attributes']['location_name']}")
			else:
				logger.info(f"[Inactive] {location['id']} {location['attributes']['location_name']}")
		# Check if there are any active locations
		if len(self.active_locations) == 0:
			logger.error("location-ids list from config doesn't match any location_id on Tastyigniter side")
			logger.info("Please set correct location ID in your configuration file")
			exit(1)
		
		# Get categories list 
		categories_list = self.request(f"categories?include=locations&pageLimit=1000")['data']
		# Get categories details
		for category in categories_list:
			category_id = int(category['id'])
			self.categories[category_id] = self.request(f"categories/{category_id}?include=menus,locations")['data']

		# Get menu options list
		self.menu_options = self.request(f"menu_item_options?pageLimit=1000")['data']

		# Get currencies list
		self.currencies = self.request(f"currencies?enabled=true&pageLimit=1000")['data']
		
		# Get coupons list
		self.coupons = self.request(f"coupons?include=menus&enabled=true&pageLimit=1000")['data']
   
		logger.info("Loading menus for active locations...")
		# Load categories and menu items for each active location
		for location in self.active_locations:
			location_id = int(location['id'])
			# Get location details
			self.locations[location_id] = self.request(f"locations/{location_id}?include=working_hours,media")['data']
   
			# Load menu
			self.menus[location_id] = self.load_menu(location_id)
  
		# Print active locations titles (TODO: with working hours)
		for location_id in self.locations:
			print(f"{self.locations[location_id]['attributes']['location_name']}")
			# Print categories and menu item
			for category_id in self.menus[location_id]:
				print(f"  {self.categories[category_id]['attributes']['name']}")
				# Print menu items in category
				for menu_item_id in self.menus[location_id][category_id]:
					print(f"    {self.menu_items[menu_item_id]['data']['attributes']['menu_name']} {self.menu_items[menu_item_id]['data']['attributes']['menu_price']}")

		# Print an ASCII cat please
		print(r"""
		\    /\
		 )  ( ')
		(  /  )
		 \(__)|""") # Copilot is a great tool for writing code

	def load_menu(self, location_id: int) -> dict:
		'''Load menu for a specific location.'''
		menu = {} # {category_id: {menu_items_ids}}
  
		# Get menu items list for location
		menu_items_list = self.request(f"menus?location={location_id}&include=media")['data']
		# print(menu_items_list)

		# Iterate through categories
		for category_id in self.categories:
			# Check if category belongs to location
			if {'type': 'locations', 'id': str(location_id)} in self.categories[category_id]['relationships']['locations']['data']:
				menu[category_id] = []
				# Iterate through menu items	
				for menu_item in menu_items_list:
					menu_item_id = int(menu_item['id'])
					# Add menu item to menu dictionary if it is not already there
					if menu_item_id not in self.menu_items:
						# Get menu items details
						self.menu_items[menu_item_id] = self.request(f"menus/{menu_item_id}?include=media,categories,menu_options")

					# Check if menu item belongs to category
					if {'type': 'categories', 'id': str(category_id)} in self.menu_items[menu_item_id]['data']['relationships']['categories']['data']:
						menu[category_id].append(menu_item_id)

		return menu
		
	def request(self, uri: str) -> dict:
		'''Request any API endpoint and return JSON response.'''
		resp = [] # Response

		# Log request
		logger.info(f"API ({self.attempts}): {uri}")
  
		# Filtrate request
		if uri.startswith("/"):
			request = uri[1:]
		else:
			request = uri
		# Check if there is a cached response if caching is enabled
		if config['ti-api-cache']:
			# Generate filename from URI via md5 hash
			filename = hashlib.md5(uri.encode()).hexdigest()
			if os.path.isfile(f"cache/{filename}.json"):
				with open(f"cache/{filename}.json", "r") as f:
					return json.load(f)

		# Delay every 30 requests to avoid 429 error
		self.api_request_counter += 1
		if self.api_request_counter == 30:
			print("Waiting 0.5 seconds to avoid 429 error")
			time.sleep(0.5)
			self.api_request_counter = 0
			return self.request(uri)

		# Create Bearer authorization header
		headers =  {"Content-Type":"application/json", "Authorization": f"Bearer {self.token}"}

		# Request API
		try:
			response = requests.get(f"{self.url}/{request}", headers=headers)
		except Exception as e:
			logger.error(f"Error {response.status_code} while connecting to Tastyigniter API")		
			# Repeat request if there are less than 5 errors
			if self.attempts < config['ti-api-max-attempts']:
				self.attempts += 1
				return self.request(uri)
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
				# Reset attempts counter
				self.attempts = 0
				# Return JSON response
				resp = response.json()

				# Cache response to file if caching is enabled
				if config['ti-api-cache']:
					# Save response to file
					# Generate filename from URI via md5 hash
					filename = hashlib.md5(uri.encode()).hexdigest()
					with open(f"cache/{filename}.json", "w") as file:
						file.write(json.dumps(resp, indent=4))
				return resp # Return JSON response
			else:
				logger.error(f"Error while retrieving {uri}")
				logger.error(f"Error {response.status_code}: {response.text}")
				exit(1)

	def get_item_options(self, item_id) -> list:
		'''Get item options from user cart.'''
		# WARNING: For now only one option and only radio buttons are supported
		available_item_options = []
		for menu_option in self.menu_items[item_id]['included']:
			if menu_option['type'] == 'menu_options':
				if menu_option['attributes']['display_type'] == 'radio': # Only radio buttons are supported
					available_item_options.append(menu_option)
					break
		return available_item_options

	def get_coupon(self, coupon_code: str) -> dict:
		'''Check if coupon code is valid.'''
		# Find coupon by code in coupons dictionary
		for coupon in ti.coupons:
			if coupon['attributes']['code'] == coupon_code:
				return coupon
		return None


class helpers:
	'''Helper functions.'''
	def __init__(self):
		pass

	def format_amount(self, amount: float | int | str, code: str = config['ti-currency-code'], decimals: int = 0) -> str:
		'''Format amount to string with currency symbol.'''
		# Convert amount to float
		amount = float(amount)
		# Add thousands separator if amount is greater than 1000
		if amount > 1000:
			amount = f"{amount:,.{decimals}f}"
		else:
			amount = f"{amount:.{decimals}f}"

		# Replace coma with space
		amount = amount.replace(",", " ")

		# Get currency symbol from ti.currencies dictionary by an attribute currency_code
		currency_symbol = next((currency['attributes']['currency_symbol'] for currency in ti.currencies if currency['attributes']['currency_code'] == code), None)
		# Return formatted amount
		return f"{amount} {currency_symbol}"


def dialogue_run(user: dict) -> Dialogue:
    # Create a new dialogue for this user in global dialogues dictionary
	if user['id'] not in dialogues:
		dialogues[user['id']] = Dialogue(user['id'])
		logger.info(f"Created new dialogue for user {user['id']}")
	
	# Update user name if it has changed
	if dialogues[user['id']].user['first_name'] != user['first_name'] or dialogues[user['id']].user['last_name'] != user['last_name']:
		dialogues[user['id']].update_name(user['first_name'], user['last_name'])
 
	return dialogues[user['id']]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Send a start-message and a keyboard with all locations on /start command."""
	# Delete cached user json file from cache folder named by user ID.json
	filename = f"cache/{update.message.from_user['id']}.json"
	if os.path.isfile(filename):
		logger.info(f"Deleting cached user file {filename}")
		os.remove(filename)
 
	dialogue = dialogue_run(update.message.from_user)
	logger.info(f"User {dialogue.user_id} sent /start command")

	# Send start message
	reply_text = config['start-message']
	keyboard = []
	
	# Single location mode
	if len(ti.active_locations) == 1:
		# Save location ID to dialogue
		dialogue.update_nav('current_location', ti.active_locations[0]['id'])
		# Create continue button
		keyboard = [[InlineKeyboardButton("Continue", callback_data="location-"+str(ti.active_locations[0]['id']))]]
	else:
		reply_text += "\n\n" + "Please select a Restaurant:"
		for location in ti.active_locations:
			keyboard.append([InlineKeyboardButton(location['attributes']['location_name'], callback_data="location-"+str(location['id']))])
	
	reply_markup = InlineKeyboardMarkup(keyboard)
	
	await update.message.reply_text(reply_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	"""Parses the CallbackQuery and updates the message text."""
	query = update.callback_query
	dialogue = dialogue_run(query.from_user)	
 
	# Log this event to logger
	logger.info(f"User {dialogue.user_id} pressed button {query.data}")
	
 
	# If current location is not set, set it to the first active location
	if dialogue.nav['current_location'] is None:
		dialogue.nav['current_location'] = ti.active_locations[0]['id']
 
	# Variables for reply
	reply_text = ''
	reply_markup = None
	navigation_buttons = []
	keyboard = []
	image = None
 
	# Handle home section (location selection)
	if query.data.startswith("location-"):
		location_id = int(query.data.split("-")[1])
		menu = ti.menus[location_id]
  
		# Check if location is active
		if location_id not in [int(location['id']) for location in ti.active_locations]:
			logger.warning(f"User {dialogue.user_id} tried to select inactive location {location_id}")
			return
  
		# Save current location ID to dialogue
		dialogue.update_nav('current_location', location_id)
 
		# Add location name to reply text
		reply_text += f"📍<b>{ti.locations[location_id]['attributes']['location_name']}</b>"
		
		# Offer to select a category 
		for category_id in menu:
			category = ti.categories[category_id]
			# Add categories to keyboard
			keyboard.append([InlineKeyboardButton(category['attributes']['name'], callback_data="category-"+str(category_id))])
  
		if len(keyboard) > 0:
			reply_text += "\n\n" + "Please select a category"
		else:
			reply_text += "\n\n" + "There are no categories for this location"
			
    # Handle category section
	elif query.data.startswith("category-"):
		category_id = int(query.data.split("-")[1])
		location_id = dialogue.nav['current_location']
		menu = ti.menus[location_id]
  
		# Save current category ID to dialogue
		dialogue.update_nav('current_category', category_id)
  
		# Add category name to reply text
		reply_text += f"<b>{ti.categories[category_id]['attributes']['name']}</b>"
  
		# Offer to select an item
		for item_id in ti.menus[location_id][category_id]:
			item = ti.menu_items[item_id]
			# Format price with spaces after every 3 digits from the end
			price = "{:,}".format(item['data']['attributes']['menu_price']).replace(",", " ")
			# Add items to keyboard
			keyboard.append([InlineKeyboardButton(f"{item['data']['attributes']['menu_name']} {price} {item['data']['attributes']['currency']}", callback_data="item-"+str(item_id))])
		
		if len(keyboard) > 0:
			reply_text += "\n\n" + "Please select an item"
		else:
			reply_text += "\n\n" + "There are no items in this category"
  
		# Create back button to location
		keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="location-"+str(dialogue.nav['current_location']))])
		
    # Handle item section 
	elif query.data.startswith("item-"): # Format "item-{id}-{action}-{params}"
		# Get item ID from button data
		item_id = int(query.data.split("-")[1])
		# Get action 
		action = query.data.split("-")[2] if len(query.data.split("-")) > 2 else None
		# Get parameters
		params = query.data.split("-")[3] if len(query.data.split("-")) > 3 else None
  
		# Get item data
		item = ti.menu_items[item_id]['data']
  
		location_id = dialogue.nav['current_location']
		category_id = dialogue.nav['current_category']
		menu = ti.menus[location_id]

		# Show item main screen
		if action == None:  
			# Add item name to reply text
			reply_text = f"<b>{item['attributes']['menu_name']}</b>"
    
			# Count this items in cart and add to reply text
			item_quantity = 0
			if len(dialogue.cart) > 0:
				# Count items with the same ID
				item_quantity = sum(item['quantity'] for item in dialogue.cart if item['id'] == item_id)

			# Add item quantity to reply text
			if item_quantity > 0:
				reply_text += f" (in a cart: {item_quantity})"
				
			# Add item description to reply text
			reply_text += f"\n\n{item['attributes']['menu_description']}"

			# Add item price to reply text
			price = "{:,}".format(item['attributes']['menu_price']) # Separate thousands with space
			reply_text += "\n\n" + f"Price: {price} {item['attributes']['currency']}"
			
			# Check is there image for this item
			if 'included' in ti.menu_items[item_id]:
				for attachment in ti.menu_items[item_id]['included']:
					if attachment['type'] == 'media':
						image = attachment['attributes']['path']

			# Create add to cart button
			keyboard.append([InlineKeyboardButton("🛒 Add to cart", callback_data=f"item-{str(item_id)}-addtocart")])
			# Handle item navigation
			keyboard_row = []
			# Create back button to category
			keyboard_row.append(InlineKeyboardButton("⬅️ Back", callback_data="category-"+str(dialogue.nav['current_category'])))
	
			# If there are more than one item in this menu category build navigation buttons
			if len(menu[category_id]) > 1:
				# Find current item index in menu[category_id]
				current_item_index = menu[category_id].index(item_id)

				# Add to reply text N of M
				reply_text += f"\n\n{current_item_index+1} of {len(menu[category_id])}"

				# Find previous item id in menu[category_id] if current item is not the first one
				if current_item_index > 0:
					previous_item_id = menu[category_id][current_item_index-1]
					keyboard_row.append(InlineKeyboardButton("<<<", callback_data="item-"+str(previous_item_id)))
			
				# Find next item id in menu[category_id] if current item is not the last one
				if current_item_index < len(menu[category_id])-1:
					next_item_id = menu[category_id][current_item_index+1]
					keyboard_row.append(InlineKeyboardButton(">>>", callback_data="item-"+str(next_item_id)))
		
			# Add keyboard row to keyboard
			if len(keyboard_row) > 0:
				keyboard.append(keyboard_row)

		# Handling Add to Cart
		elif action == "addtocart":
			# Ask the user for a quantity
			if params == None:
				# Add text to reply
				reply_text += "\n\nHow many?"
		
				# Add quantity buttons.
				keyboard_row = []
				for i in range(1, 6):
					keyboard_row.append(InlineKeyboardButton(str(i), callback_data=f"item-{str(item_id)}-addtocart-{str(i)}"))
					if i % 3 == 0:
						keyboard.append(keyboard_row)
						keyboard_row = []
				# Add last row if it is not full
				if len(keyboard_row) > 0:
					keyboard.append(keyboard_row)

				# Create back button to item
				keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="item-"+str(item_id))])

			# Add an item to cart and ask for options if there are any
			# Check if quantity is valid
			elif int(params) > 0 and int(params) <= config['max-quantity']:
				# Get quantity from params
				quantity = int(params)	
    
				# Add item to the cart and get its uid
				uid = dialogue.cart_append(item_id, quantity)

				# Add text to reply
				reply_text += f"{quantity} x {item['attributes']['menu_name']} added to your cart ✅"

				available_item_options = ti.get_item_options(item_id)
				# Ask user for an option if there are any				
				if len(available_item_options) > 0:
					dialogue.nav['current_menu_item_options'] = available_item_options[0]
					option = available_item_options[0] # Get first option. This is a temporary solution.
					# A result of print(option) is:
					# {"type": "menu_options", "id": "11", "attributes": {"menu_option_id": 11, "option_id": 5, "menu_id": 11, "required": "False", "priority": 0, "min_selected": 0, "max_selected": 0, "created_at": "2022-11-18T04:18:54.000000Z", "updated_at": "2022-11-18T04:18:54.000000Z", "option_name": "Frying options", "display_type": "radio", "option": {"option_id": 5, "option_name": "Frying options", "display_type": "radio", "priority": 0, "update_related_menu_item": 0, "created_at": "2022-11-18T04:14:23.000000Z", "updated_at": "2022-11-18T04:14:23.000000Z"}, "menu_option_values": [{"menu_option_value_id": 24, "menu_option_id": 11, "option_value_id": 11, "new_price": 0, "priority": 0, "is_default": "True", "created_at": "2022-11-18T04:18:54.000000Z", "updated_at": "2022-11-18T05:04:37.000000Z", "name": "Oil frying", "price": 0, "option_value": {"option_value_id": 11, "option_id": 5, "value": "Oil frying", "price": 0, "priority": 5, "stock_qty": 0, "option": {"option_id": 5, "option_name": "Frying options", "display_type": "radio", "priority": 0, "update_related_menu_item": 0, "created_at": "2022-11-18T04:14:23.000000Z", "updated_at": "2022-11-18T04:14:23.000000Z", "locations": []}, "stocks": []}}, {"menu_option_value_id": 25, "menu_option_id": 11, "option_value_id": 12, "new_price": 0, "priority": 1, "is_default": "False", "created_at": "2022-11-18T04:18:54.000000Z", "updated_at": "2022-11-18T05:04:37.000000Z", "name": "Dry frying", "price": 0, "option_value": {"option_value_id": 12, "option_id": 5, "value": "Dry frying", "price": 0, "priority": 1, "stock_qty": 0, "option": {"option_id": 5, "option_name": "Frying options", "display_type": "radio", "priority": 0, "update_related_menu_item": 0, "created_at": "2022-11-18T04:14:23.000000Z", "updated_at": "2022-11-18T04:14:23.000000Z", "locations": []}, "stocks": []}}]}, "relationships": {"menu_option_values": {"data": [{"type": "menu_option_values", "id": "24"}, {"type": "menu_option_values", "id": "25"}]}}}
     
					# Check if there are unselected options
					if len(available_item_options) > dialogue.cart_options_count(uid):
						# Ask user for an option
						reply_text = f"Please select an option."

						# Add option name to
						reply_text += f"\n\n<b>{option['attributes']['option_name']}</b>"
		
						# Add buttons for each option value
						default_option_value_id = None
						for option_value in option['attributes']['menu_option_values']:
							# Check if this option is default
							if option_value['is_default']:
								default_option_value_id = option_value['option_value_id']

							# Add option button
							keyboard.append([InlineKeyboardButton(f"{option_value['name']} (+{h.format_amount(option_value['price'])} VND)", callback_data=f"cart-{str(uid)}-setoption-{str(option_value['menu_option_value_id'])}")])
						
						# Add Skip button if option is not required and default option value is set
						if not option['attributes']['required']:
							keyboard.append([InlineKeyboardButton("Skip", callback_data=f"cart-{str(uid)}-setoption-{str(default_option_value_id)}")])

					else:
						# Set reply text
						reply_text = "No options available"
				
				
				# Create cancel button leadeing to remove item from cart
				keyboard.append([InlineKeyboardButton("Cancel", callback_data="cart-"+str(uid)+"-remove")])
			else:
				# Set reply text
				reply_text = "Invalid quantity"
				# Create back button to item
				keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="item-"+str(item_id))])

	# Handle cart and cart actions
	elif query.data.startswith("cart"): # Format: "cart-{uid}-{action}-{params}"
		# Get uid from query if exists
		uid = query.data.split("-")[1] if len(query.data.split("-")) > 1 else None
		# Get action from query
		action = query.data.split("-")[2] if len(query.data.split("-")) > 2 else None
		# Get params from query
		params = query.data.split("-")[3] if len(query.data.split("-")) > 3 else None
  
		# Handle cart
		if action == None:
			# Check if cart is empty
			if len(dialogue.cart) == 0:
				reply_text += "\n\nCart is empty"
			else:
				# Set message text
				reply_text = "🛒 <b>Your order is:</b>\n"
				# Show items in cart and sum subtotal price
				subtotal = 0
				k = 0
				for cart_item in dialogue.cart:
					k += 1
					item = ti.menu_items[cart_item['id']]['data']
					subtotal += item['attributes']['menu_price'] * cart_item['quantity']
					# Add items to the message text
					if cart_item['quantity'] == 1:
						reply_text += f"\n<b>{k}. {item['attributes']['menu_name']}</b>  {h.format_amount(item['attributes']['menu_price'])}"
					else:
						reply_text += f"\n<b>{k}. {item['attributes']['menu_name']}</b>  {h.format_amount(item['attributes']['menu_price'])} x {cart_item['quantity']}"
						items_prise = item['attributes']['menu_price'] * cart_item['quantity']
						reply_text += f" = {h.format_amount(items_prise)}"
					# Add options to the message text
					if len(cart_item['options']) > 0:
						for option in cart_item['options']:
							reply_text += f"\n{option['name']} (+{h.format_amount(option['price'])})"
							subtotal += option['price']

				total = subtotal
				discount = 0
    
				# Apply coupon			
				if dialogue.user['coupon'] != None:
					coupon = dialogue.user['coupon']
					# Check coupon type
					if coupon['attributes']['type'] == "F": # Fixed amount
						discount = float(coupon['attributes']['discount'])
						reply_text += f"\n\n🎁 <code>{coupon['attributes']['code']}</code> (-{h.format_amount(discount)})"
						total -= discount
					elif coupon['attributes']['type'] == "P": # Percentage
						discount = subtotal * coupon['attributes']['discount'] / 100
						reply_text += f"\n\n🎁 <code>{coupon['attributes']['code']}</code> (-{coupon['attributes']['discount']}%)"
						total -= discount
      
				# If discount is greater than subtotal, set discount to subtotal
				if discount > subtotal:
					discount = subtotal
     
				# If total is less than 0, set total to 0
				if total < 0:
					total = 0
     
				# If discount > 0 add discount to message text
				if discount > 0:
					reply_text += f"\n\nSubtotal: {h.format_amount(subtotal)}"
					reply_text += f"\nDiscount: -{h.format_amount(discount)}"
					reply_text += f"\n<b>Total: {h.format_amount(total)}</b>"
				else:
					reply_text += f"\n\n<b>Total: {h.format_amount(total)}</b>"
				
				# Add checkout button
				keyboard.append([InlineKeyboardButton("✅ Checkout", callback_data="cart-0-checkout")])
				# Create clear cart and edit cart buttons
				keyboard.append([
					InlineKeyboardButton("🗑 Clear cart", callback_data="cart-0-clear"),
					InlineKeyboardButton("✏️ Edit cart", callback_data="cart-0-edit")]
				)
				# Create button for enter coupon code
				keyboard.append([InlineKeyboardButton("🎁 Enter coupon code", callback_data="cart-0-coupon")])
    
				# Print coupon code
				#if dialogue.coupon != None:
				#	reply_text += f"\n\n<b>Coupon code</b> - {dialogue.coupon['code']}"
		# Handle clear cart
		elif action == "clear":
			# Clear cart
			dialogue.cart_clear()
			# Set message text
			reply_text = "Cart cleared"
		# Handle edit cart
		elif action == "edit":
			print("edit")
			# Add text to reply
			reply_text += "\n\nPlease select an item to edit"
			# Add items to reply text
			for item_in_catrt in dialogue.cart:
				item = ti.menu_items[item_in_catrt['id']]['data']
				# Add edit buttons
				keyboard.append([InlineKeyboardButton(f"{item['attributes']['menu_name']} x {item_in_catrt['quantity']} ✏️", callback_data=f"cart-{str(item_in_catrt['uid'])}-setquantity")])
				keyboard.append([InlineKeyboardButton(f"{item['attributes']['menu_name']} x {item_in_catrt['quantity']} ❌ ", callback_data=f"cart-{str(item_in_catrt['uid'])}-remove")])
			# Add clear cart button
			keyboard.append([InlineKeyboardButton("Clear cart", callback_data="cart-0-clear")])
			# Create back button to cart
			keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="cart")])
		# Handle remove item from cart
		elif action == "remove":
				# Remove item from cart
				dialogue.cart_remove(uid)
				# Set reply text
				reply_text += "\n\nItem removed from cart"
				# Create back button to cart
				keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="cart")])
		# Handle set quantity for item in cart
		elif action == "setquantity":
				# Ask user for quantity
				if params == None:
					# Add text to reply
					reply_text += "\n\nHow many?"
			
					# Add quantity buttons
					keyboard_row = []
					for i in range(1, 6):
						keyboard_row.append(InlineKeyboardButton(str(i), callback_data=f"cart-{str(uid)}-setquantity-{str(i)}"))
					keyboard.append(keyboard_row)
			
					# Create back button to cart
					keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="cart")])
				else:
					# Set quantity for item in cart
					dialogue.cart_set_quantity(uid, int(params))
					# Set reply text
					reply_text += f"\n\nQuantity set to {params}"
					# Create back button to cart
					keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="cart")])
		# Handle set options for item in cart
		elif action == "setoption":
			# Get item from cart
			item_in_cart = dialogue.cart_get_item(uid)
			# Get item
			item_id = item_in_cart['id']
			item = ti.menu_items[item_id]['data']
			# Get options
			available_item_options = ti.get_item_options(item_id)
			# Get option valie id
			option_value = int(params)
			
			# As temp solution, we only support one option
			option = available_item_options[0]
			
			# Find option in cart item
			selected_option = None
			for attribute in option['attributes']:
				if attribute == 'menu_option_values':
					menu_option_values = option['attributes']['menu_option_values']
					for menu_option_value in menu_option_values:
						if int(menu_option_value['menu_option_value_id']) == option_value:
							# Set selected option
							selected_option = menu_option_value
							break
   
			dialogue.cart_set_option(uid, selected_option)
   
			# Set reply text
			reply_text += f"\n\nOption set to {selected_option['name']}"
   
			# Create button the item in the menu item-{item_id}
			keyboard.append([InlineKeyboardButton(f"⬅️ Back to {item['attributes']['menu_name']}", callback_data=f"item-{item_id}")])
   
			# Create cart button
			keyboard.append([InlineKeyboardButton("🛒 Cart", callback_data="cart")])

			# Create checkout button
			keyboard.append([InlineKeyboardButton("✅ Checkout", callback_data="cart-0-checkout")])	
		# Coupon code handling
		elif action == "coupon":
			# Wait for coupon code
			dialogue.update_nav('text_requested_for', 'coupon_code')
			dialogue.update_nav('after_request_screen', 'cart')
   
			# Add text to reply
			reply_text += "\n\nPlease send me a coupon code"
			# Create back button to cart
		# Handle checkout
		elif action == "checkout":
				# Check if cart is empty
				if len(dialogue.cart) == 0:
					reply_text += "\n\nCart is empty"
				else:
					# Show items in cart and sum subtotal price
					subtotal = 0
					for cart_item in dialogue.cart:
						item = ti.menu_items[cart_item['id']]['data']
						subtotal += item['attributes']['menu_price'] * cart_item['quantity']
						# Add items to message text
						reply_text += f"\n\n<b>{item['attributes']['menu_name']}</b> - {h.format_amount(item['attributes']['menu_price'])} x {cart_item['quantity']}"
					# Add subtotal to message text
					reply_text += f"\n\n<b>Subtotal</b> - {subtotal} VND"
					# Add checkout button
					keyboard.append([InlineKeyboardButton("Checkout", callback_data="cart-0-checkout-confirm")])
			
	# Handle location reset request and confirmation
	elif query.data.startswith("resetlocation-"):
		# Get step from button data
		step = str(query.data.split("-")[1])
		reply_text += "\n\n" + "Restet location"
		# Handle request
		if step == "request":
			# If cart is not empty, add warning to message text
			if len(dialogue.cart) > 0:
				reply_text = "Your cart will be cleared"
				# Create confirm button
				keyboard.append([InlineKeyboardButton("Ok", callback_data="resetlocation-confirm")])
				# Create cancel button
				keyboard.append([InlineKeyboardButton("Cancel", callback_data="location-"+str(dialogue.nav['current_location']))])
			else:
				step = "confirm"
				
		if step == "confirm":
			# Clear cart
			dialogue.cart_clear()
			# Reset navigation
			dialogue.nav_reset()
   
			# Offer to select location
			reply_text += "\n\n" + "Please select a Restaurant:"
			for location in ti.active_locations:
				keyboard.append([InlineKeyboardButton(location['attributes']['location_name'], callback_data="location-"+str(location['id']))])
 
    # Answer the query
	await query.answer()

	# Update the message text and reply markup
	# KEYBOARD MANAGEMENT #
	# Reset location button
	if not query.data.startswith("resetlocation") and len(ti.active_locations) > 1:
		# If it is home section, add reset location button
		if query.data.startswith("location-"):
			navigation_buttons.append([InlineKeyboardButton("📍", callback_data="resetlocation-request")])
  
	# Home and cart buttons management
	show_home_button = True
	show_cart_button = False
 	# Add cart button if cart is not empty and current action is not cart
	items_in_cart = dialogue.cart_count()
	if items_in_cart > 0: show_cart_button = True
	if query.data.startswith("cart"): show_cart_button = False
	if query.data.startswith("cart-0-coupon"): show_home_button = False
	elif query.data.startswith("location-"): show_home_button = False
	# contains addtocart but not ended with addtocart
	elif "addtocart" in query.data and not query.data.endswith("addtocart"):
		show_home_button = False
		show_cart_button = False
  
	if show_cart_button:
		navigation_buttons.append([InlineKeyboardButton(f"🛒 Cart ({items_in_cart})", callback_data="cart")])
  
	# If location is set, add home button to navigation buttons
	if dialogue.nav['current_location'] & show_home_button:
		navigation_buttons.append([InlineKeyboardButton("🏠 Home", callback_data="location-"+str(dialogue.nav['current_location']))])
	
	# Add navigation buttons if there are any
	keyboard += navigation_buttons
	if len(keyboard) > 0:
		reply_markup = InlineKeyboardMarkup(keyboard)

	# If there is no text, set it to '...'
	if reply_text == '':
		reply_text = config['unknown-err']
		logger.warning("Sending empty message")
	# Add image to message text by putting a dot at the end wrapped in html link tag
	if image is not None:
		reply_text = reply_text + f" <a href=\"{image}\">.</a>"
	
	await query.message.edit_text(reply_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)


async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	'''Handle any message that is not a command'''
	query = update.message
	dialogue = dialogue_run(query.from_user)
 
	# Variables for reply
	reply_text = ''
	reply_markup = None
	navigation_buttons = []
	keyboard = []
	image = None
 
	# If we have a text message
	if query.text is not None:
		text = query.text
		# Handle coupone code if text_requested_for == 'coupon_code'
		if dialogue.nav['text_requested_for'] == 'coupon_code':
			coupon = ti.get_coupon(text)
			if coupon is not None:
				# Add coupon to cart
				# dialogue.cart_add_coupon(coupon)
				# Add text to reply
				reply_text += f"Coupon {text} added!"
    
				# Add coupon to cart
				dialogue.update_coupon(coupon)
    
				# Send sticker
				await query.reply_sticker(config['success-sticker'])
			else:
				reply_text += f"Coupon {text} is not valid!"
    
			# Add back button
			keyboard = [[InlineKeyboardButton("Back", callback_data=f"{dialogue.nav['after_request_screen']}")]]

   			# Reset text_requested_for
			dialogue.update_nav('text_requested_for', None)

	# Add navigation buttons if there are any
	keyboard += navigation_buttons
	if len(keyboard) > 0:
		reply_markup = InlineKeyboardMarkup(keyboard)

	# If there is no text, set it to '...'
	if reply_text == '':
		reply_text = config['unknown-err']
		logger.warning("Sending empty message")
	# Add image to message text by putting a dot at the end wrapped in html link tag
	if image is not None:
		reply_text = reply_text + f" <a href=\"{image}\">.</a>"
	
	await query.reply_text(reply_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

	'''
	# Do we have a location message?
	if update.message.text is None:
		if update.message.location is not None:
			# Get location
			location = update.message.location
			# TODO: Get closest location
			# closest_location = ti.get_closest_location(location.latitude, location.longitude)
			# Set location
			# dialogue.nav_set_location(closest_location['id'])
			# Send location message
			# await update.message.reply_text(f"Your location has been set to {closest_location['attributes']['location_name']}")
			print(location)
			# Send latitute and longitude to user
			await update.message.reply_text(f"{location.latitude}, {location.longitude}")
			return

		if update.message.contact is not None:
			# Get contact
			contact = update.message.contact
			# Send contact message
			await update.message.reply_text(f"Your phone number is +{contact.phone_number}")
			return

	# Request location if '/set' is sent
	if update.message.text == "/set":
		# Send location request
		await update.message.reply_text("Please send your location", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Send location", request_location=True)]], one_time_keyboard=True))
		return
	
	# Request telephone number if '/phone' is sent
	if update.message.text == "/phone":
		# Send contact sare request
		await update.message.reply_text("Please send your phone number", reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Send phone number", request_contact=True)]], one_time_keyboard=True))	

	# replay with the same message
	await update.message.reply_text(update.message.text)
	'''


def main() -> None:
	"""Run the telegram bot."""
	# Create the Application and pass it your bot's token.
	application = Application.builder().token(config['tg-token']).build()
 
	# Add handlers for start and help commands
	application.add_handler(CommandHandler("start", start))
 
	# Add a handler for callback query
	application.add_handler(CallbackQueryHandler(button))

	# Add a handler for text messages
	application.add_handler(MessageHandler(filters.TEXT | filters.LOCATION | filters.CONTACT, msg))

	# Run the bot until the user presses Ctrl-C
	application.run_polling()


if __name__ == "__main__":
	ti = TastyIgniter()
	h = helpers()
	main()