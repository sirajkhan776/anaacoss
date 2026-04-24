from django.conf import settings
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .auth import clear_auth_cookies, set_auth_cookies
from .models import Address
from .serializers import AddressSerializer, LoginSerializer, RegisterSerializer, UserSerializer


def token_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "user": UserSerializer(user).data,
    }


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        response = Response(token_payload(user), status=status.HTTP_201_CREATED)
        return set_auth_cookies(response, access=response.data["access"], refresh=response.data["refresh"])


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        response = Response(token_payload(user))
        return set_auth_cookies(response, access=response.data["access"], refresh=response.data["refresh"])


class TokenRefreshCookieView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = TokenRefreshSerializer(
            data={"refresh": request.data.get("refresh") or request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)}
        )
        serializer.is_valid(raise_exception=True)
        response = Response(serializer.validated_data)
        return set_auth_cookies(
            response,
            access=serializer.validated_data.get("access"),
            refresh=serializer.validated_data.get("refresh"),
        )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    refresh = request.data.get("refresh") or request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
    if refresh:
        try:
            RefreshToken(refresh).blacklist()
        except Exception:
            pass
    response = Response({"detail": "Logged out."})
    return clear_auth_cookies(response)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if serializer.validated_data.get("is_default"):
            Address.objects.filter(user=self.request.user).update(is_default=False)
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        if serializer.validated_data.get("is_default"):
            Address.objects.filter(user=self.request.user).exclude(pk=serializer.instance.pk).update(is_default=False)
        serializer.save()

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        address = self.get_object()
        Address.objects.filter(user=request.user).exclude(pk=address.pk).update(is_default=False)
        address.is_default = True
        address.save(update_fields=["is_default"])
        return Response(self.get_serializer(address).data, status=status.HTTP_200_OK)
