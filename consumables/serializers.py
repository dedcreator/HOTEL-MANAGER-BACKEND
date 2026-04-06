# backend/consumables/serializers.py
from rest_framework import serializers
from django.db import models 
from .models import ExpenseCategory, Expense, ExpenseAttachment

class ExpenseCategorySerializer(serializers.ModelSerializer):
    expense_count = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = ExpenseCategory
        fields = '__all__'
    
    def get_expense_count(self, obj):
        return obj.expenses.count()
    
    def get_total_amount(self, obj):
        total = obj.expenses.aggregate(total=models.Sum('amount'))['total']
        return float(total) if total else 0

class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    
    class Meta:
        model = Expense
        fields = '__all__'
        read_only_fields = ['expense_number', 'created_at', 'updated_at', 'created_by', 'updated_by']
    
    def get_can_edit(self, obj):
        request = self.context.get('request')
        if request and request.user:
            # Managers and CEO can edit (using uppercase)
            return request.user.role in ['MANAGER', 'CEO']
        return False
    
    def get_can_delete(self, obj):
        request = self.context.get('request')
        if request and request.user:
            # Only CEO can delete
            return request.user.role == 'CEO'
        return False

class ExpenseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'category', 'description', 'amount', 'payment_method',
            'expense_date', 'receipt_number', 'notes',
            'is_recurring', 'recurring_frequency'
        ]
    
    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['created_by'] = request.user
        validated_data['updated_by'] = request.user
        return super().create(validated_data)

class ExpenseUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'category', 'description', 'amount', 'payment_method',
            'expense_date', 'receipt_number', 'notes',
            'is_recurring', 'recurring_frequency'
        ]
    
    def update(self, instance, validated_data):
        request = self.context.get('request')
        validated_data['updated_by'] = request.user
        return super().update(instance, validated_data)

class ExpenseAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    
    class Meta:
        model = ExpenseAttachment
        fields = '__all__'