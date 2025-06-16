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


def is_package_available(package, start_date, total_travelers, end_date=None):
    """
    Check if a package is available for booking on the given dates
    """
    if not end_date:
        # Calculate end date based on package duration
        night_count = package.day_plans.filter(night=True).count()
        total_days = package.days + night_count
        end_date = start_date + timedelta(days=total_days)
    
    # Check if package status is available
    if package.status != 'available':
        return False, f"Package is currently {package.status}"
    
    # Get all buses associated with this package
    package_buses = package.buses.all()
    
    if not package_buses.exists():
        return False, "No buses assigned to this package"
    
    # Find available buses that can accommodate the travelers
    available_buses = []
    bus_availability_messages = []
    
    for bus in package_buses:
        # Check if bus can accommodate the number of travelers
        if bus.capacity < total_travelers:
            bus_availability_messages.append(f"Bus {bus.bus_name} capacity ({bus.capacity}) insufficient for {total_travelers} travelers")
            continue
        
        # Check if bus is available for the date range
        is_busy, busy_message = is_bus_busy(bus, start_date, end_date)
        
        if not is_busy:
            available_buses.append(bus)
        else:
            bus_availability_messages.append(f"Bus {bus.bus_name}: {busy_message}")
    
    # If we have at least one available bus, package is available
    if available_buses:
        return True, f"Package is available with {len(available_buses)} bus(es)"
    
    # No buses available
    return False, "No buses available for this package during the selected dates. Details: " + "; ".join(bus_availability_messages)