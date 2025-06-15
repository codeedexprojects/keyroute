from datetime import datetime, time, timedelta
from django.db.models import Q
from vendors.models import *
from bookings.models import *

def is_bus_busy(bus, start_date, end_date=None, start_time=None, end_time=None):
    """
    Check if a specific bus is busy during the given date range
    """
    if not end_date:
        end_date = start_date
    
    # Check if there are any bookings for this bus during the date range
    existing_bookings = BusBooking.objects.filter(
        bus=bus,
        booking_status__in=['pending', 'accepted'],
        trip_status__in=['not_started', 'ongoing']
    ).filter(
        Q(start_date__lte=end_date) & 
        Q(end_date__gte=start_date)
    )
    
    if existing_bookings.exists():
        return True, "Bus is already booked for this date range"
    
    # Check vendor busy dates for this specific bus
    vendor_busy_dates = VendorBusyDate.objects.filter(
        vendor=bus.vendor,
        buses=bus,
        date__range=[start_date, end_date]
    )
    
    for busy_date in vendor_busy_dates:
        if busy_date.from_time and busy_date.to_time and start_time and end_time:
            # Check time overlap
            if not (end_time <= busy_date.from_time or start_time >= busy_date.to_time):
                return True, f"Bus is marked as busy on {busy_date.date} from {busy_date.from_time} to {busy_date.to_time}"
        else:
            # Full day busy
            return True, f"Bus is marked as busy for the full day on {busy_date.date}"
    
    return False, "Bus is available"