from datetime import timedelta

from django.utils import timezone

from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import APIRequestLog, SecurityEvent


REQUEST_LIMIT = 30
TIME_WINDOW = timedelta(minutes=1)


class APIRequestLoggingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time
        from django.http import JsonResponse
        from .geo import lookup_country
        from .models import IPBlocklist

        ip_address = self.get_client_ip(request)

        # Enforce IP Blocklist (safeguard: check active blocks)
        if IPBlocklist.objects.filter(ip_address=ip_address, is_active=True).exists():
            return JsonResponse(
                {
                    'error': 'Access denied. Your IP address has been blocked by EduShield security administration.',
                    'blocked_ip': ip_address,
                },
                status=403,
            )

        start_time = time.monotonic()
        response = self.get_response(request)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Only monitor API requests
        if request.path.startswith('/api/'):
            ip_address = self.get_client_ip(request)
            user = self.get_user(request)
            user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:512]
            country = lookup_country(ip_address)
            user_role = getattr(user, 'role', '') if user else ''

            try:
                content_length = int(request.META.get('CONTENT_LENGTH') or 0)
            except (ValueError, TypeError):
                content_length = 0

            APIRequestLog.objects.create(
                user=user,
                ip_address=ip_address,
                endpoint=request.path,
                method=request.method,
                status_code=response.status_code,
                response_time_ms=duration_ms,
                request_size=content_length,
                user_agent=user_agent,
                user_role=user_role,
                country=country,
            )

            self.detect_abnormal_activity(ip_address)

        return response

    def get_user(self, request):
        # Session user first, then the JWT bearer token used by the SPA.
        if request.user.is_authenticated:
            return request.user

        try:
            result = JWTAuthentication().authenticate(request)
        except Exception:
            return None

        return result[0] if result else None

    def get_client_ip(self, request):

        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        if forwarded_for:
            return forwarded_for.split(',')[0].strip()

        return request.META.get('REMOTE_ADDR')

    def detect_abnormal_activity(self, ip_address):

        since = timezone.now() - TIME_WINDOW

        request_count = APIRequestLog.objects.filter(
            ip_address=ip_address,
            created_at__gte=since
        ).count()

        if request_count == REQUEST_LIMIT:

            SecurityEvent.objects.create(
                event_type='abnormal_api',
                severity='MEDIUM',
                description=(
                    f'Abnormal API activity detected. '
                    f'{request_count} requests from {ip_address} '
                    f'within 1 minute.'
                ),
                ip_address=ip_address,
            )