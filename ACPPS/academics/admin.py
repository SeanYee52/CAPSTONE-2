from django.contrib import admin
from .models import School, Department, Programme, Faculty, ProgrammePreferenceGroup, Semester

# Register your models here.
admin.site.register(
    [
        School,
        Department,
        Programme,
        Faculty,
        ProgrammePreferenceGroup,
        Semester
    ]
)