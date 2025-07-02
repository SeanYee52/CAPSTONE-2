import csv
import random
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from users.models import StudentProfile
from academics.models import Programme, Semester

User = get_user_model()

class Command(BaseCommand):
    help = 'Imports student preference text from a CSV file into StudentProfile model'

    def add_arguments(self, parser):
        parser.add_argument('csv_file_path', type=str, help='The path to the CSV file to import.')
        parser.add_argument(
            '--email_domain',
            type=str,
            default='student.example.com',
            help='The domain to use for generating student email addresses.'
        )
        parser.add_argument(
            '--id_column',
            type=str,
            default=None, # If None, will use row number or a generated ID
            help='Optional CSV column name to use as a base for student ID/email username. If not provided, a generic ID will be used.'
        )
        parser.add_argument(
            '--name_column',
            type=str,
            default=None,
            help='Optional CSV column name to use for the student\'s full name. If not provided, a generic name will be used.'
        )
        parser.add_argument(
            '--sentence_column',
            type=str,
            default='sentence',
            help='The CSV column name containing the preference text. Default is "sentence".'
        )


    def handle(self, *args, **options):
        csv_file_path = options['csv_file_path']
        email_domain = options['email_domain']
        id_column_name = options['id_column']
        name_column_name = options['name_column']
        sentence_column_name = options['sentence_column']

        # Fetch all available programmes once
        available_programmes = list(Programme.objects.all())
        if not available_programmes:
            raise CommandError("No Programmes found in the database. Please add some Programmes before running this import.")

        try:
            with open(csv_file_path, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                if not reader.fieldnames:
                    self.stdout.write(self.style.WARNING("CSV file is empty or has no headers."))
                    return

                if sentence_column_name not in reader.fieldnames:
                    raise CommandError(f"CSV file is missing the expected sentence header: '{sentence_column_name}'. Found headers: {reader.fieldnames}")
                if id_column_name and id_column_name not in reader.fieldnames:
                    raise CommandError(f"CSV file is missing the specified ID header: '{id_column_name}'. Found headers: {reader.fieldnames}")
                if name_column_name and name_column_name not in reader.fieldnames:
                    raise CommandError(f"CSV file is missing the specified name header: '{name_column_name}'. Found headers: {reader.fieldnames}")


                students_created_count = 0
                students_updated_count = 0

                with transaction.atomic():
                    for row_num, row in enumerate(reader, 1):
                        preference_text_data = row.get(sentence_column_name, "").strip()

                        # 1. Determine Student Identifier and Name
                        student_identifier_base = ""
                        full_name = f"Student {row_num}" # Default full name

                        if id_column_name:
                            student_identifier_base = row.get(id_column_name, "").strip()
                            if not student_identifier_base:
                                self.stdout.write(self.style.WARNING(f"Row {row_num}: ID column '{id_column_name}' is empty. Using generic ID."))
                                student_identifier_base = f"student{row_num}"
                        else:
                            student_identifier_base = f"student{row_num}" # Fallback if no ID column
                        
                        if name_column_name:
                            csv_full_name = row.get(name_column_name, "").strip()
                            if csv_full_name:
                                full_name = csv_full_name
                            else:
                                self.stdout.write(self.style.WARNING(f"Row {row_num}: Name column '{name_column_name}' is empty. Using generic name '{full_name}'."))
                        
                        # Generate a unique email
                        email_username_part = slugify(student_identifier_base)
                        email = f"{email_username_part}@{email_domain}"
                        
                        # # Ensure email is unique if it might not be
                        temp_email = email
                        counter = 1
                        while User.objects.filter(email=temp_email).exists():
                            temp_email = f"{email_username_part}{counter}@{email_domain}"
                            counter += 1
                        email = temp_email
                        
                        # 2. Create or get User
                        user, user_created = User.objects.get_or_create(
                            email=email,
                            defaults={
                                'full_name': full_name,
                                'user_type': 'student',
                            }
                        )

                        if user_created:
                            user.set_password('defaultPassword123!') # Set a random secure password
                            user.save()
                            self.stdout.write(self.style.SUCCESS(f"Created user: {user.email} for '{full_name}'"))
                        elif user.user_type != 'student':
                             self.stdout.write(self.style.WARNING(f"User {user.email} exists but is not a student. Updating user_type to student."))
                             user.user_type = 'student'
                             user.full_name = full_name # Update full name if user existed
                             user.save()
                        # If user existed and is already a student, we proceed to create/update profile.

                        # 3. Randomly select a Programme
                        selected_programme = random.choice(available_programmes)

                        # 4. Create or Update StudentProfile
                        # Other fields (positive_preferences, negative_preferences, supervisor) will be left blank/null.
                        profile, profile_created = StudentProfile.objects.update_or_create(
                            user=user,
                            defaults={
                                'programme': selected_programme,
                                'preference_text': preference_text_data,
                                'semester': Semester.objects.latest(),
                                # Explicitly set others to None or leave them to model defaults if appropriate
                                'positive_preferences': None,
                                'negative_preferences': None,
                                'supervisor': None,
                            }
                        )

                        if profile_created:
                            students_created_count += 1
                        else:
                            students_updated_count += 1
            
            self.stdout.write(self.style.SUCCESS(
                f"Import complete. "
                f"Student profiles created: {students_created_count}. "
                f"Student profiles updated: {students_updated_count}."
            ))

        except FileNotFoundError:
            raise CommandError(f"CSV file not found at path: {csv_file_path}")
        except CommandError as e: # Re-raise CommandErrors to halt execution
            raise e
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise CommandError(f"An unexpected error occurred during import: {e}")