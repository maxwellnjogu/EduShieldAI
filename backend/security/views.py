from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count
from .permissions import IsEduShieldAdmin

from .models import SecurityEvent, APIRequestLog
from .serializers import SecurityEventSerializer


class SecurityEventListView(APIView):
    permission_classes = [IsEduShieldAdmin]

    def get(self, request):
        events = SecurityEvent.objects.all().order_by('-created_at')

        serializer = SecurityEventSerializer(
            events,
            many=True
        )

        return Response(serializer.data)


class APIRequestLogListView(APIView):
    permission_classes = [IsEduShieldAdmin]

    def get(self, request):
        logs = APIRequestLog.objects.select_related('user').order_by('-created_at')[:100]
        from .serializers import APIRequestLogSerializer
        return Response(APIRequestLogSerializer(logs, many=True).data)

class SecurityStatsView(APIView):
    permission_classes = [IsEduShieldAdmin]

    def get(self, request):
        # Alert stats exclude informational activity-log events (tutor questions).
        alerts = SecurityEvent.objects.filter(is_informational=False)

        total_events = alerts.count()

        critical_events = alerts.filter(
            severity='CRITICAL'
        ).count()

        high_events = alerts.filter(
            severity='HIGH'
        ).count()

        medium_events = alerts.filter(
            severity='MEDIUM'
        ).count()

        low_events = alerts.filter(
            severity='LOW'
        ).count()

        prompt_injections = alerts.filter(
            event_type='prompt_injection'
        ).count()

        suspicious_logins = alerts.filter(
            event_type='suspicious_login'
        ).count()

        malicious_uploads = alerts.filter(
            event_type='malicious_upload'
        ).count()

        abnormal_api = alerts.filter(
            event_type='abnormal_api'
        ).count()

        return Response({
            'total_events': total_events,
            'severity': {
                'critical': critical_events,
                'high': high_events,
                'medium': medium_events,
                'low': low_events,
            },
            'threats': {
                'prompt_injection': prompt_injections,
                'suspicious_login': suspicious_logins,
                'malicious_upload': malicious_uploads,
                'abnormal_api': abnormal_api,
            }
        })


class FlagEventView(APIView):
    """
    POST /api/security/events/<id>/flag/
    Flags an event, adds an analyst note, and optionally creates or links an incident without blocking the IP.
    """
    permission_classes = [IsEduShieldAdmin]

    def post(self, request, event_id):
        from django.shortcuts import get_object_or_404
        from .models import SecurityEvent, Incident, IncidentAuditLog
        from .serializers import SecurityEventSerializer, IncidentSerializer

        event = get_object_or_404(SecurityEvent, pk=event_id)
        note = (request.data.get('note') or '').strip()
        create_incident = bool(request.data.get('create_incident', True))

        if not note:
            return Response({'error': 'Analyst note is required to flag an event.'}, status=400)

        # Update event metadata with flag details
        event.metadata = event.metadata or {}
        event.metadata['flagged'] = True
        event.metadata['flagged_by'] = request.user.username
        notes = event.metadata.get('analyst_notes', [])
        notes.append({
            'by': request.user.username,
            'note': note,
        })
        event.metadata['analyst_notes'] = notes
        event.save(update_fields=['metadata'])

        incident = None
        if create_incident:
            incident = Incident.objects.create(
                title=f"Flagged {event.get_event_type_display()}: {event.description[:80]}",
                description=event.description,
                status='INVESTIGATING',
                severity=event.severity if event.severity in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] else 'MEDIUM',
                source_ip=event.ip_address,
                endpoint=event.endpoint,
                analyst_notes=f"[{request.user.username}] {note}",
                created_by=request.user,
            )
            incident.related_events.add(event)

            IncidentAuditLog.objects.create(
                incident=incident,
                actor=request.user,
                action='FLAG_AND_OPEN',
                details=f"Created incident from Event #{event.id}. Note: {note}",
            )

        return Response({
            'message': f'Event #{event.id} flagged successfully.',
            'event': SecurityEventSerializer(event).data,
            'incident': IncidentSerializer(incident).data if incident else None,
        })


class IPBlocklistView(APIView):
    """
    GET  /api/security/ip-blocks/
    POST /api/security/ip-blocks/
    Enforces safeguards against self-blocking and allows admins to block an IP.
    """
    permission_classes = [IsEduShieldAdmin]

    def get(self, request):
        from .models import IPBlocklist
        from .serializers import IPBlocklistSerializer

        blocks = IPBlocklist.objects.select_related('blocked_by').order_by('-created_at')
        return Response(IPBlocklistSerializer(blocks, many=True).data)

    def post(self, request):
        from .models import IPBlocklist, Incident, IncidentAuditLog
        from .serializers import IPBlocklistSerializer

        ip = (request.data.get('ip_address') or '').strip()
        reason = (request.data.get('reason') or '').strip()
        incident_id = request.data.get('incident_id')

        if not ip:
            return Response({'error': 'ip_address is required.'}, status=400)
        if not reason:
            return Response({'error': 'Reason is required for blocking an IP.'}, status=400)

        # Safeguard: Do not block the admin's current connection IP
        client_ip = request.META.get('REMOTE_ADDR')
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded:
            client_ip = forwarded.split(',')[0].strip()

        if ip == client_ip:
            return Response(
                {'error': f'Safety block prevented: you cannot block your own current IP ({client_ip}).'},
                status=400,
            )

        block, created = IPBlocklist.objects.get_or_create(
            ip_address=ip,
            defaults={
                'reason': reason,
                'blocked_by': request.user,
                'is_active': True,
            },
        )
        if not created and not block.is_active:
            block.is_active = True
            block.reason = reason
            block.blocked_by = request.user
            block.save()

        # If linked to an incident, update its status to CONTAINED and log audit trail
        if incident_id:
            try:
                incident = Incident.objects.get(pk=incident_id)
                incident.status = 'CONTAINED'
                incident.analyst_notes = (
                    f"{incident.analyst_notes}\n[Contained by {request.user.username}]: Blocked IP {ip}. Reason: {reason}"
                ).strip()
                incident.save()
                IncidentAuditLog.objects.create(
                    incident=incident,
                    actor=request.user,
                    action='IP_BLOCKED',
                    details=f"Blocked IP {ip}. Reason: {reason}",
                )
            except Incident.DoesNotExist:
                pass

        return Response(IPBlocklistSerializer(block).data, status=201 if created else 200)


class IPBlockDetailView(APIView):
    """
    DELETE /api/security/ip-blocks/<id>/
    Unblocks an IP address (sets is_active=False or removes).
    """
    permission_classes = [IsEduShieldAdmin]

    def delete(self, request, pk):
        from django.shortcuts import get_object_or_404
        from .models import IPBlocklist, IncidentAuditLog
        from .serializers import IPBlocklistSerializer

        block = get_object_or_404(IPBlocklist, pk=pk)
        ip = block.ip_address
        block.is_active = False
        block.save()

        return Response({'message': f'IP {ip} has been unblocked.', 'block': IPBlocklistSerializer(block).data})


class IncidentListCreateView(APIView):
    """
    GET  /api/security/incidents/
    POST /api/security/incidents/
    """
    permission_classes = [IsEduShieldAdmin]

    def get(self, request):
        from .models import Incident
        from .serializers import IncidentSerializer

        incidents = (
            Incident.objects.select_related('created_by', 'assigned_to')
            .prefetch_related('related_events', 'audit_logs__actor')
            .order_by('-created_at')
        )

        status_param = request.query_params.get('status')
        if status_param:
            incidents = incidents.filter(status=status_param.upper())

        return Response(IncidentSerializer(incidents, many=True).data)

    def post(self, request):
        from .models import Incident, IncidentAuditLog, SecurityEvent
        from .serializers import IncidentSerializer

        title = (request.data.get('title') or '').strip()
        description = (request.data.get('description') or '').strip()
        severity = (request.data.get('severity') or 'MEDIUM').upper()
        source_ip = request.data.get('source_ip')
        endpoint = request.data.get('endpoint')
        notes = (request.data.get('analyst_notes') or '').strip()
        event_ids = request.data.get('event_ids') or []

        if not title:
            return Response({'error': 'Title is required.'}, status=400)

        incident = Incident.objects.create(
            title=title,
            description=description,
            severity=severity if severity in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] else 'MEDIUM',
            source_ip=source_ip,
            endpoint=endpoint,
            analyst_notes=f"[{request.user.username}] {notes}" if notes else '',
            created_by=request.user,
            status='NEW',
        )

        if event_ids:
            events = SecurityEvent.objects.filter(pk__in=event_ids)
            incident.related_events.set(events)

        IncidentAuditLog.objects.create(
            incident=incident,
            actor=request.user,
            action='CREATE_INCIDENT',
            details=f"Incident opened with title: {title}",
        )

        return Response(IncidentSerializer(incident).data, status=201)


class IncidentDetailView(APIView):
    """
    GET /api/security/incidents/<id>/
    """
    permission_classes = [IsEduShieldAdmin]

    def get(self, request, pk):
        from django.shortcuts import get_object_or_404
        from .models import Incident
        from .serializers import IncidentSerializer

        incident = get_object_or_404(
            Incident.objects.select_related('created_by', 'assigned_to').prefetch_related('related_events', 'audit_logs__actor'),
            pk=pk,
        )
        return Response(IncidentSerializer(incident).data)


class IncidentEscalateView(APIView):
    """
    POST /api/security/incidents/<id>/escalate/
    Escalates an incident to Level 2 with mandatory reason.
    """
    permission_classes = [IsEduShieldAdmin]

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        from .models import Incident, IncidentAuditLog
        from .serializers import IncidentSerializer

        incident = get_object_or_404(Incident, pk=pk)
        reason = (request.data.get('reason') or '').strip()

        if not reason:
            return Response({'error': 'Escalation reason is required to escalate to Level 2.'}, status=400)

        incident.status = 'ESCALATED_L2'
        incident.escalation_reason = reason
        incident.analyst_notes = (
            f"{incident.analyst_notes}\n[Escalated to L2 by {request.user.username}]: {reason}"
        ).strip()
        incident.save()

        IncidentAuditLog.objects.create(
            incident=incident,
            actor=request.user,
            action='ESCALATE_L2',
            details=f"Escalated to Level 2. Reason: {reason}",
        )

        return Response(IncidentSerializer(incident).data)


class IncidentResolveView(APIView):
    """
    POST /api/security/incidents/<id>/resolve/
    Resolves an incident with resolution summary notes.
    """
    permission_classes = [IsEduShieldAdmin]

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        from .models import Incident, IncidentAuditLog
        from .serializers import IncidentSerializer

        incident = get_object_or_404(Incident, pk=pk)
        resolution_notes = (request.data.get('resolution_notes') or '').strip()

        incident.status = 'RESOLVED'
        if resolution_notes:
            incident.analyst_notes = (
                f"{incident.analyst_notes}\n[Resolved by {request.user.username}]: {resolution_notes}"
            ).strip()
        incident.save()

        # Mark all related security events as resolved
        incident.related_events.update(is_resolved=True)

        IncidentAuditLog.objects.create(
            incident=incident,
            actor=request.user,
            action='RESOLVE_INCIDENT',
            details=f"Incident resolved. Notes: {resolution_notes or 'No notes provided'}",
        )

        return Response(IncidentSerializer(incident).data)