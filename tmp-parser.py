import requests, datetime
from bs4 import BeautifulSoup

# URL of the webpage to scrape
url = 'https://shop.catarchy.space/default/info'

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
    
print(options)
print(schedule)