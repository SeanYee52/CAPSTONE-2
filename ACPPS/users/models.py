from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator 
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.utils import timezone
from academics.models import Programme, Department, School, ProgrammePreferenceGroup, Semester
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
    positive_preferences = models.TextField(blank=True, null=True)
    negative_preferences = models.TextField(blank=True, null=True)
    supervisor = models.ForeignKey(
        'SupervisorProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='students'
    )
    semester = models.ForeignKey(
        Semester,
        on_delete=models.PROTECT, # Don't delete a session if programmes are linked to it
        default=get_default_semester(), 
        null=True, 
        blank=True,
        related_name='students'
    )
    programme_match_type = models.IntegerField(null=True)
    matching_topics = models.TextField(blank=True, null=True)
    conflicting_topics = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.email} - Student"

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
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, related_name='supervisors')
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, related_name='supervisors')
    expertise = models.TextField(blank=True, null=True)
    preferred_programmes_first_choice = models.ForeignKey(ProgrammePreferenceGroup, on_delete=models.SET_NULL, null=True, related_name='supervisors_first_choice')
    preferred_programmes_second_choice = models.ForeignKey(ProgrammePreferenceGroup, on_delete=models.SET_NULL, null=True, related_name='supervisors_second_choice')
    supervision_capacity = models.PositiveIntegerField(default=0)
    standardised_expertise = models.TextField(blank=True, null=True)
    accepting_students = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email} - Supervisor"
    
    def clean(self):
        super().clean()
        if self.supervision_capacity < StudentProfile.objects.filter(supervisor=self).count():
            raise ValueError("Supervision capacity cannot be less than the number of students assigned to this supervisor.")
        if self.supervision_capacity > StudentProfile.objects.all().count():
            raise ValueError("Supervision capacity cannot exceed the total number of students in the system.")
        #check if expertise is a proper list of strings and is quoted (e.g "expertise1", "expertise2")
        if self.expertise:
            self.expertise = self.expertise.strip()
            pattern = r'"([^"]*)"'
            if not re.match(pattern, self.expertise):
                raise ValueError("Expertise must be a comma-separated list of non-empty quoted strings.")
            expertise_list = re.findall(pattern, self.expertise)
            if not all(item.strip() for item in expertise_list):
                raise ValueError("Empty quotations are not allowed.")
            
    @property
    def effective_school(self):
        return self.department.school if self.department else self.school if self.school else None
    
class CoordinatorProfile(models.Model):
    supervisor = models.OneToOneField(SupervisorProfile, on_delete=models.CASCADE, primary_key=True)
    appointed_on = models.DateTimeField(auto_now_add=True)
    role_scope = models.CharField(max_length=20, choices=[('system', 'System-wide'), ('department', 'Department'), ('school', 'School')], default='system')

    def __str__(self):
        return f"{self.supervisor.user.email} - Coordinator"
    
    # Set coordinator user base to staff
    def save(self, *args, **kwargs):
        self.supervisor.user.is_staff = True
        self.supervisor.user.save()
        super().save(*args, **kwargs)