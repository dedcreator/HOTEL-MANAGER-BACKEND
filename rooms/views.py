# rooms/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Room, RoomTypeConfig, RoomSettings
from .serializers import (
    RoomSerializer, RoomStatusSerializer, 
    RoomTypeConfigSerializer, RoomSettingsSerializer
)

def is_manager_or_ceo(user):
    if not user or not user.is_authenticated:
        return False
    role = (getattr(user, 'role', '') or '').upper()
    return role in ['CEO', 'MANAGER', 'ADMIN'] or user.is_staff or user.is_superuser


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all().order_by('room_number')
    serializer_class = RoomSerializer
    
    def perform_destroy(self, instance):
        # Save snapshot for all bookings referencing this room so their records stay 100% intact
        for b in instance.bookings.all():
            if not b.room_number_snapshot:
                b.room_number_snapshot = instance.room_number
            if not b.room_type_snapshot:
                b.room_type_snapshot = instance.room_type
            b.save(update_fields=['room_number_snapshot', 'room_type_snapshot'])
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        room = self.get_object()
        new_status = request.data.get('status')
        
        if new_status in dict(Room.STATUS_CHOICES):
            room.status = new_status
            room.save()
            return Response({'status': 'success', 'new_status': room.status})
        
        return Response(
            {'error': 'Invalid status'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        available_rooms = Room.objects.filter(status='available')
        serializer = self.get_serializer(available_rooms, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get', 'post', 'patch'], url_path='settings', url_name='settings', permission_classes=[IsAuthenticated])
    def room_settings(self, request):
        """Get or update room settings (Manager & CEO)"""
        settings_obj = RoomSettings.get_settings()
        
        if request.method in ['POST', 'PATCH']:
            if not is_manager_or_ceo(request.user):
                return Response({'error': 'Only Managers and CEOs can update room settings'}, status=status.HTTP_403_FORBIDDEN)
            
            serializer = RoomSettingsSerializer(settings_obj, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                
                # If requested to apply default short rest price to all rooms
                if request.data.get('apply_price_to_all_rooms') and 'default_short_rest_price' in request.data:
                    Room.objects.all().update(short_rest_price=request.data['default_short_rest_price'])
                
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # GET response
        types = RoomTypeConfig.objects.all().order_by('name')
        if not types.exists():
            # Seed default room types if none exist
            defaults = [
                {'code': 'standard', 'name': 'Standard Room', 'default_base_price': 15000.00, 'default_short_rest_price': 8000.00, 'capacity': 2},
                {'code': 'deluxe', 'name': 'Deluxe Suite', 'default_base_price': 25000.00, 'default_short_rest_price': 12000.00, 'capacity': 3},
                {'code': 'executive', 'name': 'Executive Suite', 'default_base_price': 35000.00, 'default_short_rest_price': 15000.00, 'capacity': 4},
            ]
            for item in defaults:
                RoomTypeConfig.objects.get_or_create(code=item['code'], defaults=item)
            types = RoomTypeConfig.objects.all().order_by('name')

        rooms = Room.objects.all().order_by('room_number')
        return Response({
            'settings': RoomSettingsSerializer(settings_obj).data,
            'room_types': RoomTypeConfigSerializer(types, many=True).data,
            'total_rooms': rooms.count(),
            'short_rest_rooms_count': rooms.filter(is_short_rest_available=True).count(),
        })

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def bulk_update(self, request):
        """Bulk update room settings like short rest availability, prices, and room types"""
        if not is_manager_or_ceo(request.user):
            return Response({'error': 'Only Managers and CEOs can update room settings'}, status=status.HTTP_403_FORBIDDEN)
        
        room_updates = request.data.get('rooms', [])
        # Also support { room_ids: [...], is_short_rest_available, short_rest_price, base_price, room_type }
        room_ids = request.data.get('room_ids', [])
        
        if room_ids:
            fields_to_update = {}
            if 'is_short_rest_available' in request.data:
                fields_to_update['is_short_rest_available'] = request.data['is_short_rest_available']
            if 'short_rest_price' in request.data and request.data['short_rest_price'] is not None:
                fields_to_update['short_rest_price'] = request.data['short_rest_price']
            if 'base_price' in request.data and request.data['base_price'] is not None:
                fields_to_update['base_price'] = request.data['base_price']
            if 'room_type' in request.data and request.data['room_type']:
                fields_to_update['room_type'] = request.data['room_type']
            
            if fields_to_update:
                Room.objects.filter(id__in=room_ids).update(**fields_to_update)
        
        elif room_updates:
            for item in room_updates:
                room_id = item.get('id')
                if not room_id:
                    continue
                room = Room.objects.filter(id=room_id).first()
                if not room:
                    continue
                if 'is_short_rest_available' in item:
                    room.is_short_rest_available = item['is_short_rest_available']
                if 'short_rest_price' in item and item['short_rest_price'] is not None:
                    room.short_rest_price = item['short_rest_price']
                if 'base_price' in item and item['base_price'] is not None:
                    room.base_price = item['base_price']
                if 'room_type' in item and item['room_type']:
                    room.room_type = item['room_type']
                room.save()
        
        updated_rooms = Room.objects.all().order_by('room_number')
        return Response({
            'message': 'Rooms updated successfully',
            'rooms': RoomSerializer(updated_rooms, many=True).data
        })

    @action(detail=False, methods=['get', 'post', 'delete'], permission_classes=[IsAuthenticated])
    def room_types(self, request):
        """Manage custom room types"""
        if request.method == 'GET':
            types = RoomTypeConfig.objects.all().order_by('name')
            return Response(RoomTypeConfigSerializer(types, many=True).data)
        
        if not is_manager_or_ceo(request.user):
            return Response({'error': 'Only Managers and CEOs can manage room types'}, status=status.HTTP_403_FORBIDDEN)
        
        if request.method == 'POST':
            code = request.data.get('code', '').strip().lower()
            name = request.data.get('name', '').strip()
            if not code or not name:
                return Response({'error': 'Both code and name are required'}, status=status.HTTP_400_BAD_REQUEST)
            
            room_type, created = RoomTypeConfig.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'default_base_price': request.data.get('default_base_price', 15000.00),
                    'default_short_rest_price': request.data.get('default_short_rest_price', 8000.00),
                    'capacity': request.data.get('capacity', 2),
                    'description': request.data.get('description', ''),
                }
            )
            return Response(RoomTypeConfigSerializer(room_type).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
        
        if request.method == 'DELETE':
            type_id = request.data.get('id') or request.query_params.get('id')
            if type_id:
                RoomTypeConfig.objects.filter(id=type_id).delete()
                return Response({'message': 'Room type deleted'})
            return Response({'error': 'ID is required'}, status=status.HTTP_400_BAD_REQUEST)