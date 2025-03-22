from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from admin_panel.models import Vendor, User

class VendorSerializer(serializers.ModelSerializer):

    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Vendor
        fields = [
            'username', 'password', 'full_name', 'email_address', 'phone_no', 
            'travels_name', 'location', 'landmark', 'address', 
            'city', 'state', 'pincode'
        ]

    def validate_username(self, value):
        if not value or len(value) < 5:
            raise serializers.ValidationError('Username must be at least 5 characters long.')
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists.')
        return value

    def validate_email_address(self, value):
        if not value or len(value) < 5:
            raise serializers.ValidationError('Email address must be at least 5 characters long.')
        if Vendor.objects.filter(email_address=value).exists():
            raise serializers.ValidationError('Email address already exists.')
        return value

    def validate_password(self, value):
        if not value or len(value) < 5:
            raise serializers.ValidationError('Password must be at least 5 characters long.')
        return value

    
    
    def create(self, validated_data):
        user = User.objects.create(
            username=validated_data['username'],
            role=User.VENDOR,
            password=make_password(validated_data['password'])
        )
        validated_data.pop('username', None)
        validated_data.pop('password', None)
        validated_data['user'] = user

        vendor = Vendor.objects.create(**validated_data)   
        return vendor

