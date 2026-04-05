# backend/bookings/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Guest, Booking
from rooms.models import Room
from .serializers import (
    GuestSerializer, BookingSerializer, 
    CreateBookingSerializer, SimpleBookingSerializer,
    CheckInSerializer
)

# ========== PUBLIC ENDPOINTS (No Authentication Required) ==========

@api_view(['POST'])
@permission_classes([AllowAny])
def public_booking(request):
    """Public endpoint for website bookings - no authentication required"""
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['name', 'email', 'phone', 'roomType', 'checkIn', 'checkOut']
        for field in required_fields:
            if not data.get(field):
                return Response(
                    {'error': f'{field} is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Split name into first and last name
        name_parts = data.get('name', '').strip().split()
        first_name = name_parts[0] if name_parts else 'Guest'
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else 'Visitor'
        
        # Create guest
        guest = Guest.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=data.get('email'),
            phone=data.get('phone'),
        )
        
        # Parse dates
        check_in = datetime.strptime(data.get('checkIn'), '%Y-%m-%d').date()
        check_out = datetime.strptime(data.get('checkOut'), '%Y-%m-%d').date()
        
        # Find available room
        # Get all rooms of requested type that are available
        available_rooms = Room.objects.filter(
            room_type=data.get('roomType'),
            status='available'
        )
        
        # Filter out rooms that are booked for these dates
        booked_room_ids = Booking.objects.filter(
            room__in=available_rooms,
            check_in__lt=check_out,
            check_out__gt=check_in,
            status__in=['confirmed', 'checked_in']
        ).values_list('room_id', flat=True)
        
        available_rooms = available_rooms.exclude(id__in=booked_room_ids)
        
        if not available_rooms.exists():
            # If specific type not available, try any available room
            any_available = Room.objects.filter(status='available').exclude(
                id__in=Booking.objects.filter(
                    check_in__lt=check_out,
                    check_out__gt=check_in,
                    status__in=['confirmed', 'checked_in']
                ).values_list('room_id', flat=True)
            ).first()
            
            if any_available:
                room = any_available
            else:
                return Response(
                    {'error': 'No rooms available for selected dates'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            room = available_rooms.first()
        
        # Calculate nights
        nights = (check_out - check_in).days
        
        # Create booking
        booking = Booking.objects.create(
            guest=guest,
            room=room,
            check_in=check_in,
            check_out=check_out,
            adults=data.get('adults', 1),
            children=data.get('children', 0),
            total_nights=nights,
            total_amount=data.get('totalAmount', 0),
            special_requests=data.get('specialRequests', ''),
            status='confirmed',
            payment_status='pending'
        )
        
        return Response({
            'success': True,
            'booking_reference': booking.booking_reference,
            'message': 'Booking created successfully',
            'room_number': room.room_number
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['GET'])
@permission_classes([AllowAny])
def public_availability(request):
    """Public endpoint to check room availability"""
    check_in = request.query_params.get('check_in')
    check_out = request.query_params.get('check_out')
    room_type = request.query_params.get('room_type')
    
    if not check_in or not check_out:
        return Response(
            {'error': 'Check-in and check-out dates required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
        
        # Base query for available rooms
        available_rooms = Room.objects.filter(status='available')
        
        if room_type:
            available_rooms = available_rooms.filter(room_type=room_type)
        
        # Exclude rooms booked for these dates
        booked_room_ids = Booking.objects.filter(
            check_in__lt=check_out_date,
            check_out__gt=check_in_date,
            status__in=['confirmed', 'checked_in']
        ).values_list('room_id', flat=True)
        
        available_rooms = available_rooms.exclude(id__in=booked_room_ids)
        
        return Response({
            'available': available_rooms.exists(),
            'available_rooms': available_rooms.count(),
            'room_types': list(available_rooms.values_list('room_type', flat=True).distinct())
        })
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

# ========== VIEWSETS (Require Authentication) ==========

class GuestViewSet(viewsets.ModelViewSet):
    queryset = Guest.objects.all().order_by('-created_at')
    serializer_class = GuestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Guest.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
        return queryset

class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all().order_by('-created_at')
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateBookingSerializer
        return BookingSerializer
    
    def get_queryset(self):
        queryset = Booking.objects.all()
        
        # Filter by status
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(
                check_in__gte=start_date,
                check_out__lte=end_date
            )
        
        # Filter by room
        room = self.request.query_params.get('room')
        if room:
            queryset = queryset.filter(room_id=room)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(booking_reference__icontains=search) |
                Q(guest__first_name__icontains=search) |
                Q(guest__last_name__icontains=search) |
                Q(room__room_number__icontains=search)
            )
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def check_in(self, request, pk=None):
        booking = self.get_object()
        serializer = CheckInSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        if booking.status != 'confirmed':
            return Response(
                {'error': 'Booking must be confirmed to check in'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.payment_method = serializer.validated_data['payment_method']
        if serializer.validated_data.get('amount_paid'):
            booking.amount_paid = serializer.validated_data['amount_paid']
        
        booking.payment_status = 'paid'
        booking.status = 'checked_in'
        booking.checked_in_at = timezone.now()
        booking.save()
        
        room = booking.room
        room.status = 'occupied'
        room.save()
        
        return Response(BookingSerializer(booking).data)
    
    @action(detail=True, methods=['post'])
    def check_out(self, request, pk=None):
        booking = self.get_object()
        
        if booking.status != 'checked_in':
            return Response(
                {'error': 'Booking must be checked in to check out'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'checked_out'
        booking.checked_out_at = timezone.now()
        booking.save()
        
        room = booking.room
        room.status = 'cleaning'
        room.save()
        
        return Response(BookingSerializer(booking).data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        
        if booking.status in ['checked_out', 'cancelled']:
            return Response(
                {'error': f'Booking already {booking.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        booking.status = 'cancelled'
        booking.save()
        
        if booking.payment_status == 'paid':
            booking.payment_status = 'refunded'
            booking.save()
        
        return Response(BookingSerializer(booking).data)
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.now().date()
        
        arrivals = self.queryset.filter(
            check_in=today,
            status__in=['confirmed', 'checked_in']
        )
        
        departures = self.queryset.filter(
            check_out=today,
            status='checked_in'
        )
        
        return Response({
            'arrivals': SimpleBookingSerializer(arrivals, many=True).data,
            'departures': SimpleBookingSerializer(departures, many=True).data,
            'arrivals_count': arrivals.count(),
            'departures_count': departures.count(),
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        total_bookings = Booking.objects.count()
        active_guests = Booking.objects.filter(status='checked_in').count()
        today_arrivals = Booking.objects.filter(
            check_in=timezone.now().date(),
            status='confirmed'
        ).count()
        today_departures = Booking.objects.filter(
            check_out=timezone.now().date(),
            status='checked_in'
        ).count()
        
        return Response({
            'total_bookings': total_bookings,
            'active_guests': active_guests,
            'today_arrivals': today_arrivals,
            'today_departures': today_departures,
        })
    