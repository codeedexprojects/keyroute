from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import generics, permissions
from admin_panel.utils import send_otp, verify_otp
from .serializers import ReviewSerializer, SendOTPSerializer, UserLoginSerializer, UserProfileSerializer, UserSignupSerializer,FavouriteSerializer
from google.auth.transport import requests
from google.oauth2 import id_token
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from vendors.models import Bus
from .models import Favourite

User = get_user_model()

class NormalUserSignupView(APIView):
    def post(self, request):
        name = request.data.get("name")
        mobile = request.data.get("mobile")
        
        if not name or not mobile:
            return Response({"error": "Name and mobile number are required"}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(mobile=mobile).exists():
            return Response({"error": "Mobile number already registered"}, status=status.HTTP_400_BAD_REQUEST)

        # Send OTP to verify mobile number
        response = send_otp(mobile)
        
        if response.get("Status") == "Success":
            # Store user data temporarily in session or return for frontend to store
            return Response({
                "message": "OTP sent to your mobile",
                "session_id": response.get("Details"),
                "temp_data": {
                    "name": name,
                    "mobile": mobile,
                    "email": request.data.get("email", "")
                }
            }, status=status.HTTP_200_OK)
        
        return Response({"error": "Failed to send OTP"}, status=status.HTTP_400_BAD_REQUEST)


class VerifySignupOTPView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")
        otp = request.data.get("otp")
        name = request.data.get("name")
        email = request.data.get("email", "")

        if not mobile or not otp or not name:
            return Response({"error": "Name, mobile number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP
        response = verify_otp(mobile, otp)
        
        if response.get("Status") == "Success":
            # Create user data dictionary for serializer
            user_data = {
                "name": name,
                "mobile": mobile,
                "email": email
            }
            
            serializer = UserSignupSerializer(data=user_data)
            if serializer.is_valid():
                user = serializer.save()
                
                # Generate tokens for the new user
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    "message": "Signup successful",
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "user": {
                        "id": user.id,
                        "mobile": user.mobile,
                        "email": user.email,
                        "name": user.name,
                        "role": user.role,
                    }
                }, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)


class NormalUserLoginView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")  # Can be mobile or email
        
        if not mobile:
            return Response({"error": "Mobile number is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Find user by mobile or email
        user = User.objects.filter(mobile=mobile).first()
            
        if not user:
            return Response({"error": "User does not exist. Please sign up first."}, status=status.HTTP_400_BAD_REQUEST)

        # Send OTP to user's mobile
        response = send_otp(user.mobile)
        
        if response.get("Status") == "Success":
            return Response({
                "message": "OTP sent to your mobile",
                "session_id": response.get("Details"),
                "user_id": user.id,
            }, status=status.HTTP_200_OK)

        return Response({"error": "Failed to send OTP"}, status=status.HTTP_400_BAD_REQUEST)


class VerifyLoginOTPView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")
        otp = request.data.get("otp")

        if not mobile or not otp:
            return Response({"error": "Mobile number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP
        response = verify_otp(mobile, otp)
        
        if response.get("Status") == "Success":
            try:
                user = User.objects.get(mobile=mobile)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            login(request, user)
            return Response({
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": str(refresh),
                "user": {
                    "id": user.id,
                    "mobile": user.mobile,
                    "email": user.email,
                    "name": user.name,
                    "role": user.role,
                }
            }, status=status.HTTP_200_OK)

        return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)


class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")

            if not refresh_token:
                return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response({"message": "Logout successful."}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": "Invalid token or already logged out."}, status=status.HTTP_400_BAD_REQUEST)
        

class UserProfileUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user)
        return Response(serializer.data)
        
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            "message": "Profile updated successfully",
            "user": serializer.data
        })


class CreateReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ReviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Review submitted successfully!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class FavouriteAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        bus_id = request.data.get('bus_id')
        if not bus_id:
            return Response({'error': 'bus_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        bus = get_object_or_404(Bus, id=bus_id)

        favourite, created = Favourite.objects.get_or_create(user=request.user, bus=bus)
        if not created:
            return Response({'message': 'Already added to favourites'}, status=status.HTTP_200_OK)

        serializer = FavouriteSerializer(favourite)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        bus_id = request.data.get('bus_id')
        if not bus_id:
            return Response({'error': 'bus_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        bus = get_object_or_404(Bus, id=bus_id)
        favourite = Favourite.objects.filter(user=request.user, bus=bus).first()

        if not favourite:
            return Response({'message': 'This bus is not in your favourites'}, status=status.HTTP_404_NOT_FOUND)

        favourite.delete()
        return Response({'message': 'Removed from favourites'}, status=status.HTTP_204_NO_CONTENT)