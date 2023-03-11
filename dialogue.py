import json, os, random, string

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
            print(f"User dialog file {int(self.user_id)}.json not found")
            return False

        # Load user dialog from json file
        with open(f"cache/{int(self.user_id)}.json", "r") as file:
            dialogue = json.load(file)
   
        # Update user dialog
        self.user_id = dialogue['user_id']
        self.nav = dialogue['nav']
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
    
    def nav_reset(self) -> None:
        '''Clear user navigation.'''
        for key in self.nav:
            self.nav[key] = None
        self.save()

