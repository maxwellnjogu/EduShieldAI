from django.db import models
from django.conf import settings


class SecurityEvent(models.Model):

    SEVERITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]

    EVENT_TYPES = (
    ('prompt_injection', 'Prompt Injection'),
    ('suspicious_login', 'Suspicious Login'),
    ('successful_login', 'Successful Login'),
    ('malicious_upload', 'Malicious Upload'),
    ('abnormal_api', 'Abnormal API Activity'),
    ('unauthorized_access', 'Unauthorized Access'),
    ('tutor_question', 'Tutor Question'),
    ('other', 'Other'),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPES
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES
    )

    description = models.TextField()

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    endpoint = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    metadata = models.JSONField(
        default=dict,
        blank=True
    )

    is_resolved = models.BooleanField(default=False)

    # Activity-log entries (e.g. tutor questions): not alerts, never triaged,
    # excluded from open/resolved counts and the alert stats.
    is_informational = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    # Context, enriched automatically in save()
    user_agent = models.CharField(max_length=512, blank=True, default='')
    user_role = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=64, blank=True, default='')

    def save(self, *args, **kwargs):
        from .geo import lookup_country

        if not self.country and self.ip_address:
            self.country = lookup_country(self.ip_address)
        if not self.user_role and self.user_id:
            self.user_role = getattr(self.user, 'role', '') or ''
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.event_type} - {self.severity}"


class APIRequestLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)

    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    request_size = models.PositiveIntegerField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default='')
    user_role = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=64, blank=True, default='')

    def __str__(self):
        return f"{self.method} {self.endpoint}"


class IPBlocklist(models.Model):
    ip_address = models.GenericIPAddressField(unique=True)
    reason = models.TextField(blank=True, default='')
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blocked_ips',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ip_address} (Active: {self.is_active})"


class Incident(models.Model):
    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('INVESTIGATING', 'Investigating'),
        ('ESCALATED_L2', 'Escalated – L2'),
        ('CONTAINED', 'Contained'),
        ('RESOLVED', 'Resolved'),
    ]

    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NEW')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM')
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    endpoint = models.CharField(max_length=255, null=True, blank=True)
    analyst_notes = models.TextField(blank=True, default='')
    escalation_reason = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_incidents',
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_incidents',
    )
    related_events = models.ManyToManyField(SecurityEvent, blank=True, related_name='incidents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Incident #{self.id}: {self.title} [{self.status}]"


class IncidentAuditLog(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='audit_logs')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incident_actions',
    )
    action = models.CharField(max_length=100)
    details = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} on Incident #{self.incident_id} by {self.actor}"