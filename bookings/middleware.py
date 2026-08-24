# backend/bookings/middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser

class PublicBypassMiddleware(MiddlewareMixin):
    """
    Completely bypass authentication for public endpoints (bookings, menu, tables, orders)
    """
    def process_request(self, request):
        public_prefixes = (
            '/api/bookings/public/',
            '/api/menu/public/',
            '/api/tables/public/',
        )
        if any(request.path.startswith(prefix) for prefix in public_prefixes):
            request._dont_enforce_csrf_checks = True
            if not hasattr(request, 'user') or not request.user or not request.user.is_authenticated:
                request.user = AnonymousUser()
            if 'HTTP_AUTHORIZATION' in request.META and not request.META.get('HTTP_AUTHORIZATION'):
                del request.META['HTTP_AUTHORIZATION']
        return None