from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from .models import Booking, Traveler, Payment, CancellationPolicy
from .serializers import (BookingSerializer, TravelerSerializer, 
                         PaymentSerializer, CancellationPolicySerializer)

# Create your views here.

class BookingListCreateAPIView(APIView):
    def get(self, request):
        bookings = Booking.objects.all()
        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        serializer = BookingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BookingDetailAPIView(APIView):
    def get_object(self, pk):
        return get_object_or_404(Booking, pk=pk)
    
    def get(self, request, pk):
        booking = self.get_object(pk)
        serializer = BookingSerializer(booking)
        return Response(serializer.data)
    
    def put(self, request, pk):
        booking = self.get_object(pk)
        serializer = BookingSerializer(booking, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        booking = self.get_object(pk)
        booking.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class AddTravelerAPIView(APIView):
    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, pk=booking_id)
        serializer = TravelerSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(booking=booking)
            
            # Update booking counts
            male_count = booking.travelers.filter(gender='M').count()
            female_count = booking.travelers.filter(gender='F').count()
            children_count = booking.travelers.filter(age__lt=4).count()
            
            booking.total_males = male_count
            booking.total_females = female_count
            booking.total_children = children_count
            booking.total_adults = male_count + female_count - children_count
            booking.total_travelers = male_count + female_count
            booking.save()
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TravelerListAPIView(APIView):
    def get(self, request, booking_id):
        booking = get_object_or_404(Booking, pk=booking_id)
        travelers = booking.travelers.all()
        serializer = TravelerSerializer(travelers, many=True)
        return Response(serializer.data)

class TravelerDetailAPIView(APIView):
    def get_object(self, pk):
        return get_object_or_404(Traveler, pk=pk)
    
    def get(self, request, pk):
        traveler = self.get_object(pk)
        serializer = TravelerSerializer(traveler)
        return Response(serializer.data)
    
    def put(self, request, pk):
        traveler = self.get_object(pk)
        serializer = TravelerSerializer(traveler, data=request.data)
        if serializer.is_valid():
            serializer.save()
            
            # Update booking counts
            booking = traveler.booking
            male_count = booking.travelers.filter(gender='M').count()
            female_count = booking.travelers.filter(gender='F').count()
            children_count = booking.travelers.filter(age__lt=4).count()
            
            booking.total_males = male_count
            booking.total_females = female_count
            booking.total_children = children_count
            booking.total_adults = male_count + female_count - children_count
            booking.total_travelers = male_count + female_count
            booking.save()
            
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        traveler = self.get_object(pk)
        booking = traveler.booking
        traveler.delete()
        
        # Update booking counts after deletion
        male_count = booking.travelers.filter(gender='M').count()
        female_count = booking.travelers.filter(gender='F').count()
        children_count = booking.travelers.filter(age__lt=4).count()
        
        booking.total_males = male_count
        booking.total_females = female_count
        booking.total_children = children_count
        booking.total_adults = male_count + female_count - children_count
        booking.total_travelers = male_count + female_count
        booking.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)

class MakePaymentAPIView(APIView):
    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, pk=booking_id)
        payment_type = request.data.get('payment_type')
        amount = request.data.get('amount')
        
        if not amount:
            return Response({"error": "Amount is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create payment record
        payment = Payment.objects.create(
            booking=booking,
            amount=amount,
            payment_type=payment_type,
            transaction_id=request.data.get('transaction_id')
        )
        
        # Update booking payment status
        total_paid = booking.payments.aggregate(total=Sum('amount'))['total'] or 0
        
        if total_paid >= booking.total_amount:
            booking.payment_status = 'paid'
        elif total_paid > 0:
            booking.payment_status = 'partial'
        
        booking.save()
        
        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

class PaymentListAPIView(APIView):
    def get(self, request, booking_id):
        booking = get_object_or_404(Booking, pk=booking_id)
        payments = booking.payments.all()
        serializer = PaymentSerializer(payments, many=True)
        return Response(serializer.data)

class CancellationPolicyListAPIView(APIView):
    def get(self, request):
        policies = CancellationPolicy.objects.all()
        serializer = CancellationPolicySerializer(policies, many=True)
        return Response(serializer.data)

class CancellationPolicyDetailAPIView(APIView):
    def get(self, request, package_id):
        policy = get_object_or_404(CancellationPolicy, package_id=package_id)
        serializer = CancellationPolicySerializer(policy)
        return Response(serializer.data)