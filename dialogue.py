from classes import Config
import json, os, random, string, logging, re


class Dialogue:
    '''Class for storing user dialogs.'''
    def __init__(self, user_id, is_admin: bool = False):
        '''Initialize Dialogue class.'''
        self.config = Config()
        self.user_id = user_id # Telegram user ID
        self.user = {
            'first_name': None,
            'last_name': None,
            'phone': None,
            'location': None,
            'address': None,
            'coupon': None,
            'ti-customer': {},
            'order': {
                # Required
                'customer_id': None,
                'location_id': None,
                'first_name':  None,
                'last_name':  None,
                'email': self.config['ti-customer']['email'],
                'order_type': 'delivery', # delivery | collection (for pick-up)
                'total_items' : 0,
                'order_total': 0.0,
                'order_totals': [
                    {
                        # 'order_total_id': 792, ??? What is this?
                        'order_id': 0,
                        'code': 'subtotal',
                        'title': 'Sub Total',
                        'value': 0.0,
                        'priority': 0,
                        'is_summable': 0
                    },
                    {
                        # 'order_total_id': 791,
                        'order_id': 0,
                        'code': 'delivery',
                        'title': 'Delivery',
                        'value': 0.0,
                        'priority': 100,
                        'is_summable': 1
                    },
                    {
                        # 'order_total_id': 793,
                        'order_id': 0,
                        'code': 'total',
                        'title': 'Order Total',
                        'value': 0.0,
                        'priority': 127,
                        'is_summable': 0
                    }
                ],
                'order_menus': [],
                
                # Optional
                'telephone': None,
                'comment': None,
                'delivery_comment': None,
                'order_time_is_asap': True,
                'order_date': None,
                'order_time': None,
                'payment': 'cod', # cod | card
                'processed': 0,
                'status_id': 0,
                'status_comment': None,
            }
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
            'message_ids': [], # Message IDs we sent to user. Used for deleting messages.
        }
        self.cart = []

        self.new_answer()

        # Set up the logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        self.logger = logging.getLogger(__name__)

        # Load user dialog from json file
        self.load()

        self.is_admin = is_admin

    def new_answer(self):
        # Variables for reply
        self.reply_text = ''
        self.reply_markup = None
        self.nav_buttons = []
        self.keyboard = []
        self.image = None
    
        # Prepare navigation buttons
        self.home_button = True 
        self.cart_button = True
        
        # Send new message or edit existing one
        self.existed_message = False

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
        with open(f"cache/user_{int(self.user_id)}.json", "w") as file:
            json.dump(dialogue, file, default=[])
        file.close()

    def load(self):
        '''Load user dialog from json file.'''
        # Check if user dialog file exists
        if not os.path.isfile(f"cache/user_{int(self.user_id)}.json"):
            print(f"User dialog file {int(self.user_id)}.json not found")
            return False

        # Load user dialog from json file
        with open(f"cache/user_{int(self.user_id)}.json", "r") as file:
            dialogue = json.load(file)
   
        # Update user dialog
        self.user_id = dialogue['user_id']
        self.nav = dialogue['nav']
        if self.nav['message_ids'] is None:
            self.nav['message_ids'] = []
        self.cart = dialogue['cart']
        self.user = dialogue['user']
        file.close()
        return True

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
    
    def set_order_type(self, order_type: str) -> None:
        '''Set order type.'''
        self.user['order']['order_type'] = order_type
        self.save()
    
    def nav_reset(self) -> None:
        '''Clear user navigation.'''
        for key in self.nav:
            self.nav[key] = None
        self.save()
    
        '''Check if user is admin.'''
        # Load config
        self.config = Config()
        
        if self.user_id in self.config['admins']:
            return True
        return False

    def nav_get_current_location(self) -> dict:
        '''Get current location.'''
        current_location = self.nav['current_location']
        
        if current_location is None:
            # set to first location in config
            config = Config()
            current_location = config['location-ids'][0]
            self.update_nav('current_location', current_location)
            self.logger.warning(f"User {self.user_id} has no current location. Set to {current_location}")

            self.save()
        
        return int(current_location)

    def filter_text(self, text: str) -> str:
        # List of allowed HTML tags
        allowed_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'span', 'a', 'code', 'pre']
        
        # Rmove all tags that are not allowed
        text = re.sub(r'<(?!\/?(?:' + '|'.join(allowed_tags) + r'))[^>]+>', '', text)
        
        # Remove <br> and <p> tags
        text = re.sub(r'<br>|<p>', '', text)
        
        return text
        

class DialoguesManager:
    '''Class for managing user dialogs.'''
    def __init__(self, config):
        '''Initialize DialogsManager class.'''
        self.dialogues = {}
        self.config = config
        self.logger = self.logger()

    def get_dialog(self, tg_user: dict) -> Dialogue:
        '''Get user dialog from the list of dialogs.'''
        # Create a new dialogue for this user in global dialogues dictionary
        if tg_user['id'] not in self.dialogues:
            # check if user is admin
            is_admin = False if tg_user['id'] not in self.config['admins'] else True
            # Create new dialogue 
            self.dialogues[tg_user['id']] = Dialogue(tg_user['id'], is_admin)
            self.logger.info(f"Created new dialogue for user {tg_user['id']}")
        
        # Update user name if it has changed
        if self.dialogues[tg_user['id']].user['first_name'] != tg_user['first_name'] or self.dialogues[tg_user['id']].user['last_name'] != tg_user['last_name']:
            self.dialogues[tg_user['id']].update_name(tg_user['first_name'], tg_user['last_name'])
    
        return self.dialogues[tg_user['id']]

    def remove_dialog(self, user_id: int) -> None:
        '''Remove user dialog from the list of dialogs.'''
        # Delete cached user json file from cache folder named by user ID.json
        filename = f"cache/user_{int(user_id)}.json"
        if os.path.isfile(filename):
            self.logger.info(f"Deleting cached user file {filename}")
            os.remove(filename)
        else:
            self.logger.warning(f"Can't delete cached user file {filename}. File not found.")
        
        if user_id in self.dialogues:
            self.dialogues.pop(user_id)
            self.logger.info(f"Removed dialogue for user {user_id}")
        else:
            self.logger.warning(f"Can't remove dialogue for user {user_id}. Dialogue not found.")

    def logger(self):
        '''Get logger.'''
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        return logging.getLogger(__name__)