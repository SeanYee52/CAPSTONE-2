from django import forms
from .models import Faculty, School, Department, Programme, ProgrammePreferenceGroup, Semester

class FacultyForm(forms.ModelForm):
    class Meta:
        model = Faculty
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ['name', 'faculty']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'faculty': forms.Select(attrs={'class': 'form-select'}),
        }

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'school', 'faculty']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'school': forms.Select(attrs={'class': 'form-select'}),
            'faculty': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        school = cleaned_data.get("school")
        faculty = cleaned_data.get("faculty")
        if not school and not faculty:
            raise forms.ValidationError("A department must be associated with either a School or a Faculty.")
        return cleaned_data

class ProgrammeForm(forms.ModelForm):
    class Meta:
        model = Programme
        fields = ['name', 'department']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }

class ProgrammePreferenceGroupForm(forms.ModelForm):
    class Meta:
        model = ProgrammePreferenceGroup
        fields = ['name', 'programme']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'programme': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '5'}),
        }

class SemesterForm(forms.ModelForm):
    class Meta:
        model = Semester
        fields = ['name', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }