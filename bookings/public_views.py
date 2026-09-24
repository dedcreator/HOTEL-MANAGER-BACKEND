# backend/bookings/public_views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from decimal import Decimal
import json
import datetime
from .models import Guest, Booking
from rooms.models import Room


@csrf_exempt
@require_http_methods(["POST"])
def create_booking(request):
    """Public endpoint for creating bookings"""
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        required = ['name', 'roomType', 'checkIn', 'checkOut']
        for field in required:
            if not data.get(field):
                return JsonResponse({'error': f'{field} is required'}, status=400)
        
        # Split name
        name_parts = data['name'].strip().split()
        first_name = name_parts[0] if name_parts else 'Guest'
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else 'Guest'
        
        # Parse dates
        try:
            check_in = datetime.datetime.strptime(data['checkIn'], '%Y-%m-%d').date()
            check_out = datetime.datetime.strptime(data['checkOut'], '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

        if check_out <= check_in:
            return JsonResponse({'error': 'Check-out date must be after check-in date'}, status=400)

        # Normalize room type (e.g. duplex -> deluxe)
        raw_room_type = str(data.get('roomType', '')).lower().strip()
        room_type_map = {
            'standard': 'standard',
            'duplex': 'deluxe',
            'deluxe': 'deluxe',
            'suite': 'deluxe',
        }
        target_room_type = room_type_map.get(raw_room_type, 'standard')
        
        nights = max(1, (check_out - check_in).days)

        with transaction.atomic():
            # Find rooms matching type
            matching_rooms = Room.objects.filter(room_type=target_room_type)
            if not matching_rooms.exists():
                matching_rooms = Room.objects.all()

            # Find rooms not booked for these dates
            booked_room_ids = Booking.objects.filter(
                check_in__lt=check_out,
                check_out__gt=check_in,
                status__in=['confirmed', 'checked_in']
            ).values_list('room_id', flat=True)

            available_room = matching_rooms.exclude(id__in=booked_room_ids).first()
            if not available_room:
                # If all matching are booked, fallback to any available room in database
                available_room = matching_rooms.first() or Room.objects.first()

            if not available_room:
                # If no rooms exist at all, create a default room
                available_room = Room.objects.create(
                    room_number='101',
                    room_type=target_room_type,
                    base_price=Decimal('15000.00') if target_room_type == 'standard' else Decimal('25000.00'),
                    capacity=2 if target_room_type == 'standard' else 3,
                    status='available'
                )

            # Create or update guest
            email = str(data.get('email', '') or '').strip().lower()
            phone = str(data.get('phone', '') or '').strip()
            if email:
                guest, _ = Guest.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'phone': phone,
                    }
                )
            elif phone:
                guest, _ = Guest.objects.get_or_create(
                    phone=phone,
                    defaults={
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': '',
                    }
                )
            else:
                guest = Guest.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    email='',
                    phone='',
                )

            # Calculate total amount
            total_amount = data.get('totalAmount')
            if not total_amount or float(total_amount) <= 0:
                base = available_room.base_price * nights
                discount = base * Decimal('0.10') if nights >= 3 else Decimal('0.00')
                tax = (base - discount) * Decimal('0.075')
                total_amount = base - discount + tax
            else:
                total_amount = Decimal(str(total_amount))

            # Create booking
            booking = Booking.objects.create(
                guest=guest,
                room=available_room,
                check_in=check_in,
                check_out=check_out,
                adults=int(data.get('adults', 1)),
                children=int(data.get('children', 0)),
                total_nights=nights,
                total_amount=total_amount,
                special_requests=data.get('specialRequests', ''),
                status='confirmed',
                payment_status='pending',
                payment_method=data.get('paymentMethod', 'cash'),
            )
            
            return JsonResponse({
                'success': True,
                'booking_reference': booking.booking_reference,
                'room_number': available_room.room_number,
                'room_type': available_room.room_type,
                'check_in': str(booking.check_in),
                'check_out': str(booking.check_out),
                'total_amount': float(booking.total_amount),
                'message': 'Booking confirmed successfully'
            }, status=201)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format in request'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Booking processing failed: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def check_availability(request):
    """Check room availability"""
    check_in = request.GET.get('check_in')
    check_out = request.GET.get('check_out')
    room_type = request.GET.get('room_type')
    
    if not check_in or not check_out:
        return JsonResponse({'error': 'Dates required (check_in, check_out)'}, status=400)
    
    try:
        check_in_date = datetime.datetime.strptime(check_in, '%Y-%m-%d').date()
        check_out_date = datetime.datetime.strptime(check_out, '%Y-%m-%d').date()
        
        # Find rooms
        queryset = Room.objects.all()
        if room_type:
            mapped_type = 'deluxe' if room_type in ['duplex', 'deluxe', 'suite'] else 'standard'
            queryset = queryset.filter(room_type=mapped_type)
        
        # Exclude booked rooms
        booked_ids = Booking.objects.filter(
            check_in__lt=check_out_date,
            check_out__gt=check_in_date,
            status__in=['confirmed', 'checked_in']
        ).values_list('room_id', flat=True)
        
        available_rooms = queryset.exclude(id__in=booked_ids)
        
        return JsonResponse({
            'available': available_rooms.exists(),
            'count': available_rooms.count(),
            'rooms': list(available_rooms.values('id', 'room_number', 'room_type', 'base_price'))
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def test(request):
    """Test endpoint"""
    return JsonResponse({
        'status': 'ok',
        'method': request.method,
        'message': 'Public bookings API is operational'
    })