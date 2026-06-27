from django import forms
from django.contrib.auth import get_user_model

from .models import Profile, ShoppingProfile, User

AuthUser = get_user_model()


class CosmeticProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("skin_type", "skin_tone", "skin_concern", "hair_type", "hair_concern")
        widgets = {
            "skin_type": forms.Select(
                choices=[
                    ("", "Select skin type"),
                    ("Dry", "Dry"),
                    ("Oily", "Oily"),
                    ("Combination", "Combination"),
                    ("Normal", "Normal"),
                    ("Sensitive", "Sensitive"),
                ],
                attrs={"class": "lux-input"},
            ),
            "skin_tone": forms.Select(
                choices=[
                    ("", "Select skin tone"),
                    ("Fair", "Fair"),
                    ("Light", "Light"),
                    ("Medium", "Medium"),
                    ("Tan", "Tan"),
                    ("Deep", "Deep"),
                ],
                attrs={"class": "lux-input"},
            ),
            "skin_concern": forms.Select(
                choices=[
                    ("", "Select skin concern"),
                    ("Acne", "Acne"),
                    ("Dryness", "Dryness"),
                    ("Pigmentation", "Pigmentation"),
                    ("Dullness", "Dullness"),
                    ("Sensitivity", "Sensitivity"),
                    ("Aging", "Aging"),
                ],
                attrs={"class": "lux-input"},
            ),
            "hair_type": forms.Select(
                choices=[
                    ("", "Select hair type"),
                    ("Straight", "Straight"),
                    ("Wavy", "Wavy"),
                    ("Curly", "Curly"),
                    ("Coily", "Coily"),
                    ("Fine", "Fine"),
                    ("Thick", "Thick"),
                ],
                attrs={"class": "lux-input"},
            ),
            "hair_concern": forms.Select(
                choices=[
                    ("", "Select hair concern"),
                    ("Hair Fall", "Hair Fall"),
                    ("Dry Scalp", "Dry Scalp"),
                    ("Frizz", "Frizz"),
                    ("Damage", "Damage"),
                    ("Dandruff", "Dandruff"),
                    ("Split Ends", "Split Ends"),
                ],
                attrs={"class": "lux-input"},
            ),
        }


class NotificationSettingsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("notifications_enabled",)


class AccountDetailsForm(forms.ModelForm):
    avatar = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "lux-input", "placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"class": "lux-input", "placeholder": "Last name"}),
            "phone": forms.TextInput(attrs={"class": "lux-input", "placeholder": "Phone number"}),
            "email": forms.EmailInput(attrs={"class": "lux-input", "placeholder": "Email"}),
        }


class ShoppingProfileForm(forms.ModelForm):
    class Meta:
        model = ShoppingProfile
        fields = ("first_name", "last_name", "avatar")
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "lux-input", "placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"class": "lux-input", "placeholder": "Last name"}),
        }


class SuperAdminRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "vTextField",
                "placeholder": "Create a strong password",
                "autocomplete": "new-password",
            }
        ),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(
            attrs={
                "class": "vTextField",
                "placeholder": "Repeat the password",
                "autocomplete": "new-password",
            }
        ),
    )

    class Meta:
        model = AuthUser
        fields = ("username", "email", "first_name", "last_name")
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "vTextField",
                    "placeholder": "Choose a username",
                    "autocomplete": "username",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "vTextField",
                    "placeholder": "name@example.com",
                    "autocomplete": "email",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "vTextField",
                    "placeholder": "First name",
                    "autocomplete": "given-name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "vTextField",
                    "placeholder": "Last name",
                    "autocomplete": "family-name",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password1") != cleaned_data.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        user.is_superuser = True
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class SuperAdminPasswordChangeForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=AuthUser.objects.filter(is_superuser=True).order_by("username"),
        label="Superadmin",
    )
    password1 = forms.CharField(label="New password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm new password", widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password1") != cleaned_data.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        return cleaned_data

    def save(self):
        user = self.cleaned_data["user"]
        user.set_password(self.cleaned_data["password1"])
        user.save(update_fields=["password"])
        return user
