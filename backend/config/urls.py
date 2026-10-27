from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/auth/', include('users.urls')),
    path('api/tutor/', include('tutor.urls')),
    path('api/knowledge/', include('knowledge.urls')),
    path('api/security/', include('security.urls')),
    path('api/soc/', include('soc.urls')),
    path('api/academic/', include('academic.urls')),
]
urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)