import logging, requests, json, time, hashlib, os
import requests, datetime
from bs4 import BeautifulSoup

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
        response = self.request(f"locations?location_status=true&inclede=options")['data']

        # Check if there are any locations 
        if len(response) == 0:
            self.logger.error("There are no locations on Tastyigniter side")
            self.logger.info("Please create location on Teastyigniter side and check your configuration file")
            # TODO: offer to create location through bot and add it to config
            exit(0)
        # Check if location-ids list from config matches any location_id from Tastyigniter API response
        for location in response:
            if int(location['id']) in self.config['location-ids']:
                # WARNING: This is a temporary solution.
                # get location details via API and add it to locations dictionary
                # details = self.request(f"locations/{location['id']}?offer_delivery=True")
                # print(location['options'])
                # Problem is: details['options'] is not in API response
                # So we can't get location details via API
                # TODO: create an issue on Tastyigniter GitHub 
                # https://github.com/tastyigniter/ti-ext-api/blob/master/docs/locations.md

                parsed_location = self.parse_location_info(location)
                location['options'] = parsed_location['options']
                location['schedule'] = parsed_location['schedule']
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
   
        # Get customers list
        self.customers = self.request(f"customers?include=addresses&pageLimit=1000")['data']
   
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

    def get_item_options(self, item_id: int) -> list:
        '''Get item options from user cart.'''
        # WARNING: For now only one option and only radio buttons are supported
        available_item_options = []
        for menu_option in self.menu_items[item_id]['included']:
            if menu_option['type'] == 'menu_options':
                if menu_option['attributes']['display_type'] == 'radio': # Only radio buttons are supported
                    available_item_options.append(menu_option)
                    break
        return available_item_options

    def get_location_info(self, location_id: int) -> dict:
        parsed_location = self.parse_location_info(self.active_locations[location_id])
        self.active_locations[location_id]['options'] = parsed_location['options']
        self.active_locations[location_id]['schedule'] = parsed_location['schedule']
        return self.active_locations[location_id]

    def get_location_address(self, location_id: int) -> str:
        # Return location address: location_address_1 + location_address_2 + location_city
        return f"{self.active_locations[location_id]['attributes']['location_address_1']} {self.active_locations[location_id]['attributes']['location_address_2']} {self.active_locations[location_id]['attributes']['location_city']}"

    def get_location_name(self, location_id: int) -> str:
        return self.active_locations[location_id]['attributes']['location_name']

    def get_location_working_hours(self, location_id: str) -> str:
        # Return location working hours: turn location['schedule'] into a string
        return f"{self.active_locations[location_id]['schedule']}"

    def is_location_open(self, location_id: int) -> dict:
        # Check location schedule and return True of False for opening, delivery and pickup 
        # Example of schedule: {'opening': {'mon': {'start': '12:00 pm', 'end': '08:00 pm'}, 'tue': {'start': '00:00 pm', 'end': '00:00 pm'}, 'wed': {'start': '00:00 pm', 'end': '00:00 pm'}, 'thu': {'start': '12:00 pm', 'end': '08:00 pm'}, 'fri': {'start': '12:00 pm', 'end': '08:00 pm'}, 'sat': {'start': '12:00 pm', 'end': '08:00 pm'}, 'sun': {'start': '12:00 pm', 'end': '08:00 pm'}}, 'delivery': {'mon': {'start': '12:00 pm', 'end': '08:00 pm'}, 'tue': {'start': '00:00 pm', 'end': '00:00 pm'}, 'wed': {'start': '00:00 pm', 'end': '00:00 pm'}, 'thu': {'start': '12:00 pm', 'end': '08:00 pm'}, 'fri': {'start': '12:00 pm', 'end': '08:00 pm'}, 'sat': {'start': '12:00 pm', 'end': '08:00 pm'}, 'sun': {'start': '12:00 pm', 'end': '08:00 pm'}}, 'pickup': {'mon': {'start': '12:00 pm', 'end': '08:00 pm'}, 'tue': {'start': '00:00 pm', 'end': '00:00 pm'}, 'wed': {'start': '00:00 pm', 'end': '00:00 pm'}, 'thu': {'start': '12:00 pm', 'end': '08:00 pm'}, 'fri': {'start': '12:00 pm', 'end': '08:00 pm'}, 'sat': {'start': '12:00 pm', 'end': '08:00 pm'}, 'sun': {'start': '12:00 pm', 'end': '08:00 pm'}}}
        is_open = {'opening': False, 'delivery': False, 'pickup': False}
        now = datetime.datetime.now()

        for key in is_open:
            schedule = self.active_locations[location_id]['schedule'][key]
            for day in schedule:
                if day == now.strftime("%a").lower():
                    if schedule[day]['start'] != '00:00 pm' and schedule[day]['end'] != '00:00 pm':
                        start = datetime.datetime.strptime(schedule[day]['start'], '%I:%M %p')
                        end = datetime.datetime.strptime(schedule[day]['end'], '%I:%M %p')
                        if start <= now <= end:
                            is_open[key] = True
        return is_open  

    def get_coupon(self, coupon_code: str) -> dict:
        '''Check if coupon code is valid.'''
        # Find coupon by code in coupons dictionary
        for coupon in self.coupons:
            if coupon['attributes']['code'] == coupon_code:
                return coupon
        return None

    def parse_location_info(self, location: dict) -> dict:
        '''Temporary function to get location options via parsing 🤦‍♂️ location info page.'''    
        
        # Set timezone offset in hours from UTC
        timezone_offset = 7

        # Structure of the options dictionary from the documentation of the API
        options = {
            "offer_delivery": False,
            "offer_collection": False,
            "delivery_time_interval": 0,
            "collection_time_interval": 0,
            "delivery_lead_time": 0,
            "collection_lead_time": 0,
            "reservation_time_interval": 0,
            "reservation_lead_time": 0,
            "payments": [],
            "gallery": {}
        }

        schedule = {
            'opening': {},
            'delivery': {},
            'pickup': {}
        }

        
        # Generate URL to location info page
        url = self.config['ti-url'].replace('/api', '')
        url = f"{url}/{location['attributes']['permalink_slug']}/info"

        # Fill schedule with empty strings for each day of the week (Mon-Sun)
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            schedule['opening'][day] = None
            schedule['delivery'][day] = None
            schedule['pickup'][day] = None

        # Make a GET request to the URL and store the response
        response = requests.get(url)

        if response.status_code != 200:
            print('Error: response.status_code =', response.status_code)
            exit()

        # Create a BeautifulSoup object from the response content
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find content div
        content = soup.find('div', {'class': 'content'})

        # Find the Delivery Time and Pick-up Time
        for item in content.find_all('div', {'class': 'list-group-item'}):
            row = item.text.strip()
            
            # Ignore empty rows
            if len(row) == 0:
                continue
            
            # Ignore Last Order Time
            if 'Last Order' in row:
                continue
            
            # Ignore the word  'Delivery starts'  'Pick-up starts'
            if 'starts' in row:
                continue
            
            # From string 'Delivery in 200 minutes' get value
            if 'Delivery in' in row:
                options['delivery_time_interval'] = int(row.split(' ')[2])
            # From string 'Pick-up in 200 minutes' get value
            elif 'Pick-up in' in row:
                options['collection_time_interval'] = int(row.split(' ')[2])
            elif 'Payments' in row:
                # Get the Payments list. It is a string like 'Payments </br>Cash, Card, Apple Pay, Google Pay
                # Skip the first word 'Payments\n                '
                row = row.split('\n')[1]
                
                # Removo dot at the end of the string
                row = row[:-1]
                
                payments = row.split(',')
                
                # Trim the whitespace from the beginning and end of each payment method
                for i in range(len(payments)):
                    payments[i] = payments[i].strip()
            else:
                # Collect the schedule
                for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']:
                    if day in row:
                        if schedule['opening'][day.lower()] is None:
                            schedule['opening'][day.lower()] = row
                        elif schedule['delivery'][day.lower()] is None:
                            schedule['delivery'][day.lower()] = row
                        elif schedule['pickup'][day.lower()] is None:
                            schedule['pickup'][day.lower()] = row

        # Process schedule
        for day in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
            for key in ['opening', 'delivery', 'pickup']:
                current = schedule[key][day]
                will_be = { 'start': None, 'end': None }
                if 'CLOSED' in current:
                    will_be = {'start': '00:00 pm', 'end': '00:00 pm'}
                else:
                    # Get the start and end times from string like "Thu\n\n12:00 pm-08:30 pm"
                    will_be = {
                        'start': current.split('\n')[2].split('-')[0],
                        'end': current.split('\n')[2].split('-')[1]
                    }
                schedule[key][day] = will_be

        # current Year-Month-Day
        date = datetime.datetime.now().strftime('%Y-%m-%d')
        # Current time in UTC
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=timezone_offset)

        # Check if ReDelivery is disabled
        if 'Delivery is not available.' in content.text:
            options['offer_delivery'] = False
        else:
            # Current item in schedule
            current = schedule['delivery'][datetime.datetime.now().strftime('%a').lower()]
            # Start time in UTC
            start = datetime.datetime.strptime(date + ' ' + current['start'], "%Y-%m-%d %I:%M %p")
            # End time in UTC
            end = datetime.datetime.strptime(date + ' ' + current['end'], "%Y-%m-%d %I:%M %p")
            
            # Check if current time is between start and end times
            if start <= now <= end:
                options['offer_delivery'] = True
            else:
                options['offer_delivery'] = False

        # Check if Pick-up is disabled
        if 'Pick-up is not available.' in content.text:
            options['offer_collection'] = False
        else:
            # Current item in schedule
            current = schedule['pickup'][datetime.datetime.now().strftime('%a').lower()]

        return {'options': options, 'schedule': schedule}