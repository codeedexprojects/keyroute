from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserLoginSerializer, UserSignupSerializer
from google.auth.transport import requests
from google.oauth2 import id_token
from django.conf import settings
from rest_framework.permissions import IsAuthenticated

User = get_user_model()

class UserSignupView(APIView):
    def post(self, request):
        data = request.data

        # if "google_token" in data:  # Google Signup
        #     try:
        #         id_info = id_token.verify_oauth2_token(
        #             data["google_token"], requests.Request(), settings.GOOGLE_CLIENT_ID
        #         )

        #         email = id_info["email"]
        #         user, created = User.objects.get_or_create(email=email, defaults={"username": email.split('@')[0]})

        #         return Response({"message": "Google Signup Successful", "new_user": created}, status=status.HTTP_200_OK)

        #     except Exception as e:
        #         return Response({"error": "Invalid Google token"}, status=status.HTTP_400_BAD_REQUEST)

        # else:
             # Phone Number Signup
        serializer = UserSignupSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class UserLoginView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            login(request, user)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            return Response({
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": str(refresh),
                "user": {
                    "id": user.id,
                    "phone_number": user.phone_number,
                    "email": user.email,
                    "role": user.role
                }
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    




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
