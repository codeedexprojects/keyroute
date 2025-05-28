from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import generics, permissions
from admin_panel.utils import send_otp, verify_otp
from .serializers import  ReferralCodeSerializer, UserProfileSerializer,FavouriteSerializer,WalletSerializer,LoginSerializer,SignupSerializer,UserCreateSerializer
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
from .serializers import OngoingReferralSerializer, ReferralHistorySerializer,SightSerializer
from datetime import datetime, timedelta,timezone
from django.core.cache import cache
from django.db.models import Sum
from admin_panel.models import Experience,Sight
import pytz
import requests
import string
import random
from django.contrib.auth import login
from django.core.exceptions import ObjectDoesNotExist   
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import *
from admin_panel.models import OTPSession

User = get_user_model()

class AuthenticationView(APIView):
    def post(self, request):
        mobile = request.data.get('mobile')
        
        user_exists = User.objects.filter(mobile=mobile).exists()
        
        if user_exists:
            serializer = LoginSerializer(data=request.data)
        else:
            serializer = SignupSerializer(data=request.data)
            
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        mobile = serializer.validated_data['mobile']
        is_new_user = serializer.validated_data.get('is_new_user', False)
        
        # Clean up any existing OTP sessions for this mobile
        OTPSession.objects.filter(mobile=mobile).delete()
        
        # Send new OTP
        try:
            response = send_otp(mobile)
            print(f"OTP send response: {response}")
        except Exception as e:
            print(f"OTP send error: {str(e)}")
            return Response({"error": f"Failed to send OTP: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        if response.get("Status") == "Success":
            session_id = response.get("Details")
            from datetime import timezone
            now = datetime.now(timezone.utc)
            expiry_time = now + timedelta(minutes=10)
            
            # Store OTP session data in the database
            otp_session = OTPSession.objects.create(
                mobile=mobile,
                session_id=session_id,
                is_new_user=is_new_user,
                name=serializer.validated_data.get('name'),
                referral_code=serializer.validated_data.get('referral_code'),
                referrer=serializer.validated_data.get('referrer'),
                expires_at=expiry_time
            )
            
            print(f"OTP session created: {session_id} for mobile: {mobile}")
            
            return Response({
                "message": "OTP sent to your mobile",
                "session_id": session_id,
                "is_new_user": is_new_user,
                "temp_data": {
                    "name": serializer.validated_data.get('name'),
                    "mobile": mobile,
                    "referral_code": serializer.validated_data.get('referral_code'),
                }
            }, status=status.HTTP_200_OK)
        
        return Response({"error": "Failed to send OTP"}, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")
        otp = request.data.get("otp")
        session_id = request.data.get("session_id")

        if not mobile or not otp or not session_id:
            return Response({"error": "Mobile number, OTP, and session ID are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"VerifyOTP attempt: session={session_id}, mobile={mobile}")
            
        # Find the OTP session
        try:
            otp_session = OTPSession.objects.get(
                mobile=mobile,
                session_id=session_id
            )
        except OTPSession.DoesNotExist:
            return Response({
                "error": "OTP session expired or invalid. Please request a new OTP.",
                "code": "SESSION_NOT_FOUND",
                "session_id": session_id
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Check if the OTP has expired
        from datetime import timezone
        now = datetime.now(timezone.utc)
        if now > otp_session.expires_at:
            otp_session.delete()
            return Response({
                "error": "OTP has expired. Please request a new OTP.",
                "code": "OTP_EXPIRED"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Attempt to verify the OTP
        try:
            response = verify_otp(mobile, otp)
            print(f"OTP verification response: {response}")
        except Exception as e:
            print(f"OTP verification exception: {str(e)}")
            return Response({
                "error": f"Error verifying OTP: {str(e)}",
                "code": "VERIFICATION_ERROR"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        if response.get("Status") == "Success":
            is_new_user = otp_session.is_new_user
            
            if is_new_user:
                user_data = {
                    "name": otp_session.name,
                    "mobile": mobile,
                }
                
                serializer = UserCreateSerializer(
                    data=user_data,
                    context={"referrer": otp_session.referrer}
                )
                
                if serializer.is_valid():
                    user = serializer.save()
                else:
                    print(f"User creation errors: {serializer.errors}")
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                try:
                    user = User.objects.get(mobile=mobile)
                except User.DoesNotExist:
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Delete the OTP session after successful authentication
            otp_session.delete()

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

        return Response({
            "error": "Invalid OTP", 
            "code": "INVALID_OTP"
        }, status=status.HTTP_400_BAD_REQUEST)


class ResendOTPView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")
        session_id = request.data.get("session_id")

        if not mobile or not session_id:
            return Response({"error": "Mobile number and session ID are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"Resend OTP request: mobile={mobile}, session_id={session_id}")

        # Find the existing OTP session
        try:
            otp_session = OTPSession.objects.get(
                mobile=mobile,
                session_id=session_id
            )
        except OTPSession.DoesNotExist:
            return Response({
                "error": "No OTP session found. Please initiate authentication again.",
                "code": "SESSION_NOT_FOUND"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Send a new OTP
        try:
            response = send_otp(mobile)
            print(f"Resend OTP response: {response}")
        except Exception as e:
            print(f"Resend OTP error: {str(e)}")
            return Response({"error": f"Failed to resend OTP: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if response.get("Status") == "Success":
            new_session_id = response.get("Details")
            expiry_time = timezone.now() + timedelta(minutes=10)
            
            # Update session with new details
            otp_session.session_id = new_session_id
            otp_session.expires_at = expiry_time
            otp_session.save()

            print(f"OTP resent: old={session_id}, new={new_session_id}, mobile={mobile}")

            return Response({
                "message": "OTP resent successfully",
                "session_id": new_session_id,
                "mobile": mobile,
            }, status=status.HTTP_200_OK)

        return Response({"error": "Failed to resend OTP"}, status=status.HTTP_400_BAD_REQUEST)


class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")

            if not refresh_token:
                return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

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

class RemoveFavouriteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        bus_id = request.query_params.get('bus_id')
        package_id = request.query_params.get('package_id')

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
        return Response({'message': 'Removed from favourites'}, status=status.HTTP_200_OK)


class ListFavourites(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, bus_or_package):
        user = request.user

        if bus_or_package == "bus":
            favourites = Favourite.objects.filter(user=user).exclude(bus=None)
        elif bus_or_package == "package":
            favourites = Favourite.objects.filter(user=user).exclude(package=None)
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
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        referrals = ReferralRewardTransaction.objects.filter(
            referrer=request.user,
            status='credited'
        )
        
        serializer = ReferralHistorySerializer(referrals, many=True)

        total_reward = referrals.aggregate(total=Sum('reward_amount'))['total'] or 0

        response_data = {
            'total_reward': total_reward,
            'referral_history': serializer.data
        }

        return Response(response_data, status=status.HTTP_200_OK)


class SightView(APIView):
    def get(self, request):
        sights = Sight.objects.all()
        serializer = SightSerializer(sights, many=True)
        return Response(serializer.data)


class SightDetailView(APIView):
    def get_object(self, pk):
        try:
            return Sight.objects.get(pk=pk)
        except Sight.DoesNotExist:
            return None
    
    def get(self, request, pk):
        sight = self.get_object(pk)
        if not sight:
            return Response({'error': 'Sight not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SightDetailSerializer(sight)
        return Response(serializer.data)


class ExperienceView(APIView):
    def get(self, request, sight_id):
        experiences = Experience.objects.filter(sight_id=sight_id)
        serializer = ExperienceSerializer(experiences, many=True)
        return Response(serializer.data)



class ExperienceDetailView(APIView):
    def get_object(self, pk):
        try:
            return Experience.objects.get(pk=pk)
        except Experience.DoesNotExist:
            return None
    
    def get(self, request, pk):
        experience = self.get_object(pk)
        if not experience:
            return Response({'error': 'Experience not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = ExperienceSerializer(experience)
        return Response(serializer.data)


class SeasonTimeView(APIView):
    def get(self, request, sight_id):
        seasons = SeasonTime.objects.filter(sight_id=sight_id)
        serializer = SeasonTimeSerializer(seasons, many=True)
        return Response(serializer.data)


class SeasonTimeDetailView(APIView):
    def get_object(self, pk):
        try:
            return SeasonTime.objects.get(pk=pk)
        except SeasonTime.DoesNotExist:
            return None
    
    def get(self, request, pk):
        season = self.get_object(pk)
        if not season:
            return Response({'error': 'Season time not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = SeasonTimeSerializer(season)
        return Response(serializer.data)
    

class GreetingAPIView(APIView):
    def get(self, request):
        india_timezone = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(india_timezone)
        current_hour = current_time.hour
        
        if 5 <= current_hour < 12:
            greeting = "Good Morning"
        elif 12 <= current_hour < 17:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"
        return Response({"message": greeting})


class SimilarExperienceView(APIView):
    def get(self, request, sight_id, exclude_experience_id):
        similar_experiences = Experience.objects.filter(
            sight_id=sight_id
        ).exclude(id=exclude_experience_id)

        serializer = ExperienceSerializer(similar_experiences, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class LimitedDealListAPIView(APIView):
    def get(self, request):
        deals = LimitedDeal.objects.all().order_by('-created_at')
        serializer = LimitedDealSerializer(deals, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)