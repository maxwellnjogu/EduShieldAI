from rest_framework import serializers
from .models import SecurityEvent, APIRequestLog


class SecurityEventSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, default=None)

    class Meta:
        model = SecurityEvent
        fields = [
            'id',
            'user',
            'username',
            'user_role',
            'event_type',
            'severity',
            'description',
            'ip_address',
            'country',
            'endpoint',
            'user_agent',
            'created_at',
            'is_resolved',
            'is_informational',
        ]


class APIRequestLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, default=None)

    class Meta:
        model = APIRequestLog
        fields = [
            'id',
            'user',
            'username',
            'user_role',
            'ip_address',
            'country',
            'endpoint',
            'method',
            'status_code',
            'response_time_ms',
            'request_size',
            'user_agent',
            'created_at',
        ]


class IPBlocklistSerializer(serializers.ModelSerializer):
    blocked_by_username = serializers.CharField(source='blocked_by.username', read_only=True, default=None)

    class Meta:
        from .models import IPBlocklist
        model = IPBlocklist
        fields = [
            'id',
            'ip_address',
            'reason',
            'blocked_by',
            'blocked_by_username',
            'is_active',
            'created_at',
            'updated_at',
        ]


class IncidentAuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, default=None)

    class Meta:
        from .models import IncidentAuditLog
        model = IncidentAuditLog
        fields = [
            'id',
            'incident',
            'actor',
            'actor_username',
            'action',
            'details',
            'timestamp',
        ]


class IncidentSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default=None)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True, default=None)
    audit_logs = IncidentAuditLogSerializer(many=True, read_only=True)
    related_events_count = serializers.IntegerField(source='related_events.count', read_only=True)

    class Meta:
        from .models import Incident
        model = Incident
        fields = [
            'id',
            'title',
            'description',
            'status',
            'severity',
            'source_ip',
            'endpoint',
            'analyst_notes',
            'escalation_reason',
            'created_by',
            'created_by_username',
            'assigned_to',
            'assigned_to_username',
            'related_events',
            'related_events_count',
            'audit_logs',
            'created_at',
            'updated_at',
        ]