from django import forms

from .models import Profile, ShoppingProfile, User


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
