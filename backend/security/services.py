from datetime import timedelta

from django.utils import timezone

from .models import SecurityEvent


MAX_FAILED_ATTEMPTS = 5
TIME_WINDOW = timedelta(minutes=5)


def create_security_event(
    event_type,
    severity,
    description,
    user=None,
    ip_address=None,
    endpoint=None,
    metadata=None,
    is_informational=False,
    request=None,
    user_agent=None,
    user_role=None,
    country=None,
):
    if request:
        if not ip_address:
            forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            ip_address = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR')
        if not endpoint:
            endpoint = request.path
        if not user and getattr(request, 'user', None) and request.user.is_authenticated:
            user = request.user
        if not user_agent:
            user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:512]

    if user and not user_role:
        user_role = getattr(user, 'role', '') or ''

    return SecurityEvent.objects.create(
        event_type=event_type,
        severity=severity,
        description=description,
        user=user,
        ip_address=ip_address,
        endpoint=endpoint,
        metadata=metadata or {},
        is_informational=is_informational,
        user_agent=user_agent or '',
        user_role=user_role or '',
        country=country or '',
    )


def detect_brute_force(ip_address):
    """
    Raise a HIGH severity event once an IP has accumulated
    MAX_FAILED_ATTEMPTS failed logins inside TIME_WINDOW.
    Returns True when an alert is (or was already) raised.
    """
    since = timezone.now() - TIME_WINDOW

    recent = SecurityEvent.objects.filter(
        event_type='suspicious_login',
        ip_address=ip_address,
        created_at__gte=since,
    )

    if recent.filter(severity='HIGH').exists():
        return True

    failed_attempts = recent.filter(severity='LOW').count()

    if failed_attempts >= MAX_FAILED_ATTEMPTS:
        create_security_event(
            event_type='suspicious_login',
            severity='HIGH',
            description=(
                f'Possible brute-force attack detected. '
                f'{failed_attempts} failed login attempts '
                f'from {ip_address} within 5 minutes.'
            ),
            ip_address=ip_address,
        )
        return True

    return False