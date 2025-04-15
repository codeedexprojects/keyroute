from rest_framework import serializers
from .models import Booking, Traveler
from vendors.models import Package

class TravelerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Traveler
        fields = ['id', 'first_name', 'last_name', 'gender', 'place', 
                 'dob', 'id_proof', 'email', 'phone', 'city']
        extra_kwargs = {
            'id': {'read_only': True},
            'booking': {'read_only': True}
        }

class BookingSerializer(serializers.ModelSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Booking
        fields = ['id', 'package', 'package_details', 'start_date',
                 'total_travelers', 'total_amount', 'advance_amount', 'payment_status',
                 'is_completed', 'created_at', 'travelers']
        read_only_fields = ['id', 'created_at', 'total_travelers']
    
    def get_package_details(self, obj):
        from vendors.serializers import PackageSerializer
        return PackageSerializer(obj.package).data
    
    def create(self, validated_data):
        # The user will be added by the view
        booking = Booking.objects.create(**validated_data)
        return booking
    
    def update(self, instance, validated_data):
        # Update booking fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance