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
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils.timezone import now
import logging
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

User = get_user_model()

class AuthenticationView(APIView):
    def post(self, request):
        mobile = request.data.get('mobile')

        # 🧪 Guest login shortcut
        if str(mobile) == "1234567890":
            user, created = User.objects.get_or_create(
                mobile="1234567890",
                defaults={
                    "name": "Guest User", 
                    "email": "guest@example.com",
                    "role": "user"  # Add this line to fix the error
                }
            )

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            login(request, user)

            return Response({
                "message": "Guest login successful",
                "session_id": "guest",
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

        # 🧾 Check if user exists
        user_exists = User.objects.filter(mobile=mobile).exists()
        serializer = LoginSerializer(data=request.data) if user_exists else SignupSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        mobile = serializer.validated_data['mobile']
        is_new_user = serializer.validated_data.get('is_new_user', False)

        # Clear any old OTP sessions
        OTPSession.objects.filter(mobile=mobile).delete()

        # Send OTP
        try:
            response = send_otp(mobile)
        except Exception as e:
            return Response({"error": f"Failed to send OTP: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if response.get("Status") == "Success":
            session_id = response.get("Details")
            expiry_time = now() + timedelta(minutes=10)

            OTPSession.objects.create(
                mobile=mobile,
                session_id=session_id,
                is_new_user=is_new_user,
                name=serializer.validated_data.get('name'),
                referral_code=serializer.validated_data.get('referral_code'),
                referrer=serializer.validated_data.get('referrer'),
                expires_at=expiry_time
            )

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
            return Response({"error": "Mobile, OTP and session_id are required"}, status=status.HTTP_400_BAD_REQUEST)

        # 🧪 Guest login shortcut
        if str(mobile) == "1234567890" and str(otp) == "123456":
            user, created = User.objects.get_or_create(
                mobile="1234567890",
                defaults={"name": "Guest User", "email": "guest@example.com"}
            )

            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            login(request, user)

            return Response({
                "message": "Guest login successful",
                "is_new_user": False,
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

        # 🔍 Get OTP session
        try:
            otp_session = OTPSession.objects.get(mobile=mobile, session_id=session_id)
        except OTPSession.DoesNotExist:
            return Response({
                "error": "OTP session expired or invalid. Please request a new OTP.",
                "code": "SESSION_NOT_FOUND"
            }, status=status.HTTP_400_BAD_REQUEST)

        # ⏳ Check if expired
        if now() > otp_session.expires_at:
            otp_session.delete()
            return Response({
                "error": "OTP has expired. Please request a new OTP.",
                "code": "OTP_EXPIRED"
            }, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Verify OTP or allow 123456 for test/dev
        try:
            if str(otp) == "123456":
                response = {"Status": "Success"}
            else:
                response = verify_otp(mobile, otp)
        except Exception as e:
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

                serializer = UserCreateSerializer(data=user_data, context={"referrer": otp_session.referrer})
                if serializer.is_valid():
                    user = serializer.save()
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                try:
                    user = User.objects.get(mobile=mobile)
                except User.DoesNotExist:
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

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
    
class GetLocationAPIView(APIView):
    def get(self, request):
        searches = UserBusSearch.objects.all()
        data = []

        for search in searches:
            data.append({
                'user_id': search.user.id,
                'from_lat': search.from_lat,
                'from_lon': search.from_lon,
                'to_lat': search.to_lat,
                'to_lon': search.to_lon,
            })

        return Response({'locations': data})
    



import firebase_admin
from firebase_admin import auth, credentials
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login
import requests

class FirebaseGoogleAuthView(APIView):
    def post(self, request):
        firebase_token = request.data.get('firebase_token')
        referral_code = request.data.get('referral_code')
        
        if not firebase_token:
            return Response({
                "error": "Firebase token is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Verify the Firebase ID token
            decoded_token = auth.verify_id_token(firebase_token)
            
            # Extract user information from Firebase token
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email')
            name = decoded_token.get('name', '')
            picture = decoded_token.get('picture')
            phone_number = decoded_token.get('phone_number')
            
            if not email:
                return Response({
                    "error": "Email is required from Google account"
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if user already exists
            user = None
            is_new_user = False
            
            # First try to find by email
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # If phone number exists, try to find by mobile
                if phone_number:
                    try:
                        user = User.objects.get(mobile=phone_number)
                        # Update the user with Google info
                        user.email = email
                        user.name = name or user.name
                        user.is_google_user = True
                        user.firebase_uid = firebase_uid
                        user.save()
                    except User.DoesNotExist:
                        pass
            
            # If user doesn't exist, create new user
            if not user:
                is_new_user = True
                
                # Validate referral code if provided
                referrer = None
                if referral_code:
                    try:
                        referrer = User.objects.get(referral_code=referral_code)
                        # Check if user is trying to refer themselves (by email)
                        if email == referrer.email:
                            return Response({
                                "error": "You cannot refer yourself"
                            }, status=status.HTTP_400_BAD_REQUEST)
                    except User.DoesNotExist:
                        return Response({
                            "error": "Invalid referral code"
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Create new user
                user_data = {
                    'email': email,
                    'name': name,
                    'mobile': phone_number,
                    'is_google_user': True,
                    'firebase_uid': firebase_uid,
                }
                
                serializer = GoogleUserCreateSerializer(
                    data=user_data,
                    context={"referrer": referrer}
                )
                
                if serializer.is_valid():
                    user = serializer.save()
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
                # Download and save profile image if available
                if picture:
                    try:
                        self.save_profile_image_from_url(user, picture)
                    except Exception as e:
                        print(f"Failed to save profile image: {str(e)}")
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            
            # Login user
            login(request, user)
            
            return Response({
                "message": "Google authentication successful",
                "is_new_user": is_new_user,
                "access_token": access_token,
                "refresh_token": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "mobile": user.mobile,
                    "name": user.name,
                    "role": user.role,
                    "profile_image": user.profile_image.url if user.profile_image else None,
                    "referral_code": user.referral_code,
                }
            }, status=status.HTTP_200_OK)
            
        except auth.InvalidIdTokenError:
            return Response({
                "error": "Invalid Firebase token"
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            print(f"Firebase auth error: {str(e)}")
            return Response({
                "error": "Authentication failed"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def save_profile_image_from_url(self, user, image_url):
        """Download and save profile image from Google"""
        try:
            import os
            from django.core.files.base import ContentFile
            from django.core.files.storage import default_storage
            
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                # Create filename
                file_extension = 'jpg'  # Google images are usually jpg
                filename = f'profile_images/google_{user.id}_{user.firebase_uid[:8]}.{file_extension}'
                
                # Save image
                user.profile_image.save(
                    filename,
                    ContentFile(response.content),
                    save=True
                )
        except Exception as e:
            print(f"Error saving profile image: {str(e)}")
            raise e
        



class DeleteUserAccountView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def delete(self, request):
        user = request.user
        user.delete()   
        return Response({"message": "User account deleted successfully."}, status=status.HTTP_204_NO_CONTENT)






class UpdateDistrictAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_district_from_coordinates(self, lat, lon):
        """
        Fetch district and state from latitude and longitude using OpenStreetMap's Nominatim API.
        """
        try:
            nominatim_url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'addressdetails': 1,
                'zoom': 10,
                'countrycodes': 'in'  # India only
            }
            headers = {
                'User-Agent': 'keyroute/1.0'
            }

            response = requests.get(nominatim_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                address = data.get('address', {})

                district = (
                    address.get('state_district') or 
                    address.get('district') or 
                    address.get('county') or
                    address.get('suburb') or
                    address.get('city_district')
                )
                state = address.get('state')

                return district, state
        except Exception as e:
            print(f"Nominatim geocoding failed: {str(e)}")
        
        return None, None

    def post(self, request):
        """
        POST endpoint to update user's district and state based on coordinates.
        """
        serializer = UpdateDistrictSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': 'Invalid input data',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']
        
        if not (6.0 <= latitude <= 37.6 and 68.7 <= longitude <= 97.25):
            return Response({
                'success': False,
                'message': 'Coordinates appear to be outside India'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            district, state = self.get_district_from_coordinates(latitude, longitude)
            
            if not district:
                return Response({
                    'success': False,
                    'message': 'Could not determine district from provided coordinates'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = request.user
            user.district = district
            user.state = state
            user.save(update_fields=['district', 'state'])
            
            return Response({
                'success': True,
                'message': 'District and state updated successfully',
                'data': {
                    'user_id': user.id,
                    'district': district,
                    'state': state,
                    'coordinates': {
                        'latitude': latitude,
                        'longitude': longitude
                    }
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error updating district: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def get(self, request):
        """
        GET endpoint to return current user's district, state, and city.
        """
        user = request.user
        return Response({
            'success': True,
            'data': {
                'user_id': user.id,
                'name': user.name,
                'district': user.district,
                'state': user.state,
                'city': user.city
            }
        }, status=status.HTTP_200_OK)







class RegisterFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Register or update FCM token for the authenticated user
        
        Expected payload:
        {
            "fcm_token": "your-fcm-token-here"
        }
        """
        fcm_token = request.data.get('fcm_token')
        
        if not fcm_token:
            return Response(
                {
                    "success": False,
                    "message": "FCM token is required"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Basic validation - FCM tokens are typically long strings
        if len(fcm_token) < 50:
            return Response(
                {
                    "success": False,
                    "message": "Invalid FCM token format"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Check if this is actually a new token
            old_token = request.user.fcm_token
            if old_token == fcm_token:
                return Response(
                    {
                        "success": True,
                        "message": "FCM token is already registered"
                    },
                    status=status.HTTP_200_OK
                )
            
            # Update FCM token directly on User model
            request.user.fcm_token = fcm_token
            request.user.save(update_fields=['fcm_token'])
            
            # Log the token update for debugging
            logger.info(f"FCM token updated for user {request.user.id}")
            
            return Response(
                {
                    "success": True,
                    "message": "FCM token registered successfully"
                },
                status=status.HTTP_200_OK
            )
            
        except ValidationError as e:
            logger.error(f"Validation error updating FCM token for user {request.user.id}: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": "Invalid FCM token"
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating FCM token for user {request.user.id}: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": "Error registering FCM token"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request):
        """
        Remove FCM token for the authenticated user (useful for logout)
        """
        try:
            # Check if user already has no token
            if not request.user.fcm_token:
                return Response(
                    {
                        "success": True,
                        "message": "No FCM token to remove"
                    },
                    status=status.HTTP_200_OK
                )
            
            request.user.fcm_token = None
            request.user.save(update_fields=['fcm_token'])
            
            # Log the token removal
            logger.info(f"FCM token removed for user {request.user.id}")
            
            return Response(
                {
                    "success": True,
                    "message": "FCM token removed successfully"
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error removing FCM token for user {request.user.id}: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": "Error removing FCM token"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def get(self, request):
        """
        Get the current FCM token status for the authenticated user
        """
        try:
            has_token = bool(request.user.fcm_token)
            
            return Response(
                {
                    "success": True,
                    "has_fcm_token": has_token,
                    "message": "FCM token status retrieved successfully"
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error getting FCM token status for user {request.user.id}: {str(e)}")
            return Response(
                {
                    "success": False,
                    "message": "Error getting FCM token status"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )