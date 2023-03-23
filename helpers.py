from bs4 import BeautifulSoup

def format_amount(amount: float | int | str, code: str = 'USD', decimals: int = 0) -> str:
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
