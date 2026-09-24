# rooms/serializers.py
from rest_framework import serializers
from .models import Room, RoomTypeConfig, RoomSettings

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'

class RoomStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ['id', 'room_number', 'status']

class RoomTypeConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomTypeConfig
        fields = '__all__'

class RoomSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomSettings
        fields = '__all__'