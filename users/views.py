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
from .serializers import OngoingReferralSerializer, ReferralHistorySerializer,ExploreSerializer,SightSerializer
from datetime import datetime, timedelta
from django.core.cache import cache
from django.db.models import Sum
from admin_panel.models import Experience,Sight
import pytz

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
        is_new_user = serializer.validated_data['is_new_user']
        
        # Clear any existing memory backups to avoid confusion
        try:
            for attr in dir(VerifyOTPView):
                if attr.startswith(f"memory_otp_{mobile}_"):
                    delattr(VerifyOTPView, attr)
        except:
            pass
            
        # Clear any existing OTP sessions for this mobile number
        try:
            existing_keys = [k for k in cache._cache.keys() if isinstance(k, str) and k.startswith("otp_")]
            for key in existing_keys:
                data = cache.get(key)
                if data and data.get("mobile") == mobile:
                    cache.delete(key)
        except:
            pass
        
        # Send the OTP
        try:
            response = send_otp(mobile)
            print(f"OTP send response: {response}")
        except Exception as e:
            print(f"OTP send error: {str(e)}")
            return Response({"error": f"Failed to send OTP: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        if response.get("Status") == "Success":
            session_id = response.get("Details")
            expiry_time = datetime.now() + timedelta(minutes=10)
            
            cache_key = f"otp_{session_id}"
            
            # Store all necessary data
            otp_data = {
                "mobile": mobile,
                "is_new_user": is_new_user,
                "expiry_time": expiry_time.timestamp(),
                "name": serializer.validated_data.get('name'),
                "referral_code": serializer.validated_data.get('referral_code'),
                "referrer": serializer.validated_data.get('referrer'),
                "session_id": session_id,  # Include the session_id in the cache data
                "created_at": datetime.now().timestamp(),  # Add creation timestamp
            }
            
            # Save to both cache and class-level memory
            cache.set(cache_key, otp_data, timeout=600)
            
            # Also store in class-level attribute as backup
            memory_key = f"memory_otp_{mobile}_{session_id}"
            setattr(VerifyOTPView, memory_key, otp_data)
            
            # Important debug log
            print(f"OTP session created: {session_id} for mobile: {mobile}, cache_key: {cache_key}")
            
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
        
        # Important debug log - keep this in production for troubleshooting
        print(f"VerifyOTP attempt: session={session_id}, mobile={mobile}")
            
        # First try the direct cache key approach
        cache_key = f"otp_{session_id}"
        otp_data = cache.get(cache_key)
        
        # Store session data in memory if verification fails on first attempt
        # This creates a temporary backup to help with race conditions
        memory_key = f"memory_otp_{mobile}_{session_id}"
        if not otp_data:
            otp_data = getattr(VerifyOTPView, memory_key, None)
            if otp_data:
                print(f"Retrieved OTP data from memory backup: {memory_key}")
        
        # If still not found, try a broader search in the cache
        if not otp_data:
            try:
                # Try to find by mobile number in any active OTP session
                for key in cache._cache.keys():
                    if isinstance(key, str) and key.startswith("otp_"):
                        data = cache.get(key)
                        if data and data.get("mobile") == mobile:
                            print(f"Found alternative session key: {key}")
                            otp_data = data
                            cache_key = key
                            break
            except (AttributeError, TypeError):
                # Handle cases where cache doesn't expose keys method
                pass
                        
        if not otp_data:
            # Store the request parameters to help debugging
            print(f"Session not found. Request data: {request.data}")
            return Response({
                "error": "OTP session expired or invalid. Please request a new OTP.",
                "code": "SESSION_NOT_FOUND",
                "session_id": session_id
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Keep a memory backup for subsequent attempts
        setattr(VerifyOTPView, memory_key, otp_data)
            
        current_time = datetime.now().timestamp()
        if current_time > otp_data.get("expiry_time", 0):
            cache.delete(cache_key)
            delattr(VerifyOTPView, memory_key)
            return Response({
                "error": "OTP has expired. Please request a new OTP.",
                "code": "OTP_EXPIRED"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate that the mobile number matches what's in the cache
        if otp_data.get("mobile") != str(mobile):
            print(f"Mobile mismatch: {otp_data.get('mobile')} vs {mobile}")
            return Response({
                "error": "Mobile number mismatch. Please restart authentication.",
                "code": "MOBILE_MISMATCH"
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
            is_new_user = otp_data.get("is_new_user", False)
            
            if is_new_user:
                user_data = {
                    "name": otp_data.get("name"),
                    "mobile": mobile,
                }
                
                serializer = UserCreateSerializer(
                    data=user_data,
                    context={"referrer": otp_data.get("referrer")}
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

            # Delete the cache and memory backup after successful authentication
            try:
                cache.delete(cache_key)
                delattr(VerifyOTPView, f"memory_otp_{mobile}_{session_id}")
            except (AttributeError, KeyError):
                pass

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
    

class ResendOTPView(APIView):
    def post(self, request):
        mobile = request.data.get("mobile")
        session_id = request.data.get("session_id")

        if not mobile or not session_id:
            return Response({"error": "Mobile number and session ID are required"}, status=status.HTTP_400_BAD_REQUEST)

        # Important debugging
        print(f"Resend OTP request: mobile={mobile}, session_id={session_id}")

        # First look in the direct cache
        cache_key = f"otp_{session_id}"
        otp_data = cache.get(cache_key)

        # If not in cache, check the memory backup
        memory_key = f"memory_otp_{mobile}_{session_id}"
        if not otp_data:
            otp_data = getattr(VerifyOTPView, memory_key, None)
            if otp_data:
                print(f"Retrieved OTP data from memory for resend: {memory_key}")
        
        # If still not found, try to find any session for this mobile
        if not otp_data:
            try:
                # Try memory backups first
                for attr in dir(VerifyOTPView):
                    if attr.startswith(f"memory_otp_{mobile}_"):
                        otp_data = getattr(VerifyOTPView, attr)
                        memory_key = attr
                        break
                        
                # Then try cache
                if not otp_data:
                    for key in cache._cache.keys():
                        if isinstance(key, str) and key.startswith("otp_"):
                            data = cache.get(key)
                            if data and data.get("mobile") == mobile:
                                otp_data = data
                                cache_key = key
                                break
            except:
                pass

        if not otp_data:
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
            expiry_time = datetime.now() + timedelta(minutes=10)
            
            new_cache_key = f"otp_{new_session_id}"
            new_memory_key = f"memory_otp_{mobile}_{new_session_id}"

            # Create a fresh OTP data record
            new_otp_data = {
                **otp_data,
                "expiry_time": expiry_time.timestamp(),
                "session_id": new_session_id,
                "resent_at": datetime.now().timestamp(),
            }
            
            # Save to both cache and memory
            cache.set(new_cache_key, new_otp_data, timeout=600)
            setattr(VerifyOTPView, new_memory_key, new_otp_data)

            # Clean up old data
            try:
                cache.delete(cache_key)
                delattr(VerifyOTPView, memory_key)
            except:
                pass

            print(f"OTP resent: old={session_id}, new={new_session_id}, mobile={mobile}")

            return Response({
                "message": "OTP resent successfully",
                "session_id": new_session_id,
                "mobile": mobile,
            }, status=status.HTTP_200_OK)

        return Response({"error": "Failed to resend OTP"}, status=status.HTTP_400_BAD_REQUEST)

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
    
class ExperianceView(APIView):

    def get(self,request,sight):
        experience = Experience.objects.filter(sight=sight)
        serializer = ExploreSerializer(experience,many=True)
        return Response(serializer.data)
    
class SightView(APIView):

    def get(self,request):
        sight = Sight.objects.all()
        serializer = SightSerializer(sight,many=True)
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
