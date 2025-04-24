from rest_framework import serializers
from .models import BusBooking, PackageBooking, Travelers
from vendors.models import Package, Bus

class TravelerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Travelers
        fields = ['id', 'first_name', 'last_name', 'gender', 'place', 
                 'dob', 'id_proof', 'email', 'mobile', 'city']
        extra_kwargs = {
            'id': {'read_only': True},
            'bus_booking': {'read_only': True},
            'package_booking': {'read_only': True}
        }

class BaseBookingSerializer(serializers.ModelSerializer):
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        abstract = True
        fields = ['id','booking_status', 'user', 'start_date', 'total_amount', 'advance_amount', 
                 'payment_status', 'created_at', 'balance_amount','cancelation_reason','from_location', 'to_location', 'total_travelers']
        read_only_fields = ['id', 'created_at', 'balance_amount']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False}
        }

class BusBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    bus_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = BusBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'bus', 'bus_details', 'one_way','travelers'
        ]
        extra_kwargs = {
            'user': {'write_only': True, 'required': False}
        }
    
    def get_bus_details(self, obj):
        from vendors.serializers import BusSerializer
        return BusSerializer(obj.bus).data
    
    def create(self, validated_data):
        booking = BusBooking.objects.create(**validated_data)
        return booking

class              PackageBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = PackageBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'package', 'package_details', 'travelers'
        ]
        read_only_fields = BaseBookingSerializer.Meta.read_only_fields + ['total_travelers']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False}
        }
    
    def get_package_details(self, obj):
        from vendors.serializers import PackageSerializer
        return PackageSerializer(obj.package).data
    
    def create(self, validated_data):
        booking = PackageBooking.objects.create(**validated_data)
        return booking

class TravelerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a traveler associated with a booking"""
    booking_type = serializers.ChoiceField(choices=['bus', 'package'], write_only=True)
    booking_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Travelers
        fields = ['id', 'first_name', 'last_name', 'gender', 'place', 
                 'dob', 'id_proof', 'email', 'mobile', 'city',
                 'booking_type', 'booking_id']
        extra_kwargs = {
            'id': {'read_only': True},
        }
    
    def validate(self, data):
        booking_type = data.pop('booking_type')
        booking_id = data.pop('booking_id')
        
        if booking_type == 'bus':
            try:
                booking = BusBooking.objects.get(id=booking_id)
                data['bus_booking'] = booking
            except BusBooking.DoesNotExist:
                raise serializers.ValidationError(f"Bus booking with id {booking_id} does not exist")
        else:  # booking_type == 'package'
            try:
                booking = PackageBooking.objects.get(id=booking_id)
                data['package_booking'] = booking
            except PackageBooking.DoesNotExist:
                raise serializers.ValidationError(f"Package booking with id {booking_id} does not exist")
        
        return data
    
    def create(self, validated_data):
        traveler = Travelers.objects.create(**validated_data)
        
        # Update the total_travelers count for package bookings
        if hasattr(traveler, 'package_booking') and traveler.package_booking:
            traveler.package_booking.total_travelers = \
                traveler.package_booking.travelers.count()
            traveler.package_booking.save()
            
        return traveler