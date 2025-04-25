from datetime import time
from vendors.models import VendorBusyDate

def is_vendor_busy(vendor, booking_date, from_time=None, to_time=None):
    busy_dates = VendorBusyDate.objects.filter(vendor=vendor, date=booking_date)
    
    for busy in busy_dates:
        if busy.from_time and busy.to_time and from_time and to_time:
            if not (to_time <= busy.from_time or from_time >= busy.to_time):
                return True
        else:
            return True
    return False