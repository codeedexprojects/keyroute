from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import generics, permissions
from admin_panel.serializers import UserSerializer
from admin_panel.utils import send_otp, verify_otp
from .serializers import ResetPasswordSerializer, ReviewSerializer, SendOTPSerializer, UserLoginSerializer, UserProfileSerializer, UserSignupSerializer
from google.auth.transport import requests
from google.oauth2 import id_token
from django.conf import settings
from rest_framework.permissions import IsAuthenticated

User = get_user_model()

class NormalUserSignupView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")
        if not mobile:
            return Response({"error": "Mobile number is required"}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(mobile=mobile).exists():
            return Response({"error": "Mobile number already registered"}, status=status.HTTP_400_BAD_REQUEST)

        response = send_otp(mobile)
        print(response)
        if response.get("Status") == "Success":
            return Response({"message": "OTP sent to your mobile"}, status=status.HTTP_200_OK)
        
        return Response({"error": "Failed to send OTP"}, status=status.HTTP_400_BAD_REQUEST)


class VerifySignupOTPView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")
        otp = request.data.get("otp")

        if not mobile or not otp:
            return Response({"error": "Mobile number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        response = verify_otp(mobile, otp)
        if response.get("Status") == "Success":
            user, created = User.objects.get_or_create(mobile=mobile)
            return Response({"message": "Signup successful", "new_user": created}, status=status.HTTP_201_CREATED)

        return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)


class NormalUserLoginView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")
        if not mobile:
            return Response({"error": "Mobile number is required"}, status=status.HTTP_400_BAD_REQUEST)

        if not User.objects.filter(mobile=mobile).exists():
            return Response({"error": "User does not exist. Please sign up first."}, status=status.HTTP_400_BAD_REQUEST)

        response = send_otp(mobile)
        if response.get("Status") == "Success":
            return Response({"message": "OTP sent to your mobile"}, status=status.HTTP_200_OK)

        return Response({"error": "Failed to send OTP"}, status=status.HTTP_400_BAD_REQUEST)


class VerifyLoginOTPView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")
        otp = request.data.get("otp")

        if not mobile or not otp:
            return Response({"error": "Mobile number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)

        response = verify_otp(mobile, otp)
        if response.get("Status") == "Success":
            user, _ = User.objects.get_or_create(mobile=mobile)

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            login(request, user)
            return Response({"message": "Login successful",
                             "access_token": access_token,
                            "refresh_token": str(refresh),
                            "user": {
                                "id": user.id,
                                "mobile": user.mobile,
                                "email": user.email,
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


class SendOTPView(APIView):
    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)
        if serializer.is_valid():
            response = serializer.send_otp()
            return Response(response, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            response = serializer.save()
            return Response(response, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class CreateReviewView(APIView):
    permission_classes = [IsAuthenticated]  # User must be logged in

    def post(self, request):
        serializer = ReviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Review submitted successfully!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class UserProfileUpdateView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for users to view and update their profile.
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Return the authenticated user"""
        return self.request.user