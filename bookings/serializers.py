# backend/bookings/serializers.py
from rest_framework import serializers
from .models import Guest, Booking
from rooms.models import Room
from rooms.serializers import RoomSerializer

class GuestSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    last_name = serializers.CharField(required=False, allow_blank=True, default='')
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    phone = serializers.CharField(required=False, allow_blank=True, default='')
    
    class Meta:
        model = Guest
        fields = ['id', 'first_name', 'last_name', 'full_name', 'email', 'phone', 'id_number', 'address', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name if name else "Guest"

class BookingSerializer(serializers.ModelSerializer):
    guest_details = GuestSerializer(source='guest', read_only=True)
    room_details = RoomSerializer(source='room', read_only=True)
    guest_name = serializers.SerializerMethodField()
    room_number = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ['id', 'booking_reference', 'created_at', 'updated_at', 'checked_in_at', 'checked_out_at']
    
    def get_guest_name(self, obj):
        if obj.guest:
            name = f"{obj.guest.first_name} {obj.guest.last_name}".strip()
            return name if name else "Guest"
        return "Guest"
    
    def get_room_number(self, obj):
        if obj.room:
            return obj.room.room_number
        return obj.room_number_snapshot or "Archived Room"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not data.get('room_details'):
            data['room_details'] = {
                'id': None,
                'room_number': instance.room_number_snapshot or 'Archived Room',
                'room_type': instance.room_type_snapshot or 'standard',
                'base_price': 0,
                'status': 'deleted',
                'is_deleted': True,
            }
        return data


class CreateBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = [
            'guest', 'room', 'check_in', 'check_out', 
            'adults', 'children', 'total_nights', 'total_amount',
            'special_requests', 'status', 'payment_status'
        ]
    
    def create(self, validated_data):
        print("Creating booking with data:", validated_data)  # Debug print
        booking = Booking.objects.create(**validated_data)
        print("Created booking:", booking.id, booking.booking_reference)  # Debug print
        return booking
    
    
class CheckInSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=['cash', 'card', 'transfer'])
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    def validate(self, data):
        if data['payment_method'] == 'cash' and not data.get('amount_paid'):
            raise serializers.ValidationError("Amount paid is required for cash payments")
        return data

class SimpleBookingSerializer(serializers.ModelSerializer):
    guest_name = serializers.CharField(source='guest.__str__', read_only=True)
    room_number = serializers.CharField(source='room.room_number', read_only=True)
    
    class Meta:
        model = Booking
        fields = ['id', 'booking_reference', 'guest_name', 'room_number', 
                  'check_in', 'check_out', 'status', 'total_amount', 'payment_status']