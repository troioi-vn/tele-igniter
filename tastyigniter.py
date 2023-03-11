import logging, requests, json, time, hashlib, os

class TastyIgniter():
    '''API class for Tastyigniter API requests.'''
    def __init__(self, config):
        '''Initialize API class.'''
        self.config = config
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
 
        # Set up the logger
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        self.logger = logging.getLogger(__name__)
 
        # Connect to Tastyigniter API
        self.logger.info("Connecting to Tastyigniter API...")

        # Chek if cache is enabled
        if config['ti-api-cache']:
            self.logger.info("Tastyigniter API cache is enabled")
            # Create cache directory if it doesn't exist and 
            if not os.path.exists("cache"):
                os.mkdir("cache")
                self.logger.info("Cache directory created")
        else:
            self.logger.info("Tastyigniter API cache is disabled")
  
        self.load()
        # print_menus() # DEBUG. Print menus for all active locations

    def load(self):
        self.active_locations = []
        
        # Get active locations for connection check
        response = self.request(f"locations?location_status=true")['data']

        # Check if there are any locations 
        if len(response) == 0:
            self.logger.error("There are no locations on Tastyigniter side")
            self.logger.info("Please create location on Teastyigniter side and check your configuration file")
            # TODO: offer to create location through bot and add it to config
            exit(0)
        # Check if location-ids list from config matches any location_id from Tastyigniter API response
        for location in response:
            if int(location['id']) in self.config['location-ids']:
                self.active_locations.append(location)
                # print active locations coloring them green
                self.logger.info(f"[Active] {location['id']} {location['attributes']['location_name']}")
            else:
                self.logger.info(f"[Inactive] {location['id']} {location['attributes']['location_name']}")
        # Check if there are any active locations
        if len(self.active_locations) == 0:
            self.logger.error("location-ids list from config doesn't match any location_id on Tastyigniter side")
            self.logger.info("Please set correct location ID in your configuration file")
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
   
        self.logger.info("Loading menus for active locations...")
        # Load categories and menu items for each active location
        for location in self.active_locations:
            location_id = int(location['id'])
            # Get location details
            self.locations[location_id] = self.request(f"locations/{location_id}?include=working_hours,media")['data']
   
            # Load menu
            self.menus[location_id] = self.load_menu(location_id)    

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

    def print_menus(self):
        # Print active locations titles and menu items
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

    def request(self, uri: str) -> dict:
        '''Request any API endpoint and return JSON response.'''
        resp = [] # Response

        # Log request
        self.logger.debug(f"API ({self.attempts}): {uri}")
  
        # Filtrate request
        if uri.startswith("/"):
            request = uri[1:]
        else:
            request = uri
        # Check if there is a cached response if caching is enabled
        if self.config['ti-api-cache']:
            # Generate filename
            filename = hashlib.md5(uri.encode()).hexdigest()[:8]
            if os.path.isfile(f"cache/req_{filename}.json"):
                with open(f"cache/req_{filename}.json", "r") as f:
                    return json.load(f)

        # Delay every 30 requests to avoid 429 error
        self.api_request_counter += 1

        # Create Bearer authorization header
        headers =  {"Content-Type":"application/json", "Authorization": f"Bearer {self.config['ti-token']}"}

        # Request API
        try:
            response = requests.get(f"{self.config['ti-url']}/{request}", headers=headers)
        except Exception as e:
            self.logger.error(f"Error {response.status_code} while connecting to Tastyigniter API")
                    
            # Repeat request if there are less than 5 errors
            if self.attempts < self.config['ti-api-max-attempts']:
                self.attempts += 1
                # handle Error 429:
                if response.status_code == 429:
                    self.loggger.info("Waiting 1 second to avoid 429 error")
                    time.sleep(1)
                    
                return self.request(uri)
            # Exit the program if there are more than 5 errors
            else:
                self.logger.error("There are more than 5 errors while connecting to Tastyigniter API")
                self.logger.info("1. Check API URL and API token in your configuration file")
                self.logger.info("2. Check if Tastyigniter API is running")
                self.logger.info("3. Check if Tastyigniter API is accessible from this machine")
                self.logger.info(f"4. Check if {uri} endpoint is enabled in Tastyigniter API for this token")
                self.logger.error(f"Error: {e}")
                exit(1) 
        else:
            if response.status_code == 200:
                # Reset attempts counter
                self.attempts = 0
                # Return JSON response
                resp = response.json()

                # Cache response to file if caching is enabled
                if self.config['ti-api-cache']:
                    # Save response to file
                    # Generate unique filename
                    filename = hashlib.md5(uri.encode()).hexdigest()[:8]
                    with open(f"cache/req_{filename}.json", "w") as file:
                        file.write(json.dumps(resp, indent=4))
                return resp # Return JSON response
            else:
                self.logger.error(f"Error while retrieving {uri}")
                self.logger.error(f"Error {response.status_code}: {response.text}")
                exit(1)

    def clear_cache(self):
        '''Clear cache directory.'''
        for file in os.listdir("cache"):
            # If filename contains "req_" then it is a cached request
            if file.startswith("req_"):
                os.remove(f"cache/{file}")

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
        for coupon in self.coupons:
            if coupon['attributes']['code'] == coupon_code:
                return coupon
        return None
