from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from rest_framework import serializers

from .models import Address, Profile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone", "password")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        Profile.objects.create(user=user)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get("username")
        password = attrs.get("password")
        lookup = {}
        if "@" in username:
            lookup["email__iexact"] = username
        else:
            lookup["username__iexact"] = username

        user = User.objects.filter(**lookup).first()
        if not user:
            message = "User does not exist." if "@" in username else "Username is incorrect."
            raise serializers.ValidationError(message)
        if not check_password(password, user.password):
            raise serializers.ValidationError("Password is incorrect.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        authenticated = authenticate(
            request=self.context.get("request"),
            username=user.username,
            password=password,
        )
        attrs["user"] = authenticated or user
        return attrs


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ("avatar", "skin_type", "beauty_goals", "birth_date")


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(required=False)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "phone", "profile")
        read_only_fields = ("id", "username", "email")

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if profile_data:
            profile, _ = Profile.objects.get_or_create(user=instance)
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()
        return instance


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"
        read_only_fields = ("user",)
