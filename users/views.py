from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import generics, permissions
from admin_panel.utils import send_otp, verify_otp
from .serializers import  ReferralCodeSerializer, UserProfileSerializer, UserSignupSerializer,FavouriteSerializer,UserWalletSerializer, OngoingReferralSerializer, ReferralHistorySerializer
from google.auth.transport import requests
from google.oauth2 import id_token
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from vendors.models import Bus,Package
from .models import Favourite,UserWallet, ReferralTransaction
from django.db.models import Q

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
    permission_classes = [IsAuthenticated]

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
    
# wallet and refrel

class WalletDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        wallet, created = UserWallet.objects.get_or_create(user=request.user)
        serializer = UserWalletSerializer(wallet)
        
        ongoing_referrals = ReferralTransaction.objects.filter(
            user=request.user,
            status='pending'
        ).order_by('-created_at')
        ongoing_serializer = OngoingReferralSerializer(ongoing_referrals, many=True)
        
        referral_history = ReferralTransaction.objects.filter(
            user=request.user,
            status='completed'
        ).order_by('-completed_at')
        history_serializer = ReferralHistorySerializer(referral_history, many=True)
        
        return Response({
            'wallet': serializer.data,
            'ongoing_referrals': ongoing_serializer.data,
            'referral_history': history_serializer.data,
            'referral_code': request.user.referral_code
        })

class ReferralDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        referral_code = request.user.referral_code
        
        total_referrals = ReferralTransaction.objects.filter(
            user=request.user
        ).count()
        
        completed_referrals = ReferralTransaction.objects.filter(
            user=request.user,
            status='completed'
        ).count()
        
        from django.db.models import Sum
        total_earnings = ReferralTransaction.objects.filter(
            user=request.user,
            status='completed'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return Response({
            'referral_code': referral_code,
            'total_referrals': total_referrals,
            'completed_referrals': completed_referrals,
            'total_earnings': total_earnings
        })