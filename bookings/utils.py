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
        trip_status__in=['ongoing']
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



import logging
import requests
from decimal import Decimal
from math import radians, cos, sin, asin, sqrt
from django.conf import settings
from django.db.models import Avg
from rest_framework import serializers
from django.utils import timezone

class BusPriceCalculatorMixin:
    """
    Mixin class for unified price calculation logic across all bus serializers
    """
    
    def calculate_distance_google_api(self, from_lat, from_lon, to_lat, to_lon):
        """Calculate distance using Google Distance Matrix API"""
        try:
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                'origins': f"{from_lat},{from_lon}",
                'destinations': f"{to_lat},{to_lon}",
                'units': 'metric',
                'mode': 'driving',
                'key': settings.GOOGLE_DISTANCE_MATRIX_API_KEY   
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data['status'] == 'OK':
                element = data['rows'][0]['elements'][0]
                if element['status'] == 'OK':
                    distance_km = element['distance']['value'] / 1000
                    return Decimal(str(round(distance_km, 2)))
                else:
                    raise Exception(f"Google API element error: {element['status']}")
            else:
                raise Exception(f"Google API error: {data['status']}")
                
        except Exception as e:
            logging.error(f"Error calculating distance with Google API: {str(e)}")
            return self.calculate_distance_fallback(from_lat, from_lon, to_lat, to_lon)

    def calculate_distance_fallback(self, from_lat, from_lon, to_lat, to_lon):
        """Fallback distance calculation using Haversine formula"""
        try:
            from_lat, from_lon, to_lat, to_lon = map(radians, [from_lat, from_lon, to_lat, to_lon])
            
            dlat = to_lat - from_lat
            dlon = to_lon - from_lon
            a = sin(dlat/2)**2 + cos(from_lat) * cos(to_lat) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371  # Radius of earth in kilometers
            
            distance_km = c * r
            return Decimal(str(round(distance_km, 2)))
        except Exception as e:
            logging.error(f"Error in fallback distance calculation: {str(e)}")
            return Decimal('10.0')

    def find_optimal_route(self, origin_lat, origin_lon, destination_lat, destination_lon, stops_data):
        """Find the optimal route using nearest neighbor algorithm"""
        if not stops_data:
            return []
        
        # Create all points including origin and destination
        origin = {'lat': origin_lat, 'lon': origin_lon, 'name': 'Origin', 'type': 'origin'}
        destination = {'lat': destination_lat, 'lon': destination_lon, 'name': 'Destination', 'type': 'destination'}
        
        # Convert stops to point format
        stops = []
        for i, stop in enumerate(stops_data):
            stops.append({
                'lat': float(stop['latitude']),
                'lon': float(stop['longitude']),
                'name': stop['location_name'],
                'type': 'stop',
                'original_index': i
            })
        
        # Find optimal route using nearest neighbor algorithm
        optimal_route = []
        current_point = origin
        unvisited_stops = stops.copy()
        
        logging.info(f"=== ROUTE OPTIMIZATION ===")
        logging.info(f"Origin: {origin['name']}")
        logging.info(f"Destination: {destination['name']}")
        logging.info(f"Stops to visit: {[s['name'] for s in stops]}")
        
        # Visit all stops in optimal order
        while unvisited_stops:
            nearest_stop = None
            min_distance = float('inf')
            
            # Find nearest unvisited stop
            for stop in unvisited_stops:
                distance = self.calculate_distance_fallback(
                    current_point['lat'], current_point['lon'],
                    stop['lat'], stop['lon']
                )
                
                if distance < min_distance:
                    min_distance = distance
                    nearest_stop = stop
            
            if nearest_stop:
                optimal_route.append(nearest_stop)
                unvisited_stops.remove(nearest_stop)
                current_point = nearest_stop
                logging.info(f"Next stop: {nearest_stop['name']} (distance: {min_distance} km)")
        
        # Create final optimized stops data in the correct order
        optimized_stops_data = []
        for point in optimal_route:
            if point['type'] == 'stop':
                original_stop = stops_data[point['original_index']]
                optimized_stops_data.append(original_stop)
        
        logging.info(f"Optimized route order: {[stop['location_name'] for stop in optimized_stops_data]}")
        
        return optimized_stops_data

    def calculate_total_distance_with_stops(self, from_lat, from_lon, to_lat, to_lon, stops_data=None):
        """Calculate total distance for round trip with optimal route"""
        
        if not stops_data:
            # Simple round trip without stops
            one_way_distance = self.calculate_distance_google_api(from_lat, from_lon, to_lat, to_lon)
            total_distance = one_way_distance * 2  # Round trip
            
            logging.info(f"=== SIMPLE ROUND TRIP ===")
            logging.info(f"One way distance: {one_way_distance} km")
            logging.info(f"Round trip total: {total_distance} km")
            
            return total_distance
        
        # Find optimal route for stops
        optimized_stops = self.find_optimal_route(from_lat, from_lon, to_lat, to_lon, stops_data)
        
        # Build complete route
        forward_route = []
        forward_route.append({'lat': from_lat, 'lon': from_lon, 'name': 'Origin'})
        
        # Add optimized stops
        for stop in optimized_stops:
            forward_route.append({
                'lat': float(stop['latitude']), 
                'lon': float(stop['longitude']),
                'name': stop['location_name']
            })
        
        # Add destination
        forward_route.append({'lat': to_lat, 'lon': to_lon, 'name': 'Destination'})
        
        # Calculate forward journey distance
        forward_distance = Decimal('0.00')
        logging.info("=== FORWARD JOURNEY (OPTIMIZED ROUTE) ===")
        
        for i in range(len(forward_route) - 1):
            current_point = forward_route[i]
            next_point = forward_route[i + 1]
            
            segment_distance = self.calculate_distance_google_api(
                current_point['lat'], current_point['lon'],
                next_point['lat'], next_point['lon']
            )
            
            forward_distance += segment_distance
            logging.info(f"Segment {i+1}: {current_point['name']} -> {next_point['name']} = {segment_distance} km")
        
        logging.info(f"Forward journey total: {forward_distance} km")
        
        # Calculate return journey (reverse the forward route)
        return_distance = Decimal('0.00')
        logging.info("=== RETURN JOURNEY (REVERSE ROUTE) ===")
        
        return_route = list(reversed(forward_route))
        
        for i in range(len(return_route) - 1):
            current_point = return_route[i]
            next_point = return_route[i + 1]
            
            segment_distance = self.calculate_distance_google_api(
                current_point['lat'], current_point['lon'],
                next_point['lat'], next_point['lon']
            )
            
            return_distance += segment_distance
            logging.info(f"Return Segment {i+1}: {current_point['name']} -> {next_point['name']} = {segment_distance} km")
        
        logging.info(f"Return journey total: {return_distance} km")
        
        # Total round trip distance
        total_distance = forward_distance + return_distance
        
        logging.info(f"=== TOTAL OPTIMIZED ROUND TRIP DISTANCE: {total_distance} km ===")
        
        return total_distance

    def calculate_nights_between_dates(self, start_date, end_date):
        """Calculate number of nights between two dates"""
        if not start_date or not end_date:
            return 0
        
        delta = end_date - start_date
        return max(0, delta.days)

    def calculate_comprehensive_trip_price(self, bus, from_lat, from_lon, to_lat, to_lon, start_date=None, end_date=None, stops_data=None):
        """
        Comprehensive trip price calculation with stops optimization
        This is the unified method used across all serializers
        """
        try:
            # Validate bus pricing data
            if not bus.base_price or bus.base_price <= 0:
                logging.warning(f"Bus {bus.id} has invalid base_price: {bus.base_price}")
                return Decimal('0.00')
            
            if not bus.price_per_km or bus.price_per_km <= 0:
                logging.warning(f"Bus {bus.id} has invalid price_per_km: {bus.price_per_km}")
                return Decimal('0.00')

            # Get total distance with optimized route
            total_distance_km = self.calculate_total_distance_with_stops(
                from_lat, from_lon, to_lat, to_lon, stops_data
            )
            
            # Set default dates if not provided
            if not start_date:
                start_date = timezone.now().date()
            if not end_date:
                end_date = start_date
            
            # Calculate trip duration in days
            total_days = (end_date - start_date).days + 1 if end_date and start_date else 1
            
            # Bus pricing configuration
            base_price_per_day = bus.base_price  # Base price per day
            base_km_per_day = bus.base_price_km or Decimal('100')  # KM included per day (default 100)
            price_per_km = bus.price_per_km  # Rate for extra KM
            night_allowance = bus.night_allowance or Decimal('500')  # Driver allowance per night
            minimum_fare = bus.minimum_fare or Decimal('0.00')
            
            # Calculate base fare for total days
            base_fare = base_price_per_day * total_days
            
            # Calculate total included KM for the trip duration
            total_included_km = base_km_per_day * total_days
            
            # Calculate extra KM charges
            extra_km_charges = Decimal('0.00')
            if total_distance_km > total_included_km:
                extra_km = total_distance_km - total_included_km
                extra_km_charges = extra_km * price_per_km
            
            # Calculate nights and driver allowance
            nights = self.calculate_nights_between_dates(start_date, end_date)
            night_allowance_total = nights * night_allowance
            
            # Calculate total amount
            total_amount = base_fare + extra_km_charges + night_allowance_total
            
            # Ensure minimum fare is met
            if total_amount < minimum_fare:
                total_amount = minimum_fare
            
            logging.info(f"=== COMPREHENSIVE PRICE CALCULATION ===")
            logging.info(f"- Bus: {bus.bus_name}")
            logging.info(f"- Total distance (optimized): {total_distance_km} km")
            logging.info(f"- Total days: {total_days}")
            logging.info(f"- Base fare: {base_fare}")
            logging.info(f"- Included KM: {total_included_km}")
            logging.info(f"- Extra KM: {max(Decimal('0.00'), total_distance_km - total_included_km)}")
            logging.info(f"- Extra KM charges: {extra_km_charges}")
            logging.info(f"- Nights: {nights}")
            logging.info(f"- Night allowance: {night_allowance_total}")
            logging.info(f"- Total amount: {total_amount}")
            
            return total_amount
            
        except Exception as e:
            logging.error(f"Error calculating comprehensive trip price: {str(e)}")
            return Decimal('0.00')