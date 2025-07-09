from django import forms
from django.contrib.auth.forms import (
    UserCreationForm as DjangoUserCreationForm,
    UserChangeForm as DjangoUserChangeForm,
    AuthenticationForm as DjangoAuthenticationForm,
)
from django.contrib.auth import authenticate
from django.db import transaction # For atomic operations

from .models import User, StudentProfile, SupervisorProfile, CoordinatorProfile
from academics.models import ProgrammePreferenceGroup, Department, School, Semester

# --- User Management Forms ---

class CustomUserCreationForm(DjangoUserCreationForm):
    """
    A form for creating new users. Includes all the required
    fields, plus a repeated password.
    """
    full_name = forms.CharField(max_length=255, required=True, help_text="Required.")
    user_type = forms.ChoiceField(choices=User.USER_TYPE_CHOICES, required=True)

    class Meta(DjangoUserCreationForm.Meta):
        model = User
        fields = ("email", "full_name", "user_type")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.full_name = self.cleaned_data["full_name"]
        user.user_type = self.cleaned_data["user_type"]
        if commit:
            user.save()
        return user

class CustomUserChangeForm(DjangoUserChangeForm):
    """
    A form for updating users. Includes all the fields on
    the user, but replaces the password field with admin's
    password hash display field.
    """
    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = ("email", "full_name", "user_type", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")

class UserLoginForm(DjangoAuthenticationForm):
    """
    Login form using email instead of username.
    """
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={'autofocus': True}))

    def clean(self):
        email = self.cleaned_data.get('username') # 'username' is used by AuthenticationForm
        password = self.cleaned_data.get('password')

        if email is not None and password:
            self.user_cache = authenticate(self.request, email=email, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data

# --- Profile Forms ---

class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = [
            'preference_text',
        ]
        widgets = {
            'preference_text': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class SupervisorProfileForm(forms.ModelForm):
    class Meta:
        model = SupervisorProfile
        fields = [
            'expertise',
            'preferred_programmes_first_choice',
            'preferred_programmes_second_choice',
            'supervision_capacity',
        ]
        widgets = {
            'expertise': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Comma-separated keywords for matching, e.g., "AI", "NLP", "Computer Vision"'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_programmes_first_choice'].queryset = ProgrammePreferenceGroup.objects.all().order_by('name')
        self.fields['preferred_programmes_second_choice'].queryset = ProgrammePreferenceGroup.objects.all().order_by('name')


class CoordinatorProfileForm(forms.ModelForm):
    # This form assumes the SupervisorProfile already exists and is being "promoted"

    class Meta:
        model = CoordinatorProfile
        fields = ['supervisor'] # 'appointed_on' is auto_now_add

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supervisor'].queryset = SupervisorProfile.objects.filter(coordinatorprofile__isnull=True).select_related('user').order_by('user__email')
        self.fields['supervisor'].label_from_instance = lambda obj: f"{obj.user.full_name} ({obj.user.email})"


class CsvImportForm(forms.Form):
    """
    A simple form for uploading a CSV file.
    """
    csv_file = forms.FileField(
        label='Select a CSV file',
        help_text='The file must be in CSV format.',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )