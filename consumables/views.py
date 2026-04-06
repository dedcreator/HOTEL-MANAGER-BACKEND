# backend/consumables/views.py
from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .models import ExpenseCategory, Expense, ExpenseAttachment
from .serializers import (
    ExpenseCategorySerializer, ExpenseSerializer, 
    ExpenseCreateSerializer, ExpenseUpdateSerializer,
    ExpenseAttachmentSerializer
)

class IsManagerOrCEO(permissions.BasePermission):
    """Allow access only to managers and CEO (case-insensitive)"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # Convert role to uppercase for comparison
        role = request.user.role.upper() if request.user.role else ''
        return role in ['MANAGER', 'CEO']

class IsCEO(permissions.BasePermission):
    """Allow access only to CEO (case-insensitive)"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        role = request.user.role.upper() if request.user.role else ''
        return role == 'CEO'

class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all().order_by('name')
    serializer_class = ExpenseCategorySerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrCEO]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.all().order_by('-expense_date', '-created_at')
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrCEO]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'receipt_number', 'notes']
    ordering_fields = ['expense_date', 'amount', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ExpenseCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ExpenseUpdateSerializer
        return ExpenseSerializer
    
    def get_permissions(self):
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), IsCEO()]
        return [permissions.IsAuthenticated(), IsManagerOrCEO()]
    
    def get_queryset(self):
        queryset = Expense.objects.all()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(expense_date__gte=start_date, expense_date__lte=end_date)
        elif start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        elif end_date:
            queryset = queryset.filter(expense_date__lte=end_date)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category_id=category)
        
        # Filter by date range (last 30 days, etc.)
        period = self.request.query_params.get('period')
        if period == 'today':
            queryset = queryset.filter(expense_date=timezone.now().date())
        elif period == 'week':
            week_ago = timezone.now().date() - timedelta(days=7)
            queryset = queryset.filter(expense_date__gte=week_ago)
        elif period == 'month':
            month_ago = timezone.now().date() - timedelta(days=30)
            queryset = queryset.filter(expense_date__gte=month_ago)
        elif period == 'year':
            year_ago = timezone.now().date() - timedelta(days=365)
            queryset = queryset.filter(expense_date__gte=year_ago)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get expense summary statistics"""
        # Get date range (default: last 30 days)
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now().date() - timedelta(days=days)
        
        # Total expenses (last 30 days)
        total_expenses = Expense.objects.filter(
            expense_date__gte=start_date
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        # Expense count (last 30 days)
        expense_count = Expense.objects.filter(
            expense_date__gte=start_date
        ).count()
        
        # Expenses by category (last 30 days)
        by_category = Expense.objects.filter(
            expense_date__gte=start_date
        ).values(
            'category__name', 'category__id'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        # Convert Decimal to float for JSON serialization
        category_list = []
        for item in by_category:
            category_list.append({
                'category': item['category__id'],
                'category_name': item['category__name'],
                'total': float(item['total']) if item['total'] else 0,
                'count': item['count']
            })
        
        # Expenses by month (last 6 months)
        six_months_ago = timezone.now().date() - timedelta(days=180)
        expenses = Expense.objects.filter(expense_date__gte=six_months_ago).order_by('expense_date')
        
        by_month_dict = {}
        for expense in expenses:
            month_key = expense.expense_date.strftime('%Y-%m')
            month_name = expense.expense_date.strftime('%B %Y')
            if month_key not in by_month_dict:
                by_month_dict[month_key] = {
                    'month': month_key,
                    'month_name': month_name,
                    'total': 0,
                    'count': 0
                }
            by_month_dict[month_key]['total'] += float(expense.amount)
            by_month_dict[month_key]['count'] += 1
        
        by_month_list = sorted(by_month_dict.values(), key=lambda x: x['month'])
        
        # Get this month's total
        today = timezone.now().date()
        this_month_start = today.replace(day=1)
        this_month_total = Expense.objects.filter(
            expense_date__gte=this_month_start
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return Response({
            'total_expenses': float(total_expenses),
            'expense_count': expense_count,
            'this_month_total': float(this_month_total),
            'by_category': category_list,
            'by_month': by_month_list,
        })
    
    @action(detail=False, methods=['get'])
    def my_expenses(self, request):
        """Get expenses created by the current user"""
        expenses = self.queryset.filter(created_by=request.user)
        serializer = self.get_serializer(expenses, many=True)
        return Response(serializer.data)

class ExpenseAttachmentViewSet(viewsets.ModelViewSet):
    queryset = ExpenseAttachment.objects.all()
    serializer_class = ExpenseAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsManagerOrCEO]
    
    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)