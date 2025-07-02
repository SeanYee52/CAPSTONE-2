import csv
import io
from django.db import transaction
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Q, Exists, OuterRef

# Import your forms and models
from users.forms import (
    StudentProfileForm,
    SupervisorProfileForm,
)
from users.models import User, StudentProfile, SupervisorProfile, CoordinatorProfile
from users.forms import CsvImportForm
from academics.models import Programme, Department, School, Semester
from api.models import TopicMapping

# --- Mixin for security ---
class CoordinatorRequiredMixin(LoginRequiredMixin):
    """
    Ensures that only users with a CoordinatorProfile can access the view.
    """
    def dispatch(self, request, *args, **kwargs):
        # Check if the user has a related CoordinatorProfile.
        is_coordinator = CoordinatorProfile.objects.filter(supervisor__user=request.user).exists() or request.user.is_superuser
        if not is_coordinator:
            messages.error(request, "You do not have permission to access this page.")
            return redirect('home') 
        return super().dispatch(request, *args, **kwargs)

# --- Dashboard Views ---

class StudentDashboardView(LoginRequiredMixin, View):
    login_url = "/login/"
    redirect_field_name = "redirect_to"
    template_name = 'dashboard/student.html'

    def get(self, request, *args, **kwargs):
        try:
            supervisor = SupervisorProfile.objects.get(pk=request.user.studentprofile.supervisor)
        except:
            supervisor = None
        if supervisor:
            context = {"supervisor": supervisor}
        else:
            context = {}
        return render(request, self.template_name, context)

class SupervisorDashboardView(LoginRequiredMixin, View):
    login_url = "/login/"
    redirect_field_name = "redirect_to"
    template_name = 'dashboard/supervisor.html'

    def get(self, request, *args, **kwargs):
        context = {
            'students': [],
            'remaining_capacity': 0,
            'supervisor_profile': None,
            'students_test': StudentProfile.objects.all()
        }

        if hasattr(request.user, 'supervisorprofile'):
            supervisor_profile = request.user.supervisorprofile

            students_queryset = StudentProfile.objects.filter(supervisor=supervisor_profile)

            remaining_capacity = supervisor_profile.supervision_capacity - students_queryset.count()

            context['students'] = students_queryset
            context['remaining_capacity'] = remaining_capacity
            context['supervisor_profile'] = supervisor_profile
        else:
            messages.warning(request, "The logged-in user does not have a supervisor profile.")
        return render(request, self.template_name, context)

def supervisor_dashboard_view(request):
    return render(request, 'dashboard/supervisor.html')

#region COORDINATOR VIEWS
class CoordinatorDashboardView(CoordinatorRequiredMixin, View):
    """
    The main overview dashboard for the coordinator.
    Displays summary statistics based on the actual models.
    """
    template_name = 'dashboard/coordinator_master.html'

    def get(self, request, *args, **kwargs):
        supervisor_profile = SupervisorProfile.objects.all()
        student_profile = StudentProfile.objects.all()

        context = {
            'supervisor_with_standardized_expertise_count': supervisor_profile.exclude(
                Q(standardised_expertise__isnull=True) | Q(standardised_expertise__exact='')
            ).count(),
            'students_with_labeled_preferences_count': student_profile.filter(
                Q(positive_preferences__isnull=False) & ~Q(positive_preferences='') &
                Q(negative_preferences__isnull=False) & ~Q(negative_preferences='')
            ).count(),
            'students_allocated_count': student_profile.filter(
                supervisor__isnull=False
            ).count,
            'students_count': student_profile.count(),
            'supervisors_count': supervisor_profile.count(),
            'supervisors': supervisor_profile,
        }
        return render(request, self.template_name, context)

class CoordinatorStandardizationView(CoordinatorRequiredMixin, View):
    """
    Dedicated page for the topic standardization task.
    Displays each supervisor's original and standardized expertise.
    """
    template_name = 'dashboard/coordinator_standardize.html'

    def get(self, request, *args, **kwargs):
        supervisors = SupervisorProfile.objects.select_related('user').all().order_by('user__full_name')
        topics = TopicMapping.objects.all().order_by('standardised_topic')
        
        context = {
            'supervisors': supervisors,
            'topics': topics,
        }
        return render(request, self.template_name, context)

class CoordinatorLabelingView(CoordinatorRequiredMixin, View):
    """
    Dedicated page for the student preference labeling task.
    Displays each student's original text and their resulting positive/negative labels.
    The list of students can be filtered by semester.
    """
    template_name = 'dashboard/coordinator_label.html'

    def get(self, request, *args, **kwargs):
        semesters = Semester.objects.all().order_by('-start_date')
        
        # Get the selected semester ID from the URL query parameters
        selected_semester_id_str = request.GET.get('semester')
        selected_semester_id = None

        # Base query for student profiles
        student_profiles_query = StudentProfile.objects.select_related('user', 'semester')

        if selected_semester_id_str:
            try:
                selected_semester_id = int(selected_semester_id_str)
                student_profiles_query = student_profiles_query.filter(semester__pk=selected_semester_id)
            except (ValueError, TypeError):
                student_profiles_query = student_profiles_query.none()
        else:
            # Default to the most recent semester if no parameter is given
            latest_semester = semesters.first()
            if latest_semester:
                selected_semester_id = latest_semester.pk
                student_profiles_query = student_profiles_query.filter(semester=latest_semester)
            else:
                student_profiles_query = student_profiles_query.none()

        student_profiles = student_profiles_query.order_by('user__full_name')
        
        context = {
            'semesters': semesters,
            'student_profiles': student_profiles,
            'selected_semester_id': selected_semester_id,
        }
        return render(request, self.template_name, context)

class CoordinatorMatchingView(CoordinatorRequiredMixin, View):
    """
    Dedicated page for student to supervisor matching task.
    Displays each student and their assigned supervisor.
    List of students can be filtered by semester.
    """

    template_name = 'dashboard/coordinator_match.html'

    def get(self, request, *args, **kwargs):
        semesters = Semester.objects.all().order_by('-start_date')
        
        # Get the selected semester ID from the URL query parameters
        selected_semester_id_str = request.GET.get('semester')
        selected_semester_id = None

        # Base query for student profiles
        student_profiles_query = StudentProfile.objects.select_related('user', 'semester')

        if selected_semester_id_str:
            try:
                selected_semester_id = int(selected_semester_id_str)
                student_profiles_query = student_profiles_query.filter(semester_id=selected_semester_id)
            except (ValueError, TypeError):
                student_profiles_query = student_profiles_query.none()
        else:
            # Default to the most recent semester if no parameter is given
            latest_semester = semesters.first()
            if latest_semester:
                selected_semester_id = latest_semester.pk
                student_profiles_query = student_profiles_query.filter(semester=latest_semester)
            else:
                student_profiles_query = student_profiles_query.none()

        student_profiles = student_profiles_query.order_by('user__full_name')
        supervisor_profiles = SupervisorProfile.objects.filter(Exists(StudentProfile.objects.filter(supervisor=OuterRef('pk'))))
        context = {
            'semesters': semesters,
            'student_profiles': student_profiles,
            'supervisor_profiles': supervisor_profiles,
            'selected_semester_id': selected_semester_id,
        }
        return render(request, self.template_name, context)

class CoordinatorImportView(CoordinatorRequiredMixin, View):
    """
    Provides a page for coordinators to import students and supervisors
    from separate CSV files.
    """
    template_name = 'dashboard/coordinator_import.html'

    def get(self, request, *args, **kwargs):
        """Displays the two upload forms on the page."""
        context = {
            'student_form': CsvImportForm(),
            'supervisor_form': CsvImportForm(),
            'semesters': Semester.objects.all().order_by('-start_date')
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """Handles the form submission for either students or supervisors."""
        if 'import_students' in request.POST:
            return self._handle_student_import(request)
        elif 'import_supervisors' in request.POST:
            return self._handle_supervisor_import(request)
        else:
            messages.error(request, "Invalid submission.")
            return redirect('coordinator_import')

    def _handle_student_import(self, request):
        """Processes the uploaded CSV file for students."""
        form = CsvImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "There was an error with the form. Please upload a valid CSV file.")
            return redirect('coordinator_import')

        csv_file = form.cleaned_data['csv_file']
        
        # Decode the file and use DictReader for easy column access
        try:
            reader = csv.DictReader(io.TextIOWrapper(csv_file, 'utf-8'))
            required_headers = {'Full Name', 'Student ID', 'Programme'}
            if not required_headers.issubset(set(map(str.strip, reader.fieldnames))):
                messages.error(request, f"CSV file for students must have the headers: {', '.join(required_headers)}")
                return redirect('coordinator_import')
        except Exception:
            messages.error(request, "Could not read the uploaded file. Please ensure it is a valid, UTF-8 encoded CSV.")
            return redirect('coordinator_import')

        try:
            selected_semester_id_str = request.POST.get('semester')
            semester = Semester.objects.get(pk=selected_semester_id_str)

            if not semester:
                messages.error(request, "Invalid semester. Please select a valid semester.")
                return redirect('coordinator_import')
        except Exception:
            messages.error(request, "Missing semester parameter. Please select a semester before importing students.")
            return redirect('coordinator_import')

        created_count = 0
        errors = []

        for i, row in enumerate(reader, start=2):
            full_name = row.get('Full Name', '').strip()
            student_id = row.get('Student ID', '').strip()
            programme_name = row.get('Programme', '').strip()

            if not all([full_name, student_id, programme_name]):
                errors.append(f"Row {i}: Missing required data (Full Name, Student ID, or Programme).")
                continue

            email = f"{student_id}@imail.sunway.edu.my"

            if User.objects.filter(email__iexact=email).exists():
                errors.append(f"Row {i}: User with email {email} already exists. Skipping.")
                continue

            try:
                programme = Programme.objects.get(name__iexact=programme_name)
            except Programme.DoesNotExist:
                errors.append(f"Row {i}: Programme '{programme_name}' not found in the database. Skipping.")
                continue

            try:
                with transaction.atomic(): # Atomic per row to ensure user and profile are created together
                    password = "defaultPassword123!"
                    user = User.objects.create_user(
                        email=email,
                        full_name=full_name,
                        password=password,
                        user_type='student'
                    )
                    StudentProfile.objects.create(user=user, programme=programme, semester=semester)
                    created_count += 1
            except Exception as e:
                errors.append(f"Row {i}: A database error occurred for user {email}: {e}")

        # Provide feedback to the user
        if created_count > 0:
            messages.success(request, f"Successfully imported {created_count} new students.")
        if errors:
            messages.warning(request, "Some rows could not be imported. See errors below.")
            for error in errors:
                messages.error(request, error)
        if created_count == 0 and not errors:
            messages.info(request, "The uploaded file did not contain any new students to import.")

        return redirect('coordinator_import')

    def _handle_supervisor_import(self, request):
        """Processes the uploaded CSV file for supervisors."""
        form = CsvImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "There was an error with the form. Please upload a valid CSV file.")
            return redirect('coordinator_import')
        
        csv_file = form.cleaned_data['csv_file']

        try:
            reader = csv.DictReader(io.TextIOWrapper(csv_file, 'utf-8'))
            required_headers = {'Full Name', 'Department', 'Email'}
            if not required_headers.issubset(set(map(str.strip, reader.fieldnames))):
                messages.error(request, f"CSV file for supervisors must have the headers: {', '.join(required_headers)}")
                return redirect('coordinator_import')
        except Exception:
            messages.error(request, "Could not read the uploaded file. Please ensure it is a valid, UTF-8 encoded CSV.")
            return redirect('coordinator_import')

        created_count = 0
        errors = []

        for i, row in enumerate(reader, start=2):
            full_name = row.get('Full Name', '').strip()
            email = row.get('Email', '').strip()
            org_unit_name = row.get('Department', '').strip()

            if not all([full_name, email, org_unit_name]):
                errors.append(f"Row {i}: Missing required data (Full Name, Department, or Email).")
                continue
            
            if User.objects.filter(email__iexact=email).exists():
                errors.append(f"Row {i}: User with email {email} already exists. Skipping.")
                continue
            
            department, school = None, None
            try: # Find a matching Department
                department = Department.objects.get(name__iexact=org_unit_name)
                school = department.school
            except Department.DoesNotExist:
                try: # Find a matching School
                    school = School.objects.get(name__iexact=org_unit_name)
                except School.DoesNotExist:
                    errors.append(f"Row {i}: Neither a Department nor a School named '{org_unit_name}' was found. Skipping.")
                    continue
            
            try:
                with transaction.atomic():
                    password = "defaultPassword123!"
                    user = User.objects.create_user(
                        email=email,
                        full_name=full_name,
                        password=password,
                        user_type='supervisor'
                    )
                    SupervisorProfile.objects.create(user=user, department=department, school=school)
                    created_count += 1
            except Exception as e:
                errors.append(f"Row {i}: A database error occurred for user {email}: {e}")

        # Provide feedback
        if created_count > 0:
            messages.success(request, f"Successfully imported {created_count} new supervisors.")
        if errors:
            messages.warning(request, "Some rows could not be imported. See errors below.")
            for error in errors:
                messages.error(request, error)
        if created_count == 0 and not errors:
            messages.info(request, "The uploaded file did not contain any new supervisors to import.")
            
        return redirect('coordinator_import')

#region PROFILE UPDATE
@method_decorator(login_required, name='dispatch')
class UpdateProfileView(View):
    template_name = 'dashboard/update_profile.html'

    def get_form_and_instance(self, user):
        """
        Determines the correct form and profile instance based on user type.
        Handles cases where a profile object might not exist yet.
        """
        if hasattr(user, 'supervisorprofile'):
            return SupervisorProfileForm, user.supervisorprofile
        elif hasattr(user, 'studentprofile'):
            return StudentProfileForm, user.studentprofile
        return None, None
    
    def get_success_url(self, user):
        """Determines the redirect URL after a successful update."""
        if hasattr(user, 'supervisorprofile'):
            return reverse('supervisor_dashboard')
        elif hasattr(user, 'studentprofile'):
            return reverse('student_dashboard')
        return reverse('home')

    def get(self, request, *args, **kwargs):
        user = request.user
        form_class, instance = self.get_form_and_instance(user)
        if not form_class:
            messages.error(request, "You do not have a profile that can be updated.")
            return redirect('home') 
        form = form_class(instance=instance)
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        user = request.user
        form_class, instance = self.get_form_and_instance(user)
        if not form_class:
            messages.error(request, "You do not have a profile that can be updated.")
            return redirect('home')
        form = form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect(self.get_success_url(user))
        messages.error(request, "Please correct the errors below.")
        return render(request, self.template_name, {'form': form})