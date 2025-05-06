from rest_framework import serializers
from .models import BusBooking, PackageBooking, Travelers, BusDriverDetail, PackageDriverDetail
from vendors.models import Package, Bus
from admin_panel.utils import get_admin_commission_from_db, get_advance_amount_from_db
from admin_panel.models import AdminCommission
from django.contrib.auth import get_user_model
from users.models import ReferralTransaction

User = get_user_model()

class TravelerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Travelers
        fields = ['id', 'first_name', 'last_name', 'gender', 'age', 
                 'dob', 'id_proof', 'email', 'mobile', 'city', 'place', 'created_at']
        extra_kwargs = {
            'id': {'read_only': True},
            'bus_booking': {'read_only': True},
            'package_booking': {'read_only': True},
            'created_at': {'read_only': True}
        }

class BaseBookingSerializer(serializers.ModelSerializer):
    balance_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    referral_code = serializers.CharField(max_length=7, required=False, write_only=True)

    
    class Meta:
        abstract = True
        fields = ['id', 'user', 'start_date', 'total_amount', 'advance_amount', 
                 'payment_status', 'booking_status', 'trip_status', 'created_at', 
                 'balance_amount', 'cancelation_reason', 'total_travelers', 
                 'male', 'female', 'children', 'from_location', 'to_location']
        read_only_fields = ['id', 'created_at', 'balance_amount','referral_code']
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }

class BusBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    bus_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = BusBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'bus', 'bus_details', 'one_way', 'travelers',
        ]
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }
    
    def get_bus_details(self, obj):
        from vendors.serializers import BusSerializer
        return BusSerializer(obj.bus).data
    
    def validate_referral_code(self, value):
        """
        Validate that the referral code exists and hasn't been used by this user before.
        """
        if not value:
            return None
            
        try:
            user = self.context['request'].user
            referrer = User.objects.get(referral_code=value)
            
            # Check if user is trying to use their own referral code
            if user.id == referrer.id:
                raise serializers.ValidationError("You cannot use your own referral code.")
            
            # Check if user has already used a referral code
            if ReferralTransaction.objects.filter(referred_user=user).exists():
                raise serializers.ValidationError("You have already used a referral code.")
                
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid referral code.")

    def create(self, validated_data):
        total_amount = validated_data.get('total_amount')
        
        referral_code = validated_data.pop('referral_code', None)
        
        user = self.context['request'].user

        advance_percent, advance_amount = get_advance_amount_from_db(total_amount)
        validated_data['advance_amount'] = advance_amount

        commission_percent, revenue = get_admin_commission_from_db(total_amount)

        booking = super().create(validated_data)

        AdminCommission.objects.create(
            booking_type='bus',
            booking_id=booking.id,
            advance_amount=advance_amount,
            commission_percentage=commission_percent,
            revenue_to_admin=revenue
        )

        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                from decimal import Decimal
                
                referral_amount = 100.00
                
                ReferralTransaction.objects.create(
                    user=referrer,
                    referred_user=user,
                    booking_type='bus',
                    booking_id=booking.id,
                    amount=referral_amount,
                    transaction_type='credit',
                    status='pending'
                )
            except User.DoesNotExist:
                pass

        return booking


class PackageBookingSerializer(BaseBookingSerializer):
    travelers = TravelerSerializer(many=True, required=False, read_only=True)
    package_details = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = PackageBooking
        fields = BaseBookingSerializer.Meta.fields + [
            'package', 'package_details', 'travelers',
        ]
        read_only_fields = BaseBookingSerializer.Meta.read_only_fields
        extra_kwargs = {
            'user': {'write_only': True, 'required': False},
            'advance_amount': {'write_only': False, 'required': False},
        }
    
    def get_package_details(self, obj):
        from vendors.serializers import PackageSerializer
        return PackageSerializer(obj.package).data
    
    def validate_referral_code(self, value):
        """
        Validate that the referral code exists and hasn't been used by this user before.
        """
        if not value:
            return None
            
        try:
            user = self.context['request'].user
            referrer = User.objects.get(referral_code=value)
            
            # Check if user is trying to use their own referral code
            if user.id == referrer.id:
                raise serializers.ValidationError("You cannot use your own referral code.")
            
            # Check if user has already used a referral code
            if ReferralTransaction.objects.filter(referred_user=user).exists():
                raise serializers.ValidationError("You have already used a referral code.")
                
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid referral code.")

    def create(self, validated_data):
        total_amount = validated_data.get('total_amount')
        
        referral_code = validated_data.pop('referral_code', None)
        
        user = self.context['request'].user

        advance_percent, advance_amount = get_advance_amount_from_db(total_amount)
        validated_data['advance_amount'] = advance_amount

        commission_percent, revenue = get_admin_commission_from_db(total_amount)

        booking = super().create(validated_data)

        AdminCommission.objects.create(
            booking_type='package',
            booking_id=booking.id,
            advance_amount=advance_amount,
            commission_percentage=commission_percent,
            revenue_to_admin=revenue
        )

        if referral_code:
            try:
                referrer = User.objects.get(referral_code=referral_code)
                from decimal import Decimal
                
                referral_amount = 100.00 
                
                ReferralTransaction.objects.create(
                    user=referrer,
                    referred_user=user,
                    booking_type='package',
                    booking_id=booking.id,
                    amount=referral_amount,
                    transaction_type='credit',
                    status='pending'
                )
            except User.DoesNotExist:
                pass

        return booking

class TravelerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a traveler associated with a booking"""
    booking_type = serializers.ChoiceField(choices=['bus', 'package'], write_only=True)
    booking_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Travelers
        fields = ['id', 'first_name', 'last_name', 'gender', 'age', 'place', 
                 'dob', 'id_proof', 'email', 'mobile', 'city',
                 'booking_type', 'booking_id', 'created_at']
        extra_kwargs = {
            'id': {'read_only': True},
            'created_at': {'read_only': True}
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