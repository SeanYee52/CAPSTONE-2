import csv
import random
import re
import ast
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify # For generating username part of email

from users.models import SupervisorProfile
from academics.models import School, Department, ProgrammePreferenceGroup 

User = get_user_model()

DEPARTMENT_MAPPING = {
    "DDSAI": "Department of Data Science and Artificial Intelligence",
    "DSCCR": "Department of Smart Computing and Cyber Resilience",
    "HUMAC": "Research Centre for Human-Machine Collaboration (HUMAC)"
    # "SEN" is handled as a special case for School
}
SCHOOL_OF_ENGINEERING_ABBR = "SEN"
SCHOOL_OF_ENGINEERING_NAME = "School of Engineering"

class Command(BaseCommand):
    help = 'Imports supervisors from a CSV file into SupervisorProfile model'

    def add_arguments(self, parser):
        parser.add_argument('csv_file_path', type=str, help='The path to the CSV file to import.')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file_path']

        # Try to get the School of Engineering - script will fail if it doesn't exist
        try:
            school_of_eng = School.objects.get(name=SCHOOL_OF_ENGINEERING_NAME)
        except School.DoesNotExist:
            raise CommandError(f"School '{SCHOOL_OF_ENGINEERING_NAME}' does not exist. Please create it first.")

        # Pre-fetch departments to avoid multiple DB hits in loop
        departments_cache = {}
        for abbr, name in DEPARTMENT_MAPPING.items():
            try:
                departments_cache[abbr] = Department.objects.get(name=name)
            except Department.DoesNotExist:
                raise CommandError(f"Department '{name}' (for abbreviation '{abbr}') does not exist. Please create it first.")

        # Pre-fetch programme preference groups
        programme_groups_cache = {pg.name: pg for pg in ProgrammePreferenceGroup.objects.all()}

        try:
            with open(csv_file_path, mode='r', encoding='utf-8-sig') as file: # utf-8-sig handles BOM
                reader = csv.DictReader(file)
                
                if not reader.fieldnames:
                    self.stdout.write(self.style.WARNING("CSV file is empty or has no headers."))
                    return

                expected_headers = ["Name", "Department", "Preferred Programme for Supervision (1st Choice)", 
                                    "Preferred Programme for Supervision (2nd Choice)", 
                                    "Expertise Area 1", "Expertise Area 2", "Expertise Area 3"]
                
                for header in expected_headers:
                    if header not in reader.fieldnames:
                        raise CommandError(f"CSV file is missing expected header: '{header}'. Found headers: {reader.fieldnames}")

                supervisors_created_count = 0
                supervisors_updated_count = 0

                with transaction.atomic(): # Use a transaction for atomicity
                    for row_num, row in enumerate(reader, 1):
                        full_name = row.get("Name", "").strip()
                        department_abbr = row.get("Department", "").strip()
                        pref_prog_1_raw = row.get("Preferred Programme for Supervision (1st Choice)", "").strip()
                        pref_prog_2_raw = row.get("Preferred Programme for Supervision (2nd Choice)", "").strip()
                        # exp1, exp2, exp3 are all python lists
                        
                        #region NEED TO UPDATE
                        exp1 = ast.literal_eval(row.get("Expertise Area 1", ""))
                        exp2 = ast.literal_eval(row.get("Expertise Area 2", ""))
                        exp3 = ast.literal_eval(row.get("Expertise Area 3", ""))
                        combined_exp = exp1 + exp2 + exp3

                        if not full_name:
                            self.stdout.write(self.style.WARNING(f"Skipping row {row_num}: Supervisor name is missing."))
                            continue

                        # 1. Create or get User
                        # Generate a unique email. Using slugify for a cleaner username part.
                        # You might need a more robust way to ensure email uniqueness or derive it.
                        email_username_part = slugify(full_name)
                        email = f"{email_username_part}@supervisor.example.com" # Using a placeholder domain
                        
                        user, user_created = User.objects.get_or_create(
                            email=email,
                            defaults={
                                'full_name': full_name,
                                'user_type': 'supervisor',
                                'password': 'defaultPassword123!'
                            }
                        )
                        if user_created:
                            user.set_password('defaultPassword123!') # Or User.objects.make_random_password()
                            user.save()
                            self.stdout.write(self.style.SUCCESS(f"Created user: {user.email}"))
                        elif user.user_type != 'supervisor':
                             self.stdout.write(self.style.WARNING(f"User {user.email} exists but is not a supervisor. Skipping profile creation for this user."))
                             continue


                        # 2. Determine Department and School
                        supervisor_department = None
                        supervisor_school = None

                        if department_abbr == SCHOOL_OF_ENGINEERING_ABBR:
                            supervisor_school = school_of_eng
                        elif department_abbr in departments_cache:
                            supervisor_department = departments_cache[department_abbr]
                        elif department_abbr: # If abbreviation is present but not mapped
                            self.stdout.write(self.style.WARNING(f"Row {row_num} for '{full_name}': Unknown department abbreviation '{department_abbr}'. Department will be null."))
                        # If department_abbr is empty, both will remain None which is allowed by model

                        # 3. Compile Expertise
                        #region NEED TO UPDATE
                        expertise_list = [re.sub(r"[^\w\s/-]", "", e).strip().lower() for e in combined_exp if e] # Filter out empty strings
                        # use regex to remove any non-alphanumeric characters such as "[" and "]" and "'" and convert to lowercase
                        # do not remove "/" as it is used in some expertise areas
                        expertise_text = ', '.join(f'"{e}"' for e in expertise_list if e.strip() != "")

                        # 4. Get Preferred Programmes
                        pref_prog_1_obj = None
                        if pref_prog_1_raw:
                            cleaned_pref_1 = pref_prog_1_raw # Assuming names are exact as in DB
                            if cleaned_pref_1 in programme_groups_cache:
                                pref_prog_1_obj = programme_groups_cache[cleaned_pref_1]
                            else:
                                self.stdout.write(self.style.WARNING(f"Row {row_num} for '{full_name}': ProgrammePreferenceGroup '{cleaned_pref_1}' (1st choice) not found. Skipping."))

                        pref_prog_2_obj = None
                        if pref_prog_2_raw:
                            cleaned_pref_2 = pref_prog_2_raw # Assuming names are exact as in DB
                            if cleaned_pref_2 in programme_groups_cache:
                                pref_prog_2_obj = programme_groups_cache[cleaned_pref_2]
                            else:
                                self.stdout.write(self.style.WARNING(f"Row {row_num} for '{full_name}': ProgrammePreferenceGroup '{cleaned_pref_2}' (2nd choice) not found. Skipping."))

                        # 5. Supervision Capacity
                        supervision_capacity = random.randint(3, 10)

                        # 6. Create or Update SupervisorProfile
                        # standardized_expertise is left blank (model default)
                        profile, profile_created = SupervisorProfile.objects.update_or_create(
                            user=user,
                            defaults={
                                'department': supervisor_department,
                                'school': supervisor_school, # Explicitly set school, esp. for SEN
                                'expertise': expertise_text,
                                'preferred_programmes_first_choice': pref_prog_1_obj,
                                'preferred_programmes_second_choice': pref_prog_2_obj,
                                'supervision_capacity': supervision_capacity,
                                'standardised_expertise': None, # Explicitly set to blank as per requirement
                            }
                        )

                        if profile_created:
                            supervisors_created_count += 1
                        else:
                            supervisors_updated_count += 1

            self.stdout.write(self.style.SUCCESS(
                f"Import complete. "
                f"Supervisors created: {supervisors_created_count}. "
                f"Supervisors updated: {supervisors_updated_count}."
            ))

        except FileNotFoundError:
            raise CommandError(f"CSV file not found at path: {csv_file_path}")
        except Exception as e:
            raise CommandError(f"An error occurred during import: {e}")