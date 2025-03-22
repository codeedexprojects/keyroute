from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import VendorSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password

from admin_panel.models import *

# Create your views here.

# VENDOR REGISTRATION
class VendorSignupAPIView(APIView):
 
    def post(self, request):
        serializer = VendorSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Vendor registered successfully!", "data": serializer.data},
                status=status.HTTP_201_CREATED
            )
        return Response(
            {"errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
# VEONDOR LOGIN
class LoginAPIView(APIView):
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {"errors": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)
        if user is None:
            return Response(
                {"errors": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            "message": "Login successful!",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)


# VENDOR FORGOT PASSWORD
class ForgotPasswordAPIView(APIView):
    def post(self, request):
        email = request.data.get('email')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')

        if not email or not new_password or not confirm_password:
            return Response({"error": "Email, new password, and confirm password are required."}, status=status.HTTP_400_BAD_REQUEST)

        if new_password != confirm_password:
            return Response({"error": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vendor = Vendor.objects.get(email_address=email)
            user = vendor.user   
            user.set_password(new_password)
            user.save()
            return Response({"message": "Password updated successfully!"}, status=status.HTTP_200_OK)

        except Vendor.DoesNotExist:
            return Response({"error": "Vendor with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)





