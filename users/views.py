from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import generics, permissions
from admin_panel.utils import send_otp, verify_otp
from .serializers import  ReferralCodeSerializer, UserProfileSerializer,FavouriteSerializer,WalletSerializer,AuthenticationSerializer,UserSignupSerializer
from google.auth.transport import requests
from google.oauth2 import id_token
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from vendors.models import Bus,Package
from .models import Favourite
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Wallet
from .models import ReferralRewardTransaction
from .serializers import OngoingReferralSerializer, ReferralHistorySerializer

User = get_user_model()

class AuthenticationView(APIView):
    """
    Combined API for login and signup functionality.
    If user already exists, it works as login.
    If user doesn't exist, it works as signup.
    """
    def post(self, request):
        serializer = AuthenticationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        mobile = serializer.validated_data['mobile']
        is_new_user = serializer.validated_data['is_new_user']
        
        # Send OTP for verification
        response = send_otp(mobile)
        
        if response.get("Status") == "Success":
            return Response({
                "message": "OTP sent to your mobile",
                "session_id": response.get("Details"),
                "is_new_user": is_new_user,
                "temp_data": {
                    "name": serializer.validated_data.get('name'),
                    "mobile": mobile,
                    "referral_code": serializer.validated_data.get('referral_code'),
                }
            }, status=status.HTTP_200_OK)
        
        return Response({"error": "Failed to send OTP"}, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    """
    Verify OTP and create user account if new user,
    or authenticate existing user.
    """
    def post(self, request):
        mobile = request.data.get("mobile")
        otp = request.data.get("otp")
        name = request.data.get("name")
        referral_code = request.data.get("referral_code")
        is_new_user = request.data.get("is_new_user", False)

        if not mobile or not otp:
            return Response({"error": "Mobile number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)
            
        # For new users, name is required
        if is_new_user and not name:
            return Response({"error": "Name is required for new users"}, status=status.HTTP_400_BAD_REQUEST)

        # Verify OTP
        response = verify_otp(mobile, otp)
        
        if response.get("Status") == "Success":
            # Handle new user registration
            if is_new_user:
                user_data = {
                    "name": name,
                    "mobile": mobile,
                    "referral_code": referral_code,
                }
                serializer = UserSignupSerializer(data=user_data)
                if serializer.is_valid():
                    user = serializer.save()
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            # Handle existing user login
            else:
                try:
                    user = User.objects.get(mobile=mobile)
                except User.DoesNotExist:
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Generate tokens and login
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            login(request, user)
            return Response({
                "message": "Authentication successful",
                "is_new_user": is_new_user,
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
        

class UserProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "message": "Profile updated successfully",
            "user": serializer.data
        }, status=status.HTTP_200_OK)


# class CreateReviewView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         serializer = ReviewSerializer(data=request.data, context={'request': request})
#         if serializer.is_valid():
#             serializer.save()
#             return Response({"message": "Review submitted successfully!"}, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


class FavouriteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        bus_id = request.data.get('bus_id')
        package_id = request.data.get('package_id')

        if not bus_id and not package_id:
            return Response({'error': 'bus_id or package_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if bus_id:
            bus = get_object_or_404(Bus, id=bus_id)
            favourite, created = Favourite.objects.get_or_create(user=request.user, bus=bus)
        else:
            package = get_object_or_404(Package, id=package_id)
            favourite, created = Favourite.objects.get_or_create(user=request.user, package=package)

        if not created:
            return Response({'message': 'Already added to favourites'}, status=status.HTTP_200_OK)

        serializer = FavouriteSerializer(favourite)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        bus_id = request.data.get('bus_id')
        package_id = request.data.get('package_id')

        if not bus_id and not package_id:
            return Response({'error': 'bus_id or package_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        if bus_id:
            bus = get_object_or_404(Bus, id=bus_id)
            favourite = Favourite.objects.filter(user=request.user, bus=bus).first()
        else:
            package = get_object_or_404(Package, id=package_id)
            favourite = Favourite.objects.filter(user=request.user, package=package).first()

        if not favourite:
            return Response({'message': 'Item is not in your favourites'}, status=status.HTTP_404_NOT_FOUND)

        favourite.delete()
        return Response({'message': 'Removed from favourites'}, status=status.HTTP_204_NO_CONTENT)


class ListFavourites(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, bus_or_package):
        user = request.user

        if bus_or_package == "bus":
            favourites = Favourite.objects.filter(user=user, bus__isnull=False)
        elif bus_or_package == "package":
            favourites = Favourite.objects.filter(user=user, package__isnull=False)
        else:
            return Response({'error': 'Invalid type. Use "bus" or "package".'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = FavouriteSerializer(favourites, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class GetReferralCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = ReferralCodeSerializer(user)
        return Response(serializer.data)
    
class GetWalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            wallet = user.wallet
        except Wallet.DoesNotExist:
            return Response({"error": "Wallet not found."}, status=404)

        serializer = WalletSerializer(wallet)
        return Response(serializer.data, status=200)
    

class OngoingReferralsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        referrals = ReferralRewardTransaction.objects.filter(
            referrer=request.user,
            status='pending'
        )
        
        serializer = OngoingReferralSerializer(referrals, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ReferralHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        referrals = ReferralRewardTransaction.objects.filter(
            referrer=request.user,
            status='credited'
        )
        
        serializer = ReferralHistorySerializer(referrals, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
