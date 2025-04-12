from rest_framework import serializers
from .models import Booking, Traveler, Payment, CancellationPolicy

class TravelerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Traveler
        fields = ['id', 'first_name', 'last_name', 'age', 'gender', 'place', 
                 'dob', 'id_proof', 'email', 'phone', 'city', 'is_primary']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'amount', 'payment_type', 'payment_date', 'transaction_id']

class CancellationPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = CancellationPolicy
        fields = ['id', 'description', 'is_advance_refundable']

class BookingSerializer(serializers.ModelSerializer):
    travelers = TravelerSerializer(many=True, required=False)
    payments = PaymentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Booking
        fields = ['id', 'package', 'start_date', 'total_adults', 
                 'total_children', 'total_males', 'total_females', 'total_rooms',
                 'total_travelers', 'total_amount', 'advance_amount', 'payment_status',
                 'is_completed', 'created_at', 'updated_at', 'travelers', 'payments']
    
    def create(self, validated_data):
        travelers_data = validated_data.pop('travelers', [])
        booking = Booking.objects.create(**validated_data)
        
        for traveler_data in travelers_data:
            Traveler.objects.create(booking=booking, **traveler_data)
        
        return booking
    
    def update(self, instance, validated_data):
        travelers_data = validated_data.pop('travelers', [])
        # Update booking fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Handle travelers update if needed
        if travelers_data:
            instance.travelers.all().delete()  # Remove existing travelers
            for traveler_data in travelers_data:
                Traveler.objects.create(booking=instance, **traveler_data)
        
        return instance