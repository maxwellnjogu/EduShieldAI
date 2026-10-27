from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncHour
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.response import Response
from rest_framework.views import APIView

from security.models import APIRequestLog, SecurityEvent
from security.permissions import IsEduShieldAdmin
from security.serializers import SecurityEventSerializer

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
MAX_BULK_IDS = 500

VALID_SEVERITIES = {value for value, _ in SecurityEvent.SEVERITY_CHOICES}
VALID_EVENT_TYPES = {value for value, _ in SecurityEvent.EVENT_TYPES}


def parse_bool(value, default=True):
    """Strict boolean parsing (bool('false') would otherwise be True)."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ('true', '1', 'yes'):
        return True
    if text in ('false', '0', 'no'):
        return False
    raise ValueError('Invalid boolean value.')


class SocSummaryView(APIView):
    """Aggregated data for the SOC dashboard (last 24 hours)."""
    permission_classes = [IsEduShieldAdmin]

    def get(self, request):
        since = timezone.now() - timedelta(hours=24)
        recent = SecurityEvent.objects.filter(created_at__gte=since)
        # Alerts exclude informational activity-log entries (e.g. tutor questions).
        alerts = recent.filter(is_informational=False)

        timeline = (
            alerts.annotate(hour=TruncHour('created_at'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )

        top_ips = (
            recent.exclude(ip_address__isnull=True)
            .values('ip_address')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        by_severity = {
            row['severity']: row['count']
            for row in alerts.values('severity').annotate(count=Count('id'))
        }
        by_type = {
            row['event_type']: row['count']
            for row in recent.values('event_type').annotate(count=Count('id'))
        }

        top_users = (
            recent.exclude(user__isnull=True)
            .values('user__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        top_endpoints = (
            APIRequestLog.objects.filter(created_at__gte=since)
            .values('endpoint')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        top_roles = (
            recent.exclude(user_role='')
            .values('user_role')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        top_countries = (
            recent.exclude(country='')
            .values('country')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )

        return Response({
            'window_hours': 24,
            'events_last_24h': alerts.count(),
            'informational_last_24h': recent.filter(is_informational=True).count(),
            'open_events': SecurityEvent.objects.filter(
                is_resolved=False, is_informational=False
            ).count(),
            'unresolved_critical': SecurityEvent.objects.filter(
                is_resolved=False,
                is_informational=False,
                severity__in=['HIGH', 'CRITICAL'],
            ).count(),
            'resolved_last_24h': alerts.filter(is_resolved=True).count(),
            'api_requests_last_24h': APIRequestLog.objects.filter(
                created_at__gte=since
            ).count(),
            'by_severity': by_severity,
            'by_type': by_type,
            'timeline': list(timeline),
            'top_ips': list(top_ips),
            'top_users': [
                {'username': r['user__username'], 'count': r['count']}
                for r in top_users
            ],
            'top_endpoints': list(top_endpoints),
            'top_roles': [{'role': r['user_role'], 'count': r['count']} for r in top_roles],
            'top_countries': [{'country': r['country'], 'count': r['count']} for r in top_countries],
        })


class EventListView(APIView):
    """
    Filterable, paginated event list.

    Query params: severity, event_type, is_resolved, ip, user, search,
    since / until (ISO 8601), limit (max 200), offset.
    """
    permission_classes = [IsEduShieldAdmin]

    def get(self, request):
        params = request.query_params
        events = SecurityEvent.objects.select_related('user').order_by('-created_at', '-id')

        severity = params.get('severity')
        if severity:
            severity = severity.upper()
            if severity not in VALID_SEVERITIES:
                return Response({'error': 'Invalid severity.'}, status=400)
            events = events.filter(severity=severity)

        event_type = params.get('event_type')
        if event_type:
            if event_type not in VALID_EVENT_TYPES:
                return Response({'error': 'Invalid event_type.'}, status=400)
            events = events.filter(event_type=event_type)

        if params.get('is_informational') is not None:
            try:
                events = events.filter(
                    is_informational=parse_bool(params.get('is_informational'))
                )
            except ValueError:
                return Response({'error': 'Invalid is_informational.'}, status=400)

        if params.get('is_resolved') is not None:
            # Open/resolved is alert triage, so informational entries are
            # left out unless is_informational was requested explicitly.
            if params.get('is_informational') is None:
                events = events.filter(is_informational=False)
            try:
                events = events.filter(is_resolved=parse_bool(params.get('is_resolved')))
            except ValueError:
                return Response({'error': 'Invalid is_resolved.'}, status=400)

        if params.get('ip'):
            events = events.filter(ip_address=params['ip'])

        if params.get('user'):
            events = events.filter(user__username=params['user'])

        if params.get('user_role'):
            events = events.filter(user_role__iexact=params['user_role'])

        if params.get('country'):
            events = events.filter(country__iexact=params['country'])

        if params.get('endpoint'):
            events = events.filter(endpoint=params['endpoint'])

        search = params.get('search')
        if search:
            events = events.filter(
                Q(description__icontains=search)
                | Q(endpoint__icontains=search)
                | Q(user_agent__icontains=search)
                | Q(country__icontains=search)
                | Q(user__username__icontains=search)
            )

        for key, lookup in (('since', 'created_at__gte'), ('until', 'created_at__lte')):
            raw = params.get(key)
            if raw:
                parsed = parse_datetime(raw)
                if parsed is None:
                    return Response({'error': f'Invalid {key} datetime.'}, status=400)
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed)
                events = events.filter(**{lookup: parsed})

        try:
            limit = int(params.get('limit', DEFAULT_PAGE_SIZE))
            offset = int(params.get('offset', 0))
        except ValueError:
            return Response({'error': 'limit and offset must be integers.'}, status=400)
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        offset = max(0, offset)

        count = events.count()
        page = events[offset:offset + limit]

        return Response({
            'count': count,
            'limit': limit,
            'offset': offset,
            'results': SecurityEventSerializer(page, many=True).data,
        })


class EventDetailView(APIView):
    """Single event including its metadata."""
    permission_classes = [IsEduShieldAdmin]

    def get(self, request, event_id):
        event = get_object_or_404(SecurityEvent, pk=event_id)
        data = SecurityEventSerializer(event).data
        data['metadata'] = event.metadata
        data['username'] = event.user.username if event.user else None
        return Response(data)


class ResolveEventView(APIView):
    """Mark a security event as resolved (or re-open it)."""
    permission_classes = [IsEduShieldAdmin]

    def post(self, request, event_id):
        event = get_object_or_404(SecurityEvent, pk=event_id)
        try:
            event.is_resolved = parse_bool(request.data.get('is_resolved'))
        except ValueError:
            return Response({'error': 'Invalid is_resolved.'}, status=400)
        event.save(update_fields=['is_resolved'])
        return Response(SecurityEventSerializer(event).data)


class BulkResolveView(APIView):
    """Resolve (or re-open) many events at once: {"ids": [...], "is_resolved": true}."""
    permission_classes = [IsEduShieldAdmin]

    def post(self, request):
        ids = request.data.get('ids')
        if (
            not isinstance(ids, list)
            or not ids
            or len(ids) > MAX_BULK_IDS
            or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids)
        ):
            return Response(
                {'error': f'ids must be a list of 1-{MAX_BULK_IDS} integers.'},
                status=400,
            )
        try:
            is_resolved = parse_bool(request.data.get('is_resolved'))
        except ValueError:
            return Response({'error': 'Invalid is_resolved.'}, status=400)

        updated = SecurityEvent.objects.filter(pk__in=ids).update(is_resolved=is_resolved)
        return Response({'updated': updated, 'is_resolved': is_resolved})
