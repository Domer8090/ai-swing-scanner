from datetime import datetime
import pytz

def market_is_open():
    et = pytz.timezone("US/Eastern")
    now = datetime.now(et)

    # Weekend check
    if now.weekday() >= 5:
        return False

    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    return market_open <= now <= market_close
