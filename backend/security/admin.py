from django.contrib import admin

from .models import SecurityEvent, APIRequestLog


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'severity', 'ip_address', 'is_resolved', 'created_at')
    list_filter = ('severity', 'event_type', 'is_resolved')


@admin.register(APIRequestLog)
class APIRequestLogAdmin(admin.ModelAdmin):
    list_display = ('method', 'endpoint', 'ip_address', 'created_at')
