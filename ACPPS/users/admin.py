from django.contrib import admin
from .models import User, StudentProfile, SupervisorProfile, CoordinatorProfile

# Register your models here.
admin.site.register(
    [
        User,
        StudentProfile,
        SupervisorProfile,
        CoordinatorProfile,
    ]
)