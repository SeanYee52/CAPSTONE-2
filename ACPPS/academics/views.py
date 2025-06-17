from django.urls import reverse_lazy
from django.views.generic import View
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import Http404

from .models import Faculty, School, Department, Programme, ProgrammePreferenceGroup, Semester
from .forms import (
    FacultyForm, SchoolForm, DepartmentForm, ProgrammeForm, ProgrammePreferenceGroupForm, SemesterForm
)
from .mixins import CoordinatorRequiredMixin

# Centralized configuration for our models
MODEL_CONFIG = {
    'faculty': {
        'model': Faculty,
        'form': FacultyForm,
        'plural': 'Faculties',
        'singular': 'Faculty'
    },
    'school': {
        'model': School,
        'form': SchoolForm,
        'plural': 'Schools',
        'singular': 'School'
    },
    'department': {
        'model': Department,
        'form': DepartmentForm,
        'plural': 'Departments',
        'singular': 'Department'
    },
    'programme': {
        'model': Programme,
        'form': ProgrammeForm,
        'plural': 'Programmes',
        'singular': 'Programme'
    },
    'preferencegroup': {
        'model': ProgrammePreferenceGroup,
        'form': ProgrammePreferenceGroupForm,
        'plural': 'Preference Groups',
        'singular': 'Preference Group'
    },
    'semester': {
        'model': Semester,
        'form': SemesterForm,
        'plural': 'Semesters',
        'singular': 'Semester',
    }
}

class AcademicDashboardView(CoordinatorRequiredMixin, View):
    """
    The master view for the academics section.
    Displays a dashboard with summaries and links to manage each academic model.
    """
    template_name = 'academics/master_dashboard.html'

    def get(self, request, *args, **kwargs):
        # Dynamically create context for the dashboard from our config
        dashboard_items = []
        for key, config in MODEL_CONFIG.items():
            dashboard_items.append({
                'key': key,
                'plural_name': config['plural'],
                'count': config['model'].objects.count(),
                'manage_url': reverse_lazy('academics:admin_list', kwargs={'model_name': key})
            })
            
        context = {
            'dashboard_items': dashboard_items
        }
        return render(request, self.template_name, context)

class AcademicAdminView(CoordinatorRequiredMixin, View):
    """
    A single, dynamic view to handle List, Create, and Update operations
    for all academic models (Faculty, School, Department, etc.).
    """
    
    def dispatch(self, request, *args, **kwargs):
        """
        Gets model configuration from URL parameter and sets it on the view instance.
        """
        model_name = kwargs.get('model_name')
        if model_name not in MODEL_CONFIG:
            raise Http404("The requested academic model does not exist.")
        
        # Store configuration for use in other methods
        self.config = MODEL_CONFIG[model_name]
        self.model = self.config['model']
        self.form_class = self.config['form']
        self.model_name_key = model_name # e.g., 'faculty'
        
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        """
        Handles both displaying a list of objects and displaying a
        form for creation or update.
        """
        pk = kwargs.get('pk')
        context = {
            'config': self.config,
            'model_name_key': self.model_name_key,
        }

        # If a primary key is provided, it's an UPDATE view
        if pk:
            obj = get_object_or_404(self.model, pk=pk)
            form = self.form_class(instance=obj)
            context['form'] = form
            context['object'] = obj
            return render(request, 'academics/generic_form.html', context)
        
        # If no primary key, it's a LIST or CREATE view
        # The URL pattern distinguishes between list and create ('/add/')
        if 'add' in request.path:
            form = self.form_class()
            context['form'] = form
            return render(request, 'academics/generic_form.html', context)
        else:
            objects = self.model.objects.all()
            context['object_list'] = objects
            return render(request, 'academics/generic_list.html', context)

    def post(self, request, *args, **kwargs):
        """
        Handles form submission for both creating new objects and
        updating existing ones.
        """
        pk = kwargs.get('pk')
        obj = None

        # If a primary key is provided, it's an UPDATE operation
        if pk:
            obj = get_object_or_404(self.model, pk=pk)
            form = self.form_class(request.POST, request.FILES, instance=obj)
            action_word = 'updated'
        # Otherwise, it's a CREATE operation
        else:
            form = self.form_class(request.POST, request.FILES)
            action_word = 'created'
            
        if form.is_valid():
            saved_obj = form.save()
            messages.success(
                request,
                f"{self.config['singular']} '{saved_obj}' was {action_word} successfully."
            )
            # Redirect to the list view for this model type
            return redirect('academics:admin_list', model_name=self.model_name_key)
            
        # If form is not valid, re-render the form page with errors
        context = {
            'config': self.config,
            'model_name_key': self.model_name_key,
            'form': form,
            'object': obj, # will be None for create view, which is fine
        }
        return render(request, 'academics/generic_form.html', context)