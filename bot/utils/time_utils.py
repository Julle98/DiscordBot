from datetime import datetime, timezone, timedelta
import pytz

def get_current_time_in_utc_plus_2():
    utc_plus_2 = timezone(timedelta(hours=2))
    current_time = datetime.now(utc_plus_2)
    return current_time.strftime('%d-%m-%Y %H:%M:%S')

def get_current_time_in_helsinki():
    helsinki_tz = pytz.timezone("Europe/Helsinki")
    current_time = datetime.now(helsinki_tz)
    return current_time.strftime("%d.%m.%Y %H:%M")