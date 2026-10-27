from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from security.services import create_security_event, detect_brute_force

from .serializers import RegisterSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "role": request.user.role,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
        })


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    def validate(self, attrs):
        try:
            return super().validate(attrs)

        except Exception:
            request = self.context.get('request')
            ip_address = request.META.get('REMOTE_ADDR') if request else None

            attempted_username = str(attrs.get('username', ''))[:150]
            target_role = ''
            if attempted_username:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                matched_user = User.objects.filter(username=attempted_username).first()
                if matched_user:
                    target_role = getattr(matched_user, 'role', '') or ''

            create_security_event(
                event_type='suspicious_login',
                severity='LOW',
                description=f'Failed login attempt for user "{attempted_username}".' if attempted_username else 'Failed login attempt.',
                request=request,
                ip_address=ip_address,
                endpoint=request.path if request else None,
                user_role=target_role,
                metadata={'username': attempted_username},
            )

            detect_brute_force(ip_address)

            raise


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer