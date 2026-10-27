"""IP geo-location helpers.

Private/loopback addresses are labelled "Local network". Public addresses are
resolved offline from a MaxMind GeoLite2-Country (or City) database when both
are available:

* the optional ``geoip2`` package is installed, and
* ``GEOIP_DB_PATH`` is set in Django settings or the environment.

Otherwise the country is left blank, so the SOC shows "unknown" instead of a
guess. No network calls are ever made, and no IP is sent to a third party.
"""
import ipaddress
import os
from functools import lru_cache

from django.conf import settings

LOCAL_LABEL = 'Local network'


@lru_cache(maxsize=1)
def _reader():
    path = getattr(settings, 'GEOIP_DB_PATH', None) or os.environ.get('GEOIP_DB_PATH')
    if not path or not os.path.exists(path):
        return None
    try:
        import geoip2.database
        return geoip2.database.Reader(path)
    except Exception:
        return None


@lru_cache(maxsize=2048)
def lookup_country(ip_address):
    """Return a country name, LOCAL_LABEL for private IPs, or '' if unknown."""
    if not ip_address:
        return ''
    try:
        ip = ipaddress.ip_address(ip_address)
    except ValueError:
        return ''

    if ip.is_private or ip.is_loopback or ip.is_link_local:
        return LOCAL_LABEL

    reader = _reader()
    if reader is None:
        return ''
    try:
        # Country DBs expose .country(); City DBs expose both.
        response = reader.country(ip_address)
        return (response.country.name or '')[:64]
    except Exception:
        return ''
