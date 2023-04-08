#!/usr/bin/env python3
''' Telegram food ordering bot.
This bot provides a frontend for online food ordering on Telegram using Testignighter as a backend.
GitHub https://github.com/troioi-vn/tele-igniter
'''

import os, logging, re

from classes import Config
from dialogue import DialoguesManager
from tastyigniter import TastyIgniter
from helpers import format_amount

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode, MessageEntityType
from telegram.error import BadRequest


async def process_usser_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ All user actions are handled here.
    CallbackQueris, Commands, Text messages, Location messages, Phone messages."""
    
    # Get user dialogue or create a new one
    dialogue = dm.get_dialog(update.effective_user)
    dialogue.new_answer()
    
    # Check if this is a command
    if update.message is not None and update.message.entities is not None and update.message.entities[0].type == MessageEntityType.BOT_COMMAND:
        command = update.message.text.split()[0]
        logger.info(f"User {dialogue.user_id} sent command {command}")

        # Handle /start command
        if command == "/start":
            # Send start message
            dialogue.reply_text = config['start-message']
            dialogue.home_button = False
            dialogue.cart_button = False
            
            # Single location mode
            if len(ti.active_locations) == 1:
                # Save location ID to dialogue
                dialogue.update_nav('current_location', ti.active_locations[0]['id'])
                # Create continue button
                dialogue.keyboard = [[InlineKeyboardButton("Continue", callback_data="location-"+str(ti.active_locations[0]['id']))]]
            else:
                dialogue.reply_text += "\n\n" + "Please select a Restaurant:"
                for location in ti.active_locations:
                    dialogue.keyboard.append([InlineKeyboardButton(location['attributes']['location_name'], callback_data="location-"+str(location['id']))])

    elif update.callback_query is not None:
        query = update.callback_query        
        dialogue.existed_message = True
        
        # Log this event to logger
        logger.info(f"User {dialogue.user_id} pressed button {query.data}")

        location_id = dialogue.nav_get_current_location()

        # Handle home section (location selection)
        if query.data.startswith("location-"):
            location_id = int(query.data.split("-")[1])
            menu = ti.menus[location_id]
            dialogue.home_button = False
            
    
            # Check if location is active
            if location_id not in [int(location['id']) for location in ti.active_locations]:
                logger.warning(f"User {dialogue.user_id} tried to select inactive location {location_id}")
                return
    
            # Save current location ID to dialogue
            dialogue.update_nav('current_location', location_id)

            location = ti.get_location_info(location_id)
            
            # Add location name to reply text
            dialogue.reply_text += f"📍<b>{location['attributes']['location_name']}</b>"
            
            # If user is admin, add admin tag
            if dialogue.user_id in config['admins']:
                dialogue.reply_text += f" [admin]"
            
            # Add location description to reply text
            dialogue.reply_text += f"\n{location['attributes']['description']}"
                        
            location_statuses = ti.get_location_statuses(location_id)
            
            dialogue.reply_text += "\n"
            
            if location_statuses['delivery']['status']:
                dialogue.reply_text += f"\n✅ Delivery until {location_statuses['delivery']['ends']}"
            else:
                dialogue.reply_text += f"\n⏸ Delivery will open at {location_statuses['delivery']['starts']}"
            
            if location_statuses['pickup']['status']:
                dialogue.reply_text += f"\n✅ Pickup until {location_statuses['pickup']['ends']}"
            else:
                dialogue.reply_text += f"\n⏸ Pickup will open at {location_statuses['pickup']['starts']}"
            
            # Offer to select a category 
            for category_id in menu:
                category = ti.categories[category_id]
                # Add categories to keyboard
                dialogue.keyboard.append([InlineKeyboardButton(category['attributes']['name'], callback_data="category-"+str(category_id))])
    
            if len(dialogue.keyboard) > 0:
                dialogue.reply_text += "\n\n" + "Please select a category"
            else:
                dialogue.reply_text += "\n\n" + "There are no categories for this location"
            
            # Admin buttons
            if dialogue.is_admin:
                # Reload button
                dialogue.nav_buttons.append([InlineKeyboardButton("🔄 Reload", callback_data="admin-reload")])
                
        # Handle category section
        elif query.data.startswith("category-"):
            category_id = int(query.data.split("-")[1])
            menu = ti.menus[location_id]
    
            # Save current category ID to dialogue
            dialogue.update_nav('current_category', category_id)
    
            # Add category name to reply text
            dialogue.reply_text += f"<b>{ti.categories[category_id]['attributes']['name']}</b>"
    
            # Offer to select an item
            for item_id in ti.menus[location_id][category_id]:
                item = ti.menu_items[item_id]
                # Format price with spaces after every 3 digits from the end
                price = format_amount(item['data']['attributes']['menu_price'], item['data']['attributes']['currency'])
                # Add items to keyboard
                dialogue.keyboard.append([InlineKeyboardButton(f"{item['data']['attributes']['menu_name']} {price}", callback_data="item-"+str(item_id))])
            
            if len(dialogue.keyboard) > 0:
                dialogue.reply_text += "\n\n" + "Please select an item"
            else:
                dialogue.reply_text += "\n\n" + "There are no items in this category"
    
            # Create back button to location
            dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="location-"+str(dialogue.nav['current_location']))])
            
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
    
            category_id = dialogue.nav['current_category']
            menu = ti.menus[location_id]

            # Show item main screen
            if action == None:  
                # Add item name to reply text
                dialogue.reply_text = f"<b>{item['attributes']['menu_name']}</b>"
        
                # Count this items in cart and add to reply text
                current_item_quantity = dialogue.cart_count()
                if current_item_quantity > 0:
                    # Count items with the same ID
                    current_item_quantity = sum(item['quantity'] for item in dialogue.cart if item['id'] == item_id)

                # Add item quantity to reply text
                if current_item_quantity > 0:
                    dialogue.reply_text += f" (in a cart: {current_item_quantity})"
                    
                # Add item description to reply text
                dialogue.reply_text += f"\n\n{item['attributes']['menu_description']}"

                # Add item price to reply text
                dialogue.reply_text += "\n\n" + f"Price: {format_amount(item['attributes']['menu_price'], item['attributes']['currency'])} {item['attributes']['currency']}"
                
                # Check is there image for this item
                if 'included' in ti.menu_items[item_id]:
                    for attachment in ti.menu_items[item_id]['included']:
                        if attachment['type'] == 'media':
                            dialogue.image = attachment['attributes']['path']

                # Create add to cart button
                dialogue.keyboard.append([InlineKeyboardButton("🛒 Add to cart", callback_data=f"item-{str(item_id)}-addtocart")])
                # Handle item navigation
                keyboard_row = []
                # Create back button to category
                keyboard_row.append(InlineKeyboardButton("⬅️ Back", callback_data="category-"+str(dialogue.nav['current_category'])))
        
                # If there are more than one item in this menu category build navigation buttons
                if len(menu[category_id]) > 1:
                    # Find current item index in menu[category_id]
                    current_item_index = menu[category_id].index(item_id)

                    # Add to reply text N of M
                    dialogue.reply_text += f"\n\n{current_item_index+1} of {len(menu[category_id])}"

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
                    dialogue.keyboard.append(keyboard_row)

            # Handling Add to Cart
            elif action == "addtocart":
                # Ask the user for a quantity
                if params == None:
                    # Add text to reply
                    dialogue.reply_text += "\n\nHow many?"
            
                    # Add quantity buttons.
                    keyboard_row = []
                    for i in range(1, 6):
                        keyboard_row.append(InlineKeyboardButton(str(i), callback_data=f"item-{str(item_id)}-addtocart-{str(i)}"))
                        if i % 3 == 0:
                            dialogue.keyboard.append(keyboard_row)
                            keyboard_row = []
                    # Add last row if it is not full
                    if len(keyboard_row) > 0:
                        dialogue.keyboard.append(keyboard_row)

                    # Create back button to item
                    dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="item-"+str(item_id))])

                # Add an item to cart and ask for options if there are any
                # Check if quantity is valid
                elif int(params) > 0 and int(params) <= config['max-quantity']:
                    # Get quantity from params
                    quantity = int(params)    
        
                    # Check quantity is in reasonable range
                    if quantity < 1 or quantity > config['max-quantity']:
                        quantity = 1
                        logging.warning(f"Quantity {quantity} is out of range (1-{config['max-quantity']})")
                        
                    # Add item to the cart and get its uid
                    uid = dialogue.cart_append(item_id, quantity)
                    dialogue.cart_button = True

                    # Add text to reply
                    dialogue.reply_text += f"{quantity} x {item['attributes']['menu_name']} added to your cart ✅"

                    available_item_options = ti.get_item_options(item_id)
                    # Ask user for an option if there are any                
                    if len(available_item_options) > 0:
                        dialogue.nav['current_menu_item_options'] = available_item_options[0]
                        option = available_item_options[0] # Get first option. This is a temporary solution.
        
                        # Check if there are unselected options
                        if len(available_item_options) > dialogue.cart_options_count(uid):
                            # Ask user for an option
                            dialogue.reply_text = f"Please select an option."

                            # Add option name to
                            dialogue.reply_text += f"\n\n<b>{option['attributes']['option_name']}</b>"
            
                            # Add buttons for each option value
                            default_option_value_id = None
                            for option_value in option['attributes']['menu_option_values']:
                                # Check if this option is default
                                if option_value['is_default']:
                                    default_option_value_id = option_value['menu_option_value_id']

                                # Add option button
                                dialogue.keyboard.append([InlineKeyboardButton(f"{option_value['name']} (+{format_amount(option_value['price'], item['attributes']['currency'])})", callback_data=f"cart-{str(uid)}-setoption-{str(option_value['menu_option_value_id'])}")])
                            
                            # Add Skip button if option is not required and default option value is set
                            if not option['attributes']['required']:
                                dialogue.keyboard.append([InlineKeyboardButton(f"Skip", callback_data=f"cart-{str(uid)}-setoption-{str(default_option_value_id)}")])

                            # Disable home and cart buttons
                            dialogue.home_button = False
                            dialogue.cart_button = False

                        # There are no unselected options
                        else:
                            pass
    
                    # Create back to the item button
                    dialogue.keyboard.append([InlineKeyboardButton(f"⬅️ {item['attributes']['menu_name']}", callback_data=f"item-{str(item_id)}")])
                    
                    # Create cancel button leadeing to remove item from cart
                    dialogue.keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cart-"+str(uid)+"-remove")])
                else:
                    # Set reply text
                    dialogue.reply_text = "Invalid quantity"
                    # Create back button to item
                    dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="item-"+str(item_id))])

        # Handle cart and cart actions
        elif query.data.startswith("cart"): # Format: "cart-{uid}-{action}-{params}"
            # Get uid from query if exists
            uid = query.data.split("-")[1] if len(query.data.split("-")) > 1 else None
            # Get action from query
            action = query.data.split("-")[2] if len(query.data.split("-")) > 2 else None
            # Get params from query
            params = query.data.split("-")[3] if len(query.data.split("-")) > 3 else None
    
            dialogue.cart_button = False
    
            # Handle cart
            if action == None:
                # Check if cart is empty
                if dialogue.cart_count() == 0:
                    dialogue.reply_text += "\n\nCart is empty"
                else:
                    # Set message text
                    dialogue.reply_text = "🛒 <b>Your order is:</b>"
                    # Show items in cart and sum subtotal price
                    subtotal = 0
                    k = 0
                    for cart_item in dialogue.cart:
                        k += 1
                        item = ti.menu_items[cart_item['id']]['data']
                        subtotal += item['attributes']['menu_price'] * cart_item['quantity']
                        # Add items to the message text
                        if cart_item['quantity'] == 1:
                            dialogue.reply_text += f"\n\n<b>{k}. {item['attributes']['menu_name']}</b>\n"
                            dialogue.reply_text += f"{format_amount(item['attributes']['menu_price'], item['attributes']['currency'])}"
                        else:
                            dialogue.reply_text += f"\n\n<b>{k}. {item['attributes']['menu_name']}</b>\n"
                            dialogue.reply_text += f"{format_amount(item['attributes']['menu_price'], item['attributes']['currency'])} x {cart_item['quantity']}"
                            
                            items_price = item['attributes']['menu_price'] * cart_item['quantity']
                            dialogue.reply_text += f" = {format_amount(items_price, item['attributes']['currency'])}"
                        # Add options to the message text
                        if len(cart_item['options']) > 0:
                            for option in cart_item['options']:
                                if option is not None:
                                    if option['price'] == 0:
                                        dialogue.reply_text += f"\n{option['name']}"
                                    else:
                                        dialogue.reply_text += f"\n{option['name']} (+{format_amount(option['price'], option['currency'])})"
                                        subtotal += option['price'] * cart_item['quantity']

                    total = subtotal
                    discount = 0

                    # Check delivery type
                    if dialogue.user['order']['order_type'] == 'delivery':
                        # Delivery fee
                        # TODO: Add delivery fee calculation
                        # delivery_fee = ti.get_delivery_fee(subtotal, location_id)
                        # Temporary solution config delivery fee tmp-delivery-fee and tmp-delivery-free-limit - amount of order to get free delivery
                        delivery_fee = config['tmp-delivery-fee']
                        delivery_free_limit = config['tmp-delivery-free-limit']

                        if subtotal >= delivery_free_limit:
                            delivery_fee = 0
                        
                        if delivery_fee == 0:
                            if delivery_free_limit > 0:
                                dialogue.reply_text += f"\n\nDelivery fee: <s>{format_amount(config['tmp-delivery-fee'], item['attributes']['currency'])}</s> {format_amount(0, item['attributes']['currency'])}"
                            else:
                                dialogue.reply_text += f"\n\nDelivery fee: {format_amount(0, item['attributes']['currency'])}"
                        else:
                            dialogue.reply_text += f"\n\nDelivery fee: {format_amount(delivery_fee, item['attributes']['currency'])}"
                            dialogue.reply_text += " (Free delivery for orders over " + format_amount(config['tmp-delivery-free-limit'], item['attributes']['currency']) + ")"
                            total += delivery_fee
                    # Pickup
                    elif dialogue.user['order']['order_type'] == 'collection':
                        # Add pickup address to the message text
                        dialogue.reply_text += f"\n\nPick up from: {ti.get_location_name(location_id)}"
                        dialogue.reply_text += f"\nAddress: {ti.get_location_address(location_id)}"

                    # Apply coupon            
                    if dialogue.user['coupon'] != None:
                        coupon = dialogue.user['coupon']
                        # Check coupon type
                        if coupon['attributes']['type'] == "F": # Fixed amount
                            discount = float(coupon['attributes']['discount'])
                            dialogue.reply_text += f"\n\n🎁 <code>{coupon['attributes']['code']}</code> (-{format_amount(discount, config['ti-currency-code'])})"
                            total -= discount
                        elif coupon['attributes']['type'] == "P": # Percentage
                            discount = subtotal * coupon['attributes']['discount'] / 100
                            dialogue.reply_text += f"\n\n🎁 <code>{coupon['attributes']['code']}</code> (-{coupon['attributes']['discount']}%)"
                            total -= discount
        
                    # If discount is greater than subtotal, set discount to subtotal
                    if discount > subtotal:
                        discount = subtotal
        
                    # If total is less than 0, set total to 0
                    if total < 0:
                        total = 0
        
                    # If discount > 0 add discount to message text
                    if discount > 0:
                        dialogue.reply_text += f"\n\nSubtotal: {format_amount(subtotal, config['ti-currency-code'])}"
                        dialogue.reply_text += f"\nDiscount: -{format_amount(discount, config['ti-currency-code'])}"
                        dialogue.reply_text += f"\n<b>Total: {format_amount(total, config['ti-currency-code'])}</b>"
                    else:
                        dialogue.reply_text += f"\n\n<b>Total: {format_amount(total, config['ti-currency-code'])}</b>"
                    
                    # Add select order_type button and checkout button
                    dialogue.keyboard.append([
                        InlineKeyboardButton(f"{config['ti-order-types'][dialogue.user['order']['order_type']]['emoji']} {dialogue.user['order']['order_type'].capitalize()}", callback_data="cart-0-order_type"),
                        InlineKeyboardButton("✅ Checkout", callback_data="checkout"),
                    ])
                    # Create clear cart and edit cart buttons
                    dialogue.keyboard.append([
                        InlineKeyboardButton("🗑 Clear cart", callback_data="cart-0-clear"),
                        InlineKeyboardButton("✏️ Edit cart", callback_data="cart-0-edit")]
                    )
                    # Create button for enter coupon code
                    dialogue.keyboard.append([InlineKeyboardButton("🎁 Enter coupon code", callback_data="cart-0-coupon")])
        
                    # Print coupon code
                    #if dialogue.coupon != None:
                    #    dialogue.reply_text += f"\n\n<b>Coupon code</b> - {dialogue.coupon['code']}"
            # Handle clear cart
            elif action == "clear":
                # Clear cart
                dialogue.cart_clear()
                # Set message text
                dialogue.reply_text = "Cart cleared"
            # Handle edit cart
            elif action == "edit":
                print("edit")
                # Add text to reply
                dialogue.reply_text += "\n\nPlease select an item to edit"
                # Add items to reply text
                for item_in_catrt in dialogue.cart:
                    item = ti.menu_items[item_in_catrt['id']]['data']
                    # Add edit buttons
                    dialogue.keyboard.append([InlineKeyboardButton(f"{item['attributes']['menu_name']} x {item_in_catrt['quantity']} ✏️", callback_data=f"cart-{str(item_in_catrt['uid'])}-setquantity")])
                    dialogue.keyboard.append([InlineKeyboardButton(f"{item['attributes']['menu_name']} x {item_in_catrt['quantity']} ❌ ", callback_data=f"cart-{str(item_in_catrt['uid'])}-remove")])
                # Create back button to cart
                dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="cart")])
            # Handle remove item from cart
            elif action == "remove":
                    # Remove item from cart
                    dialogue.cart_remove(uid)
                    # Set reply text
                    dialogue.reply_text += "\n\nItem removed from cart"
                    # Create back button to cart
                    dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="cart")])
            # Handle set quantity for item in cart
            elif action == "setquantity":
                    # Ask user for quantity
                    if params == None:
                        # Add text to reply
                        dialogue.reply_text += "\n\nHow many?"
                
                        # Add quantity buttons
                        keyboard_row = []
                        for i in range(1, 6):
                            keyboard_row.append(InlineKeyboardButton(str(i), callback_data=f"cart-{str(uid)}-setquantity-{str(i)}"))
                        dialogue.keyboard.append(keyboard_row)
                
                        # Create back button to cart
                        dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="cart")])
                    else:
                        # Set quantity for item in cart
                        dialogue.cart_set_quantity(uid, int(params))
                        # Set reply text
                        dialogue.reply_text += f"\n\nQuantity set to {params}"
                        # Create back button to cart
                        dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="cart")])
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
                dialogue.reply_text += f"\n\nOption set to {selected_option['name']}"
    
                # Create button the item in the menu item-{item_id}
                dialogue.keyboard.append([InlineKeyboardButton(f"⬅️ Back to {item['attributes']['menu_name']}", callback_data=f"item-{item_id}")])
            # Handle order_type type selection. Set dialogue.user['order']['order_type'] = "delivery" | "collection"
            elif action == "order_type":
                if params == None:
                    dialogue.reply_text += "\n\nWill you pick up the order yourself or choose delivery?"
                    dialogue.reply_text += f"\n\nRestaurant: {ti.get_location_name(location_id)}"
                    dialogue.reply_text += f"\nAddress: {ti.get_location_address(location_id)}"
                    
                    location_statuses = ti.get_location_statuses(location_id)
                    
                    dialogue.reply_text += "\n"
                    if location_statuses['delivery']['status']:
                        dialogue.reply_text += f"\n✅ Delivery until {location_statuses['delivery']['ends']}"
                    else:
                        dialogue.reply_text += f"\n⏸ Delivery will open at {location_statuses['delivery']['starts']}"
                    
                    if location_statuses['pickup']['status']:
                        dialogue.reply_text += f"\n✅ Pickup until {location_statuses['pickup']['ends']}"
                    else:
                        dialogue.reply_text += f"\n⏸ Pickup will open at {location_statuses['pickup']['starts']}"
                    
                    # Add order type buttons
                    for delivery_type in config['ti-order-types']:
                        dialogue.keyboard.append([InlineKeyboardButton(f"{config['ti-order-types'][delivery_type]['emoji']} {delivery_type.capitalize()}", callback_data=f"cart-0-order_type-{delivery_type}")])
                        
                    # Create back button to cart
                    dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="cart")])
                elif params in config['ti-order-types']:
                    # Set order type
                    dialogue.set_order_type(params)
                    # Set reply text
                    dialogue.reply_text += f"\n\nOrder type set to {params}"
                    # Create button to cart
                    dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back to cart", callback_data="cart")])
                else:
                    logger.error(f"Invalid order type: {params}")
                    # Set reply text
                    dialogue.reply_text += f"\n\nInvalid order type"
                    # Create button to cart
                    dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back to cart", callback_data="cart")])
            # Coupon code handling
            elif action == "coupon":
                # Wait for coupon code
                dialogue.update_nav('text_requested_for', 'coupon_code')
                dialogue.update_nav('after_request_screen', 'cart')
    
                # Add text to reply
                dialogue.reply_text += "\n\nPlease send me a coupon code"
                
                # Disable home and cart buttons
                dialogue.home_button = False
                dialogue.cart_button = False
        
        # Handle checkout
        elif query.data.startswith("checkout"):
                dialogue.reply_text += "<b>Checkout</b>"
                
                # Check if cart is empty
                if dialogue.cart_count() == 0:
                    dialogue.reply_text += "\n\nYour cart is empty. Please add some items to cart"
                    # Create button to home screen
                    dialogue.keyboard.append([InlineKeyboardButton("🏠 Home", callback_data=f"location-{dialogue.nav['current_location']}")])
                # Check if user did not enter phone number
                elif dialogue.user['phone'] == None:
                    # Request user to enter phone number
                    dialogue.reply_text = "Please enter your phone number to continue."
                    dialogue.reply_text += "\n\nYou can enter your phone number or send it to me by pressing the button below."
                    
                    dialogue.update_nav('text_requested_for', 'phone')
                    dialogue.update_nav('after_request_screen', 'cart')
                    dialogue.reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("Send phone number", request_contact=True)],
                        [KeyboardButton("❌ Cancel")] # ❌ is a sign to go after_request_screen
                    ])
                    await query.message.dialogue.reply_text(dialogue.reply_text, reply_markup=dialogue.reply_markup, parse_mode=ParseMode.HTML)
                    return
                else:
                    order = dialogue.user['order']
                    '''
                    Requare user to enter:
                    - Payment method (default: cod)
                    - Delivery method (default: delivery)
                    - Delivery address or user location
                    
                    Optional:
                    - Ask for delivery time 
                    - Ask for phone number
                    - Ask for comment
                    '''
                    
                    # Liast all checkout parameters and their values
                    dialogue.reply_text += "\n\n"
                    # Delivery method
                    if order['order_type'] == 'delivery':
                        # Delivery method
                        dialogue.reply_text += f"🚚 Your order will be delivered to: <b>{order['delivery_address']}</b>\n"
                    elif order['order_type'] == 'collection':
                        # Delivery method
                        dialogue.reply_text += f"You can pick up your order from: <b>{ti.active_locations[dialogue.nav['current_location']]['name']}</b>\n"
                        # Location address
                        dialogue.reply_text += f"📍 Address: <b>{ti.active_locations[dialogue.nav['current_location']]['location_address_1']}</b>\n"
                        if ti.active_locations[dialogue.nav['current_location']]['location_address_2']:
                            dialogue.reply_text += f"<b>{ti.active_locations[dialogue.nav['current_location']]['location_address_2']}</b>\n"
                    
                    # Payment method
                    dialogue.reply_text += f"💵 Payment method: <b>{dialogue.checkout['payment_method']}</b>\n"
                    
                    # Add button to change delivery method
                    dialogue.keyboard.append([InlineKeyboardButton("Change delivery method", callback_data=f"checkout-deliverymethod")])
                    
                    # Add button to change payment method
                    dialogue.keyboard.append([InlineKeyboardButton("Change payment method", callback_data=f"checkout-paymentmethod")])
        
        # Handle location reset request and confirmation
        elif query.data.startswith("resetlocation-"):
            # Get step from button data
            step = str(query.data.split("-")[1])
            
            # Handle request
            if step == "request":
                # If cart is not empty, add warning to message text
                if dialogue.cart_count() > 0:
                    dialogue.reply_text = "Your cart will be cleared"
                    # Create confirm button
                    dialogue.keyboard.append([InlineKeyboardButton("Ok", callback_data="resetlocation-confirm")])
                    # Create cancel button
                    dialogue.keyboard.append([InlineKeyboardButton("Cancel", callback_data="location-"+str(dialogue.nav['current_location']))])
                else:
                    step = "confirm"
                    
            if step == "confirm":
                # Clear cart
                dialogue.cart_clear()
                # Reset navigation
                dialogue.nav_reset()

                # Disable home button
                dialogue.home_button = False 

                # Offer to select location
                dialogue.reply_text += "\n\n" + "Please select a Restaurant:"
                for location in ti.active_locations:
                    dialogue.keyboard.append([InlineKeyboardButton(location['attributes']['location_name'], callback_data="location-"+str(location['id']))])
    
        # Handle Admin commands
        elif query.data.startswith("admin-"):
            action = str(query.data.split("-")[1])
            
            # Reload data from API
            if action == "reload":
                ti.clear_cache()
                ti.load()
                dialogue.reply_text += "\n\nCache is cleared, data is reloaded"
                
            # Create back button
            dialogue.keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="location-"+str(dialogue.nav['current_location']))])    

        # Update the message from which the query originated
        # KEYBOARD MANAGEMENT #
        # Reset location button
        if not query.data.startswith("resetlocation") and len(ti.active_locations) > 1:
            # If it is home section, add reset location button
            if query.data.startswith("location-"):
                dialogue.nav_buttons.append([InlineKeyboardButton("📍", callback_data="resetlocation-request")])
    
        # Home and cart buttons management     
        if query.data.startswith("cart-0-coupon"): dialogue.home_button = False
        elif query.data.startswith("location-"): dialogue.home_button = False

    # TODO: All code below should be moved to Dialogue class
    if dialogue.cart_button and dialogue.cart_count():
        dialogue.nav_buttons.append([InlineKeyboardButton(f"🛒 Cart ({dialogue.cart_count()})", callback_data="cart")])
  
    # If location is set, add home button to navigation buttons
    if dialogue.home_button:
        dialogue.nav_buttons.append([InlineKeyboardButton("🏠 Home", callback_data="location-"+str(dialogue.nav['current_location']))])
    
    # Add navigation buttons if there are any
    dialogue.keyboard += dialogue.nav_buttons
    if len(dialogue.keyboard) > 0:
        dialogue.reply_markup = InlineKeyboardMarkup(dialogue.keyboard)

    # If there is no text, set default text
    if dialogue.reply_text == '':
        dialogue.reply_text = config['unknown-err']
        logger.warning("Sending empty message")
    # Add image to message text by putting a dot at the end wrapped in html link tag
    if dialogue.image is not None:
        dialogue.reply_text = dialogue.reply_text + f" <a href=\"{dialogue.image}\">.</a>"
    
    # List of allowed HTML tags
    allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'span', 'a', 'code', 'pre']
    
    # Rmove all tags that are not allowed
    dialogue.reply_text = re.sub(r'<(?!\/?(?:' + '|'.join(allowed_tags) + r'))[^>]+>', '', dialogue.reply_text)
    
    # Remove <br> and <p> tags
    dialogue.reply_text = re.sub(r'<br>|<p>', '', dialogue.reply_text)

    # Send the message or edit the existing one
    if dialogue.existed_message:
        await query.answer() # Answer the query to remove the loading animation
        try:
            await query.message.edit_text(dialogue.reply_text, reply_markup=dialogue.reply_markup, parse_mode=ParseMode.HTML)
        except BadRequest:
            await query.message.edit_text(config['unknown-err'], reply_markup=dialogue.reply_markup, parse_mode=ParseMode.HTML)
            logger.error("Error while editing message")
            logger.error(dialogue.reply_text)
    # If there is no message, send a new one
    else:
        try:
            sent =  await update.message.dialogue.reply_text(dialogue.reply_text, reply_markup=dialogue.reply_markup, parse_mode=ParseMode.HTML)
            # Store message ID to dialogue for deleting later
            cat = dialogue.nav['message_ids'] + [sent.message_id] if 'message_ids' in dialogue.nav else [sent.message_id]
            dialogue.update_nav('message_ids', cat)
        except BadRequest:
            await update.message.dialogue.reply_text(config['unknown-err'], reply_markup=dialogue.reply_markup, parse_mode=ParseMode.HTML)
            logger.error("Error while sending message")
            logger.error(dialogue.reply_text)

    # BUG: sometimes nav['message_ids'] is not defined
    if type(dialogue.nav['message_ids']) is not list:
        dialogue.nav['message_ids'] = []

    # Check if we have more then one message in the dialogue
    if 'message_ids' in dialogue.nav and len(dialogue.nav['message_ids']) > 1:
        # Delete all messages except the last one
        for message_id in dialogue.nav['message_ids'][:-1]:
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=message_id)
            except BadRequest as e:
                logger.warning(f"Could not delete message {message_id}: {e}")                
            else:
                logger.info(f"Deleted {len(dialogue.nav['message_ids'])-1} messages")
        # Anyways, keep only the last message ID in dialogue
        dialogue.update_nav('message_ids', dialogue.nav['message_ids'][-1:])
    

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    '''Handle any message that is not a command'''
    query = update.message
    dialogue = dm.get_dialog(update.effective_user)
    dialogue.new_answer()
    
    # If we have a text message
    if query.text is not None:
        text = query.text
        # Handle cancel request, to go back the "one-message mode"
        if text.startswith('❌'):
            dialogue.reply_text += "Cancelled"
            
            # Reset text_requested_for
            dialogue.update_nav('text_requested_for', None)
            
            # Add continue button
            dialogue.keyboard.append([InlineKeyboardButton("Continue", callback_data=dialogue.nav['after_request_screen'])])
            
        # Handle coupone code
        if dialogue.nav['text_requested_for'] == 'coupon_code':
            coupon = ti.get_coupon(text)
            if coupon is not None:
                # Add coupon to cart
                # dialogue.cart_add_coupon(coupon)
                # Add text to reply
                dialogue.reply_text += f"Coupon {text} added!"
    
                # Add coupon to cart
                dialogue.update_coupon(coupon)
    
                # Send sticker
                await query.reply_sticker(config['success-sticker'])
            else:
                dialogue.reply_text += f"Coupon {text} is not valid!"
    
            # Add back button
            dialogue.keyboard = [[InlineKeyboardButton("Back", callback_data=f"{dialogue.nav['after_request_screen']}")]]

               # Reset text_requested_for
            dialogue.update_nav('text_requested_for', None)

    # Add navigation buttons if there are any
    dialogue.keyboard += dialogue.nav_buttons
    if len(dialogue.keyboard) > 0:
        dialogue.reply_markup = InlineKeyboardMarkup(dialogue.keyboard)

    # If there is no text, set it to '...'
    if dialogue.reply_text == '':
        dialogue.reply_text = config['unknown-err']
        logger.warning("Sending empty message")
    # Add image to message text by putting a dot at the end wrapped in html link tag
    if dialogue.image is not None:
        dialogue.reply_text = dialogue.reply_text + f" <a href=\"{dialogue.image}\">.</a>"
    
    await query.dialogue.reply_text(dialogue.reply_text, reply_markup=dialogue.reply_markup, parse_mode=ParseMode.HTML)

    '''
    # Do we have a location message?
    if update.message.text is None:
        if update.message.location is not None:
            # Get location
            location = update.message.location
            # Send latitute and longitude to user
            await update.message.dialogue.reply_text(f"{location.latitude}, {location.longitude}")
            return

        if update.message.contact is not None:
            # Get contact
            contact = update.message.contact
            # Send contact message
            await update.message.dialogue.reply_text(f"Your phone number is +{contact.phone_number}")
            return

    # Request location if '/set' is sent
    if update.message.text == "/set":
        # Send location request
        await update.message.dialogue.reply_text("Please send your location", dialogue.reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Send location", request_location=True)]], one_time_keyboard=True))
        return
    
    # Request telephone number if '/phone' is sent
    if update.message.text == "/phone":
        # Send contact sare request
        await update.message.dialogue.reply_text("Please send your phone number", dialogue.reply_markup=ReplyKeyboardMarkup([[KeyboardButton("Send phone number", request_contact=True)]], one_time_keyboard=True))

    # replay with the same message
    await update.message.dialogue.reply_text(update.message.text)
    '''


def main() -> None:
    """Run the telegram bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(config['tg-token']).build()
 
    # Add handlers for start and help commands
    application.add_handler(CommandHandler("start", process_usser_action))
 
    # Add a handler for callback query
    application.add_handler(CallbackQueryHandler(process_usser_action))

    # Add a handler for text messages
    application.add_handler(MessageHandler(filters.TEXT | filters.LOCATION | filters.CONTACT, msg))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":    
    # Set up the logger
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    logger = logging.getLogger(__name__)

    # Load config
    config = Config()
    
    # Create a DialogsManager instance
    dm = DialoguesManager(config)
    
    # Connect to TarastyIgniter API
    ti = TastyIgniter(config)
    
    main()