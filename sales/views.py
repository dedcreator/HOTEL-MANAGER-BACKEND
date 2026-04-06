# backend/sales/views.py
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q  
from django.utils import timezone
from datetime import timedelta
from .models import Sale, Customer, SavedCart 
from .serializers import (
    SaleSerializer, CreateSaleSerializer, TodaySummarySerializer,
    CustomerSerializer, SavedCartSerializer, CreateSavedCartSerializer
)

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().order_by('-created_at')
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateSaleSerializer
        return SaleSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context
    
    def perform_create(self, serializer):
        serializer.save()  # staff is handled inside CreateSaleSerializer.create()
    
    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get today's sales summary"""
        today = timezone.now().date()
        today_sales = Sale.objects.filter(created_at__date=today)
        
        total_sales = today_sales.aggregate(total=Sum('total_amount'))['total'] or 0
        total_transactions = today_sales.count()
        
        cash_sales = today_sales.filter(payment_method='cash').aggregate(total=Sum('total_amount'))['total'] or 0
        card_sales = today_sales.filter(payment_method='card').aggregate(total=Sum('total_amount'))['total'] or 0
        room_charges = today_sales.filter(payment_method='room_charge').aggregate(total=Sum('total_amount'))['total'] or 0
        
        return Response({
            'summary': {
                'total_sales': float(total_sales),
                'count': total_transactions
            },
            'cash_sales': float(cash_sales),
            'card_sales': float(card_sales),
            'room_charges': float(room_charges),
            'transactions': SaleSerializer(today_sales, many=True).data
        })
    
    @action(detail=False, methods=['get'])
    def revenue_report(self, request):
        """Get revenue report by period"""
        period = request.query_params.get('period', 'weekly')
        
        today = timezone.now().date()
        
        if period == 'weekly':
            report = []
            for i in range(7):
                day = today - timedelta(days=6-i)
                day_sales = Sale.objects.filter(created_at__date=day)
                report.append({
                    'name': day.strftime('%a'),
                    'date': day.isoformat(),
                    'revenue': float(day_sales.aggregate(total=Sum('total_amount'))['total'] or 0),
                    'transactions': day_sales.count()
                })
        else:  # monthly
            report = []
            for i in range(4):
                week_start = today - timedelta(days=28-(i*7))
                week_end = week_start + timedelta(days=6)
                week_sales = Sale.objects.filter(created_at__date__gte=week_start, created_at__date__lte=week_end)
                report.append({
                    'name': f'Week {i+1}',
                    'revenue': float(week_sales.aggregate(total=Sum('total_amount'))['total'] or 0),
                    'transactions': week_sales.count()
                })
        
        return Response(report)

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all().order_by('-created_at')
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = Customer.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search)
            )
        return queryset
    
    @action(detail=True, methods=['post'])
    def add_visit(self, request, pk=None):
        customer = self.get_object()
        customer.total_visits += 1
        customer.last_visit = timezone.now()
        customer.save()
        
        total_spent = Sale.objects.filter(customer=customer).aggregate(total=Sum('total_amount'))['total'] or 0
        customer.total_spent = total_spent
        customer.save()
        
        return Response(CustomerSerializer(customer).data)

class SavedCartViewSet(viewsets.ModelViewSet):
    queryset = SavedCart.objects.filter(is_completed=False).order_by('-created_at')
    serializer_class = SavedCartSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreateSavedCartSerializer
        return SavedCartSerializer
    
    def get_queryset(self):
        queryset = SavedCart.objects.filter(is_completed=False)
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        return queryset
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        cart = self.get_object()
        cart.is_completed = True
        cart.completed_at = timezone.now()
        cart.save()
        return Response({'status': 'cart completed', 'cart_id': cart.id})