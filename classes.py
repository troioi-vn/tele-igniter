import os, yaml


class helpers:
    '''Helper functions.'''
    def __init__(self):
        pass

    def format_amount(self, amount: float | int | str, code: str = 'USD', decimals: int = 0) -> str:
        '''Format amount to string with currency symbol.'''
        symbols = {
            'VND': '₫',
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
            'CNY': '¥',
            'KRW': '₩',
            'UAH': '₴',
            'RUB': '₽',
        }
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
        currency_symbol = symbols[code] if code in symbols else code
        
        # Return formatted amount
        return f"{amount} {currency_symbol}"



class Config:
    def __init__(self, filename):
        self.c = {}
        
        # Check configuration file. If there is no .config.yml file run a sepup.py script
        if not os.path.isfile(".config.yml"):
            print("Configuration file .config.yml not found")
            print("Running setup.py script...")
            # Run setup.py script
            import setup
            setup.run()
        
        # Load configuration file
        try:
            with open(filename, 'r') as f:
                self.c = yaml.load(f, Loader=yaml.FullLoader)
                # self.config =  yaml.safe_load(open(".config.yml"))
        except Exception as e:
            # Log this error to logger
            print("Configuration file is invalid")
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
        
    def get(self, key):
        return self.c[key]
    
    def set(self, key, value):
        self.c[key] = value
    
    def save(self, filename):
        with open(filename, 'w') as f:
            yaml.dump(self.c, f)
            
    def __str__(self):
        return str(self.c)
    
    def __repr__(self):
        return str(self.c)
    
    def __getitem__(self, key):
        return self.c[key]