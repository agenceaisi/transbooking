from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    TransBookingTokenObtainPairSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
    UserRegistrationSerializer,
)


class UserRegistrationView(GenericAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserProfileSerializer(user).data, status=status.HTTP_201_CREATED)


class TransBookingTokenObtainPairView(TokenObtainPairView):
    serializer_class = TransBookingTokenObtainPairSerializer


class TransBookingTokenRefreshView(TokenRefreshView):
    pass


class LogoutView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"refresh": "Ce champ est obligatoire."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        token = RefreshToken(refresh)
        token.blacklist()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserMeView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserProfileUpdateSerializer
        return UserProfileSerializer

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserProfileSerializer(user).data)
