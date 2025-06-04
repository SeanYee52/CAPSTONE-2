from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.messages.views import SuccessMessageMixin

from .models import Faculty, School, Department, Programme, ProgrammePreferenceGroup
from .forms import (
    FacultyForm, SchoolForm, DepartmentForm, ProgrammeForm, ProgrammePreferenceGroupForm
)
from .mixins import CoordinatorRequiredMixin # Import the mixin

# --- Faculty Views ---
class FacultyListView(CoordinatorRequiredMixin, ListView):
    model = Faculty
    template_name = 'academics/faculty_list.html'
    context_object_name = 'faculties'

class FacultyCreateView(CoordinatorRequiredMixin, SuccessMessageMixin, CreateView):
    model = Faculty
    form_class = FacultyForm
    template_name = 'academics/faculty_form.html'
    success_url = reverse_lazy('academics:faculty_list')
    success_message = "Faculty '%(name)s' was created successfully."

class FacultyUpdateView(CoordinatorRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Faculty
    form_class = FacultyForm
    template_name = 'academics/faculty_form.html'
    success_url = reverse_lazy('academics:faculty_list')
    success_message = "Faculty '%(name)s' was updated successfully."

# --- School Views ---
class SchoolListView(CoordinatorRequiredMixin, ListView):
    model = School
    template_name = 'academics/school_list.html'
    context_object_name = 'schools'

class SchoolCreateView(CoordinatorRequiredMixin, SuccessMessageMixin, CreateView):
    model = School
    form_class = SchoolForm
    template_name = 'academics/school_form.html'
    success_url = reverse_lazy('academics:school_list')
    success_message = "School '%(name)s' was created successfully."

class SchoolUpdateView(CoordinatorRequiredMixin, SuccessMessageMixin, UpdateView):
    model = School
    form_class = SchoolForm
    template_name = 'academics/school_form.html'
    success_url = reverse_lazy('academics:school_list')
    success_message = "School '%(name)s' was updated successfully."

# --- Department Views ---
class DepartmentListView(CoordinatorRequiredMixin, ListView):
    model = Department
    template_name = 'academics/department_list.html'
    context_object_name = 'departments'

class DepartmentCreateView(CoordinatorRequiredMixin, SuccessMessageMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'academics/department_form.html'
    success_url = reverse_lazy('academics:department_list')
    success_message = "Department '%(name)s' was created successfully."

class DepartmentUpdateView(CoordinatorRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = 'academics/department_form.html'
    success_url = reverse_lazy('academics:department_list')
    success_message = "Department '%(name)s' was updated successfully."

# --- Programme Views ---
class ProgrammeListView(CoordinatorRequiredMixin, ListView):
    model = Programme
    template_name = 'academics/programme_list.html'
    context_object_name = 'programmes'

class ProgrammeCreateView(CoordinatorRequiredMixin, SuccessMessageMixin, CreateView):
    model = Programme
    form_class = ProgrammeForm
    template_name = 'academics/programme_form.html'
    success_url = reverse_lazy('academics:programme_list')
    success_message = "Programme '%(name)s' was created successfully."

class ProgrammeUpdateView(CoordinatorRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Programme
    form_class = ProgrammeForm
    template_name = 'academics/programme_form.html'
    success_url = reverse_lazy('academics:programme_list')
    success_message = "Programme '%(name)s' was updated successfully."

# --- ProgrammePreferenceGroup Views ---
class ProgrammePreferenceGroupListView(CoordinatorRequiredMixin, ListView):
    model = ProgrammePreferenceGroup
    template_name = 'academics/preferencegroup_list.html'
    context_object_name = 'preference_groups'

class ProgrammePreferenceGroupCreateView(CoordinatorRequiredMixin, SuccessMessageMixin, CreateView):
    model = ProgrammePreferenceGroup
    form_class = ProgrammePreferenceGroupForm
    template_name = 'academics/preferencegroup_form.html'
    success_url = reverse_lazy('academics:preferencegroup_list')
    success_message = "Preference Group '%(name)s' was created successfully."

class ProgrammePreferenceGroupUpdateView(CoordinatorRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ProgrammePreferenceGroup
    form_class = ProgrammePreferenceGroupForm
    template_name = 'academics/preferencegroup_form.html'
    success_url = reverse_lazy('academics:preferencegroup_list')
    success_message = "Preference Group '%(name)s' was updated successfully."