import os, yaml
    

class Config:
    def __init__(self, filename: str = ".config.yml"):
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