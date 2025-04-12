from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count
from .models import Booking, Traveler
from .serializers import (BookingSerializer, TravelerSerializer)
from vendors.models import Package
from vendors.serializers import PackageSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated

class BookingListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Only show bookings for the current user
        bookings = Booking.objects.filter(user=request.user)
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        if serializer.is_valid():
            booking = serializer.save(user=request.user)
            # No need to set total_travelers here as it should be 0 initially
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ListPackage(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        packages = Package.objects.all()
        serializer = PackageSerializer(packages, many=True)
        return Response(serializer.data)

class BookingDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        # Only allow access to the user's own bookings
        return get_object_or_404(Booking, pk=pk, user=user)
    
    def get(self, request, pk):
        booking = self.get_object(pk, request.user)
        serializer = BookingSerializer(booking)
        return Response(serializer.data)
    
    def put(self, request, pk):
        booking = self.get_object(pk, request.user)
        serializer = BookingSerializer(booking, data=request.data, partial=True)
        if serializer.is_valid():
            booking = serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        booking = self.get_object(pk, request.user)
        booking.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class AddTravelerAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
        serializer = TravelerSerializer(data=request.data)
        
        if serializer.is_valid():
            traveler = serializer.save(booking=booking)
            
            # Update total_travelers count
            booking.total_travelers = booking.travelers.count()
            booking.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TravelerListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, booking_id):
        booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
        travelers = booking.travelers.all()
        serializer = TravelerSerializer(travelers, many=True)
        return Response(serializer.data)

class TravelerDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        traveler = get_object_or_404(Traveler, pk=pk)
        if traveler.booking.user != user:
            self.permission_denied(self.request)
        return traveler
    
    def get(self, request, pk):
        traveler = self.get_object(pk, request.user)
        serializer = TravelerSerializer(traveler)
        return Response(serializer.data)
    
    def put(self, request, pk):
        traveler = self.get_object(pk, request.user)
        serializer = TravelerSerializer(traveler, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        traveler = self.get_object(pk, request.user)
        booking = traveler.booking
        traveler.delete()
        
        booking.total_travelers = booking.travelers.count()
        booking.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class BookingDetailsByStatus(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, status):
        user = request.user
        bookings = Booking.objects.filter(payment_status=status,user=user)
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)