from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from academics.models import Programme, Department, School, ProgrammePreferenceGroup, Semester
from api.models import StandardisedTopic
import re


def get_default_semester():
    try:
        # .latest() is a convenient shortcut that uses get_latest_by from Meta
        latest_session = Semester.objects.latest()
        return latest_session.pk
    except Semester.DoesNotExist:
        # If no sessions exist, new Programmes can't have a default.
        # Returning None makes the field empty, which requires it to be nullable.
        return None

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    full_name = models.CharField(max_length=255, blank=False, null=False)

    USER_TYPE_CHOICES = (
        ('student', 'Student'),
        ('supervisor', 'Supervisor'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['user_type']

    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return self.full_name or self.email

class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    programme = models.ForeignKey(Programme, on_delete=models.SET_NULL, null=True, related_name='students')
    preference_text = models.TextField(blank=True, null=True)
    positive_preferences = models.ManyToManyField(StandardisedTopic, blank=True, related_name='positive_preferences_students')
    negative_preferences = models.ManyToManyField(StandardisedTopic, blank=True, related_name='negative_preferences_students')
    supervisor = models.ForeignKey('SupervisorProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    semester = models.ForeignKey(
        Semester,
        on_delete=models.PROTECT, # Don't delete a semester if programmes are linked to it
        default=get_default_semester(), 
        null=True, 
        blank=True,
        related_name='students'
    )
    programme_match_type = models.IntegerField(null=True)
    matching_topics = models.ManyToManyField(StandardisedTopic, blank=True, related_name='matching_students')
    conflicting_topics = models.ManyToManyField(StandardisedTopic, blank=True, related_name='conflicting_students')

    PREFERENCE_MAX_LENGTH = 4093
    
    def __str__(self):
        return f"{self.user.email} - Student"
    
    def clean(self):
        super().clean()
        if self.preference_text:
            if len(self.preference_text) > self.PREFERENCE_MAX_LENGTH:
                raise ValidationError({
                    'preference_text': "The preference text cannot exceed 4093 characters."
                })

    @property
    def department(self):
        return self.programme.department if self.programme else None

    @property
    def school(self):
        return self.programme.department.school if self.programme else None
    
    @property
    def student_id(self):
        return self.user.email.split('@')[0] if self.user.email else None

class SupervisorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='supervisors', blank=True)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, related_name='supervisors', blank=True)
    expertise = models.TextField(blank=True, null=True)
    preferred_programmes_first_choice = models.ForeignKey(ProgrammePreferenceGroup, on_delete=models.SET_NULL, null=True, related_name='supervisors_first_choice', blank=True)
    preferred_programmes_second_choice = models.ForeignKey(ProgrammePreferenceGroup, on_delete=models.SET_NULL, null=True, related_name='supervisors_second_choice', blank=True)
    supervision_capacity = models.PositiveIntegerField(default=0)
    standardised_expertise = models.ManyToManyField(StandardisedTopic, blank=True, related_name='supervisors')
    accepting_students = models.BooleanField(default=True)

    EXPERTISE_MAX_LENGTH = 1023

    def __str__(self):
        return f"{self.user.email} - Supervisor"
    
    def clean(self):
        super().clean()
        if self.supervision_capacity < StudentProfile.objects.filter(supervisor=self).count():
            raise ValidationError({'supervision_capacity': "Supervision capacity cannot be less than the number of students assigned to this supervisor."})
        if self.supervision_capacity > StudentProfile.objects.all().count():
            raise ValidationError({'supervision_capacity': "Supervision capacity cannot exceed the total number of students in the system."})
        #check if expertise is a proper list of strings and is quoted (e.g "expertise1", "expertise2")
        if self.expertise:
            if len(self.expertise) > self.EXPERTISE_MAX_LENGTH:
                raise ValidationError({
                    'expertise': _(f'The expertise field cannot exceed {self.EXPERTISE_MAX_LENGTH} characters.')
                })
            self.expertise = self.expertise.strip()
            pattern = r'^"([^"]+)"(?:,\s*"([^"]+)")*$'
            if not re.match(pattern, self.expertise):
                raise ValidationError({'expertise': "Expertise must be a comma-separated list of non-empty quoted strings."})
            extract_pattern = r'"([^"]+)"'
            expertise_list = re.findall(extract_pattern, self.expertise)
            if not all(item.strip() for item in expertise_list):
                raise ValidationError({'expertise': "Empty quotations are not allowed."})
            
    @property
    def effective_school(self):
        return self.department.school if self.department else self.school if self.school else None
    
    @property
    def is_profile_incomplete(self):
        """
        Returns True if any of the key profile fields are empty, otherwise False.
        """
        return (
            (not self.expertise or not self.expertise.strip()) or
            self.preferred_programmes_first_choice is None or
            self.preferred_programmes_second_choice is None
        )
    
class CoordinatorProfile(models.Model):
    supervisor = models.OneToOneField(SupervisorProfile, on_delete=models.CASCADE, primary_key=True)
    appointed_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.supervisor.user.email} - Coordinator"
    
    # Set coordinator user base to staff
    def save(self, *args, **kwargs):
        self.supervisor.user.is_staff = True
        self.supervisor.user.save()
        super().save(*args, **kwargs)