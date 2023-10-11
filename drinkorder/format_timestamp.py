import datetime as dt
from datetime import datetime
import pytz

def format_timestamp(timestamp):
    # Convert the timestamp string to a datetime object
    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f')

    # Convert the datetime object to the local timezone (assuming it's UTC)
    local_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    local_dt = local_tz.localize(dt)

    # Format the datetime object as a string in the desired format
    formatted_str = local_dt.strftime('%A, %H:%M:%S, %d-%m-%Y')

    # Convert to Vietnamese language
    formatted_str = formatted_str.replace('Monday', 'Thứ Hai')
    formatted_str = formatted_str.replace('Tuesday', 'Thứ Ba')
    formatted_str = formatted_str.replace('Wednesday', 'Thứ Tư')
    formatted_str = formatted_str.replace('Thursday', 'Thứ Năm')
    formatted_str = formatted_str.replace('Friday', 'Thứ Sáu')
    formatted_str = formatted_str.replace('Saturday', 'Thứ Bảy')
    formatted_str = formatted_str.replace('Sunday', 'Chủ nhật')

    return formatted_str

def date_from_webkit(webkit_timestamp):
    epoch_start = dt.datetime(1601,1,1)
    delta = dt.timedelta(microseconds=int(webkit_timestamp))
    return epoch_start + delta
