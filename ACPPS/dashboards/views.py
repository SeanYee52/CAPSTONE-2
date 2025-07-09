import csv
import io
import datetime
from django.http import HttpResponse
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
from academics.models import Programme, Department, School, Semester, ProgrammePreferenceGroup
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
    from separate CSV files. Handles both creation of new users and
    updates to existing users.
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

    def _parse_boolean(self, value):
        """Helper to interpret various string representations of a boolean."""
        if isinstance(value, str):
            val = value.lower().strip()
            if val in ('true', '1', 't', 'y', 'yes'):
                return True
            if val in ('false', '0', 'f', 'n', 'no'):
                return False
        return None # Return None for empty or ambiguous values

    def _handle_student_import(self, request):
        """
        Processes the uploaded CSV file for students. Creates or updates records.
        
        Required CSV Headers:
        - 'Full Name'
        - 'Student ID'
        - 'Programme'
        
        Optional CSV Headers:
        - 'Supervisor Email' (Email of the supervisor to assign)
        - 'Preference Text'
        - 'Positive Preferences'
        - 'Negative Preferences'
        - 'Programme Match Type' (Integer)
        - 'Matching Topics'
        - 'Conflicting Topics'
        """
        form = CsvImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "There was an error with the form. Please upload a valid CSV file.")
            return redirect('coordinator_import')

        csv_file = form.cleaned_data['csv_file']
        
        try:
            reader = csv.DictReader(io.TextIOWrapper(csv_file, 'utf-8-sig'))
            headers = set(map(str.strip, reader.fieldnames or []))
            required_headers = {'Full Name', 'Student ID', 'Programme'}
            if not required_headers.issubset(headers):
                messages.error(request, f"CSV for students must have headers: {', '.join(required_headers)}")
                return redirect('coordinator_import')
        except Exception:
            messages.error(request, "Could not read the uploaded file. Ensure it is a valid, UTF-8 encoded CSV.")
            return redirect('coordinator_import')

        try:
            semester = Semester.objects.get(pk=request.POST.get('semester'))
        except (Semester.DoesNotExist, ValueError, TypeError):
            messages.error(request, "A valid semester must be selected before importing students.")
            return redirect('coordinator_import')

        created_count, updated_count, errors = 0, 0, []

        for i, row in enumerate(reader, start=2):
            full_name = row.get('Full Name', '').strip()
            student_id = row.get('Student ID', '').strip().lower()
            programme_name = row.get('Programme', '').strip()

            if not all([full_name, student_id, programme_name]):
                errors.append(f"Row {i}: Missing required data (Full Name, Student ID, or Programme).")
                continue

            try:
                programme = Programme.objects.get(name__iexact=programme_name)
            except Programme.DoesNotExist:
                errors.append(f"Row {i}: Programme '{programme_name}' not found. Skipping.")
                continue

            email = f"{student_id}@imail.sunway.edu.my"
            profile_data = {}

            # Handle optional fields and Foreign Keys
            try:
                if 'Supervisor Email' in headers and row.get('Supervisor Email', '').strip():
                    supervisor_email = row.get('Supervisor Email').strip()
                    profile_data['supervisor'] = SupervisorProfile.objects.get(user__email__iexact=supervisor_email)
                
                if 'Programme Match Type' in headers and row.get('Programme Match Type', '').strip():
                    profile_data['programme_match_type'] = int(row.get('Programme Match Type').strip())

                # Simple text fields
                optional_text_fields = ['preference_text', 'positive_preferences', 'negative_preferences',
                                        'matching_topics', 'conflicting_topics']
                csv_headers_map = {'preference_text': 'Preference Text', 'positive_preferences': 'Positive Preferences',
                                   'negative_preferences': 'Negative Preferences', 'matching_topics': 'Matching Topics',
                                   'conflicting_topics': 'Conflicting Topics'}

                for field in optional_text_fields:
                    header = csv_headers_map[field]
                    if header in headers:
                        profile_data[field] = row.get(header, '').strip()

            except SupervisorProfile.DoesNotExist:
                errors.append(f"Row {i}: Supervisor with email '{row.get('Supervisor Email')}' not found. Skipping.")
                continue
            except (ValueError, TypeError):
                errors.append(f"Row {i}: Invalid 'Programme Match Type'. It must be a whole number. Skipping.")
                continue

            try:
                with transaction.atomic():
                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={'full_name': full_name, 'user_type': 'student'}
                    )
                    
                    if created:
                        user.set_password("defaultPassword123!")
                        user.save()
                    else:
                        user.full_name = full_name
                        user.user_type = 'student'
                        user.save()
                    
                    profile, profile_created = StudentProfile.objects.update_or_create(
                        user=user,
                        defaults={'programme': programme, 'semester': semester, **profile_data}
                    )
                    
                    if created: created_count += 1
                    else: updated_count += 1

            except Exception as e:
                errors.append(f"Row {i}: Database error for student {email}: {e}")

        # Provide feedback
        if created_count > 0: messages.success(request, f"Successfully created {created_count} new students.")
        if updated_count > 0: messages.info(request, f"Successfully updated {updated_count} existing students.")
        if errors:
            messages.warning(request, "Some rows could not be imported. See errors below:")
            for error in errors: messages.error(request, error)
        if created_count == 0 and updated_count == 0 and not errors:
            messages.info(request, "The file did not contain any new or updated student information.")
        return redirect('coordinator_import')

    def _handle_supervisor_import(self, request):
        """
        Processes the uploaded CSV file for supervisors. Creates or updates records.
        
        Required CSV Headers:
        - 'Full Name'
        - 'Email'
        - 'Department' (Name of the Department or School)
        
        Optional CSV Headers:
        - 'Expertise'
        - 'Supervision Capacity' (Integer)
        - 'Accepting Students' (True/False, Yes/No, 1/0)
        - 'Standardised Expertise'
        - 'Preferred Programmes First Choice' (Name of the ProgrammePreferenceGroup)
        - 'Preferred Programmes Second Choice' (Name of the ProgrammePreferenceGroup)
        """
        form = CsvImportForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Error with form. Please upload a valid CSV file.")
            return redirect('coordinator_import')
        
        csv_file = form.cleaned_data['csv_file']

        try:
            reader = csv.DictReader(io.TextIOWrapper(csv_file, 'utf-8-sig'))
            headers = set(map(str.strip, reader.fieldnames or []))
            required_headers = {'Full Name', 'Department', 'Email'}
            if not required_headers.issubset(headers):
                messages.error(request, f"CSV for supervisors must have headers: {', '.join(required_headers)}")
                return redirect('coordinator_import')
        except Exception:
            messages.error(request, "Could not read the uploaded file. Ensure it is a valid, UTF-8 encoded CSV.")
            return redirect('coordinator_import')

        created_count, updated_count, errors = 0, 0, []

        for i, row in enumerate(reader, start=2):
            full_name = row.get('Full Name', '').strip()
            email = row.get('Email', '').strip().lower()
            org_unit_name = row.get('Department', '').strip()

            if not all([full_name, email, org_unit_name]):
                errors.append(f"Row {i}: Missing required data (Full Name, Department, or Email).")
                continue
            
            department, school = None, None
            try:
                department = Department.objects.get(name__iexact=org_unit_name)
                school = department.school
            except Department.DoesNotExist:
                try:
                    school = School.objects.get(name__iexact=org_unit_name)
                except School.DoesNotExist:
                    errors.append(f"Row {i}: Department/School '{org_unit_name}' not found. Skipping.")
                    continue
            
            profile_data = {}
            try:
                if 'Expertise' in headers: profile_data['expertise'] = row.get('Expertise', '').strip()
                if 'Standardised Expertise' in headers: profile_data['standardised_expertise'] = row.get('Standardised Expertise', '').strip()
                
                if 'Supervision Capacity' in headers and row.get('Supervision Capacity', '').strip():
                    profile_data['supervision_capacity'] = int(row.get('Supervision Capacity').strip())
                
                if 'Accepting Students' in headers:
                    accepting = self._parse_boolean(row.get('Accepting Students'))
                    if accepting is not None: profile_data['accepting_students'] = accepting
                
                if 'Preferred Programmes First Choice' in headers and row.get('Preferred Programmes First Choice', '').strip():
                    group_name = row.get('Preferred Programmes First Choice').strip()
                    profile_data['preferred_programmes_first_choice'] = ProgrammePreferenceGroup.objects.get(name__iexact=group_name)
                
                if 'Preferred Programmes Second Choice' in headers and row.get('Preferred Programmes Second Choice', '').strip():
                    group_name = row.get('Preferred Programmes Second Choice').strip()
                    profile_data['preferred_programmes_second_choice'] = ProgrammePreferenceGroup.objects.get(name__iexact=group_name)

            except (ValueError, TypeError):
                errors.append(f"Row {i}: Invalid 'Supervision Capacity'. It must be a whole number. Skipping.")
                continue
            except ProgrammePreferenceGroup.DoesNotExist:
                errors.append(f"Row {i}: Programme Preference Group '{row.get('Preferred Programmes First Choice') or row.get('Preferred Programmes Second Choice')}' not found. Skipping.")
                continue

            try:
                with transaction.atomic():
                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={'full_name': full_name, 'user_type': 'supervisor'}
                    )
                    if created:
                        user.set_password("defaultPassword123!")
                        user.save()
                    else:
                        user.full_name = full_name
                        user.user_type = 'supervisor'
                        user.save()
                    
                    profile, profile_created = SupervisorProfile.objects.update_or_create(
                        user=user,
                        defaults={'department': department, 'school': school, **profile_data}
                    )
                    if created: created_count += 1
                    else: updated_count += 1

            except Exception as e:
                errors.append(f"Row {i}: Database error for supervisor {email}: {e}")

        # Provide feedback
        if created_count > 0: messages.success(request, f"Successfully created {created_count} new supervisors.")
        if updated_count > 0: messages.info(request, f"Successfully updated {updated_count} existing supervisors.")
        if errors:
            messages.warning(request, "Some rows could not be imported. See errors below:")
            for error in errors: messages.error(request, error)
        if created_count == 0 and updated_count == 0 and not errors:
            messages.info(request, "The file did not contain any new or updated supervisor information.")
            
        return redirect('coordinator_import')

class CoordinatorExportView(CoordinatorRequiredMixin, View):
    """
    Handles exporting student or supervisor data to a CSV file.
    The exported file is formatted to be re-importable by CoordinatorImportView.
    """

    def get(self, request, *args, **kwargs):
        """
        Determines whether to export students or supervisors based on the URL.
        """
        user_type = kwargs.get('user_type')
        if user_type == 'students':
            return self._export_students(request)
        elif user_type == 'supervisors':
            return self._export_supervisors(request)
        else:
            messages.error(request, "Invalid export type specified.")
            return redirect('dashboard') # Or some other appropriate page

    def _export_students(self, request):
        """
        Generates and returns a CSV file of all student data.
        """
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="students_export_{datetime.date.today()}.csv"'},
        )

        # Use the same headers as the import expects
        writer = csv.writer(response)
        header = [
            'Student ID', 'Full Name', 'Programme', 'Supervisor Email',
            'Preference Text', 'Positive Preferences', 'Negative Preferences',
            'Programme Match Type', 'Matching Topics', 'Conflicting Topics'
        ]
        writer.writerow(header)

        # Optimize query to fetch related data in one go
        students = StudentProfile.objects.select_related(
            'user', 'programme', 'supervisor__user'
        ).all()

        for profile in students:
            writer.writerow([
                profile.student_id,
                profile.user.full_name,
                profile.programme.name if profile.programme else '',
                profile.supervisor.user.email if profile.supervisor and profile.supervisor.user else '',
                profile.preference_text or '',
                profile.positive_preferences or '',
                profile.negative_preferences or '',
                profile.programme_match_type if profile.programme_match_type is not None else '',
                profile.matching_topics or '',
                profile.conflicting_topics or '',
            ])

        return response

    def _export_supervisors(self, request):
        """
        Generates and returns a CSV file of all supervisor data.
        """
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="supervisors_export_{datetime.date.today()}.csv"'},
        )

        writer = csv.writer(response)
        header = [
            'Email', 'Full Name', 'Department', 'Supervision Capacity',
            'Accepting Students', 'Expertise', 'Standardised Expertise',
            'Preferred Programmes First Choice', 'Preferred Programmes Second Choice'
        ]
        writer.writerow(header)

        # Optimize query
        supervisors = SupervisorProfile.objects.select_related(
            'user', 'department', 'school',
            'preferred_programmes_first_choice', 'preferred_programmes_second_choice'
        ).all()

        for profile in supervisors:
            # The import function checks for Department name first, then School name.
            # We will export the Department name if it exists, otherwise the School name.
            org_unit_name = profile.department.name if profile.department else \
                            (profile.school.name if profile.school else '')

            writer.writerow([
                profile.user.email,
                profile.user.full_name,
                org_unit_name,
                profile.supervision_capacity,
                profile.accepting_students,
                profile.expertise or '',
                profile.standardised_expertise or '',
                profile.preferred_programmes_first_choice.name if profile.preferred_programmes_first_choice else '',
                profile.preferred_programmes_second_choice.name if profile.preferred_programmes_second_choice else '',
            ])
            
        return response

class DeleteStudentsBySemesterView(CoordinatorRequiredMixin, View):
    """
    Provides a page for coordinators to delete all students from a selected semester.
    This is a destructive action and requires explicit confirmation.
    """
    template_name = 'dashboard/delete_students_confirmation.html'

    def get(self, request, *args, **kwargs):
        """
        Displays the confirmation page with a list of semesters.
        """
        context = {
            'semesters': Semester.objects.all().order_by('-start_date')
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        """
        Handles the deletion of students for the selected semester.
        """
        semester_id = request.POST.get('semester')
        confirmation = request.POST.get('confirmation_check')

        # Security Check: Ensure the user explicitly confirmed the action.
        if not confirmation:
            messages.error(request, "You must check the confirmation box to proceed with the deletion.")
            return redirect('delete_students_by_semester')

        if not semester_id:
            messages.error(request, "You must select a semester.")
            return redirect('delete_students_by_semester')

        try:
            semester = Semester.objects.get(pk=semester_id)
        except Semester.DoesNotExist:
            messages.error(request, "The selected semester is invalid.")
            return redirect('delete_students_by_semester')

        # Find the users to be deleted.
        # Deleting the User will cascade and delete the associated StudentProfile.
        users_to_delete = User.objects.filter(
            studentprofile__semester=semester,
            user_type='student' # Extra safeguard
        )
        
        count = users_to_delete.count()

        if count > 0:
            try:
                with transaction.atomic():
                    # The .delete() method returns the number of objects deleted and a dictionary with details.
                    deleted_count, _ = users_to_delete.delete()
                
                messages.success(request, f"Successfully deleted {count} students and their accounts from the semester: {semester.name}.")
            except Exception as e:
                 messages.error(request, f"An error occurred during deletion: {e}")
        else:
            messages.info(request, f"No students were found in the semester '{semester.name}' to delete.")

        return redirect('coordinator_import') # Redirect back to the main import/export page

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