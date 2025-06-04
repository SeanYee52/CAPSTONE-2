from django.contrib import admin
from .models import School, Department, Programme, Faculty, ProgrammePreferenceGroup

# Register your models here.
admin.site.register(
    [
        School,
        Department,
        Programme,
        Faculty,
        ProgrammePreferenceGroup
    ]
)