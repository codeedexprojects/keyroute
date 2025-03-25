from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=False, allow_blank=True)  # Optional email

    class Meta:
        model = User
        fields = ['phone_number', 'email', 'password', 'confirm_password']

    def validate(self, data):
        # Ensure passwords match
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # Check if phone number already exists
        if User.objects.filter(phone_number=data['phone_number']).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already registered."})

        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')  # Remove confirm_password before creating user
        user = User(
            phone_number=validated_data['phone_number'],
            email=validated_data.get('email', '')  # Email is optional
        )
        user.set_password(validated_data['password'])  # Hash password
        user.save()
        return user




class UserLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        phone_number = data.get("phone_number")
        password = data.get("password")

        if not phone_number or not password:
            raise serializers.ValidationError("Phone number and password are required.")

        user = authenticate(phone_number=phone_number, password=password)

        if not user:
            raise serializers.ValidationError("Invalid phone number or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is not active.")

        data["user"] = user
        return data
