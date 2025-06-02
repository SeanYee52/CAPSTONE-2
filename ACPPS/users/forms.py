from django import forms
from django.contrib.auth.forms import (
    UserCreationForm as DjangoUserCreationForm,
    UserChangeForm as DjangoUserChangeForm,
    AuthenticationForm as DjangoAuthenticationForm,
)
from django.contrib.auth import authenticate
from django.db import transaction # For atomic operations

from .models import User, StudentProfile, SupervisorProfile, CoordinatorProfile, Programme, Department

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
            'programme',
            'preference_text',
            'positive_preferences',
            'negative_preferences',
        ]
        widgets = {
            'preference_text': forms.Textarea(attrs={'rows': 4}),
            'positive_preferences': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., machine learning, web development, data analysis'}),
            'negative_preferences': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., embedded systems, theoretical physics'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['programme'].queryset = Programme.objects.all().order_by('name')


class SupervisorProfileForm(forms.ModelForm):
    class Meta:
        model = SupervisorProfile
        fields = [
            'department',
            'office_number',
            'expertise',
            'preferred_programmes_first_choice',
            'preferred_programmes_second_choice',
            'supervision_capacity',
            'standardised_expertise'
        ]
        widgets = {
            'expertise': forms.Textarea(attrs={'rows': 4}),
            'standardised_expertise': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Comma-separated keywords for matching, e.g., AI, NLP, Computer Vision'}),
            'preferred_programmes_first_choice': forms.CheckboxSelectMultiple,
            'preferred_programmes_second_choice': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.all().order_by('name')
        self.fields['preferred_programmes_first_choice'].queryset = Programme.objects.all().order_by('name')
        self.fields['preferred_programmes_second_choice'].queryset = Programme.objects.all().order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        first_choice = cleaned_data.get('preferred_programmes_first_choice')
        second_choice = cleaned_data.get('preferred_programmes_second_choice')

        if first_choice and second_choice:
            if first_choice.intersection(second_choice):
                raise forms.ValidationError(
                    "A programme cannot be selected as both a first and second choice preference."
                )
        return cleaned_data


class CoordinatorProfileForm(forms.ModelForm):
    # This form assumes the SupervisorProfile already exists and is being "promoted"

    class Meta:
        model = CoordinatorProfile
        fields = ['supervisor', 'role_scope'] # 'appointed_on' is auto_now_add

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supervisor'].queryset = SupervisorProfile.objects.filter(coordinatorprofile__isnull=True).select_related('user').order_by('user__email')
        self.fields['supervisor'].label_from_instance = lambda obj: f"{obj.user.full_name} ({obj.user.email})"


# --- Combined Registration Forms ---

class StudentRegistrationForm(forms.Form):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=255, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Password")

    programme = forms.ModelChoiceField(queryset=Programme.objects.all().order_by('name'), required=True)
    # Add other StudentProfile fields if needed at registration

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_confirm_password(self):
        password = self.cleaned_data.get('password')
        confirm_password = self.cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return confirm_password

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            full_name=self.cleaned_data['full_name'],
            user_type='student'
        )
        StudentProfile.objects.create(
            user=user,
            programme=self.cleaned_data['programme'],
            graduation_year=self.cleaned_data['graduation_year']
            # Add other fields if collected
        )
        return user


class SupervisorRegistrationForm(forms.Form):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=255, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirm Password")

    department = forms.ModelChoiceField(queryset=Department.objects.all().order_by('name'), required=True)
    office_number = forms.CharField(max_length=20, required=True)
    supervision_capacity = forms.IntegerField(min_value=0, initial=0, required=False) # Optional at registration
    expertise = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False) # Optional at registration

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_confirm_password(self):
        password = self.cleaned_data.get('password')
        confirm_password = self.cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return confirm_password

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            full_name=self.cleaned_data['full_name'],
            user_type='supervisor'
        )
        SupervisorProfile.objects.create(
            user=user,
            department=self.cleaned_data['department'],
            office_number=self.cleaned_data['office_number'],
            supervision_capacity=self.cleaned_data.get('supervision_capacity', 0),
            expertise=self.cleaned_data.get('expertise', '')
        )
        return user