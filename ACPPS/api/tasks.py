# api/tasks.py
from celery import shared_task
import google.generativeai as genai
import json
import os
import re
import math
import time

from .models import OriginalTopic, StandardisedTopic
from users.models import StudentProfile, SupervisorProfile, User
from academics.models import Semester
from django.db.models import Q, F, Count, Sum
from django.db import transaction

def get_standardisation_map_from_gemini(unique_terms_list, model, prompt=""):
    """
    Sends a list of unique expertise terms to Gemini and asks for a standardisation map.
    Returns a dictionary: {"original_term": "standardised_term"}.
    """
    if not model:
        print("Gemini model not initialized. Cannot proceed.")
        return None
    if not unique_terms_list:
        print("No unique terms provided to standardise.")
        return {}
    
    if not prompt:
        prompt = f"""
        You are an expert academic research field categorizer and data normalizer.
        I have a list of expertise areas extracted from a dataset of supervisors.
        Many of these terms are variations of the same concept (e.g., "IoT", "Internet of Things", "Industrial IoT")
        or very closely related.

        Your task is to analyze the following list of unique expertise terms and create a JSON object
        that maps each original term to a single, consistent, standardised "umbrella" term.
        Your aim is to reduce redundancy and ensure that similar or synonymous terms are grouped under 
        a single standardised term to be used for labeling and categorization of student's preferences in a university database.

        Guidelines:
        1. The standardised term should be a concise and commonly understood representation of the concept.
        2. If an original term is already a good standard, it can map to itself.
        3. Group synonymous or similar terms under ONE standardised term. For example, if "Machine Learning", "ML", and "Deep Learning" are present, they might all map to "Machine Learning" or you might decide "Deep Learning" should map to "Deep Learning" if it's distinct enough, while "ML" maps to "Machine Learning". Use your best judgment to create meaningful umbrella terms.
        4. The output MUST be a single JSON object where keys are the *original* expertise terms from the input list, and values are their corresponding *standardised* umbrella terms. Every term from the input list must be a key in the output JSON.
        5. Do not include any explanatory text outside the JSON object. Just the JSON.

        List of unique expertise terms:
        {json.dumps(unique_terms_list)}

        Please provide the JSON mapping:
        """

    print("Sending request to Gemini API...")
    try:
        response = model.generate_content(prompt)
        # Gemini API can sometimes wrap JSON in markdown backticks
        cleaned_response_text = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        # Validate and parse JSON
        try:
            standardisation_map = json.loads(cleaned_response_text)
            # Basic validation: ensure it's a dict
            if not isinstance(standardisation_map, dict):
                print("Error: Gemini did not return a valid JSON dictionary.")
                print("Raw response:", response.text)
                return None
            # Ensure all original terms are keys
            missing_keys = [term for term in unique_terms_list if term not in standardisation_map]
            if missing_keys:
                print(f"Warning: Gemini's map is missing keys for: {missing_keys}")
                for key in missing_keys:
                    standardisation_map[key] = key # self-mapping
            return standardisation_map
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from Gemini: {e}")
            print("Raw response text from Gemini:")
            print(response.text) # print the raw response for debugging
            return None
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        if hasattr(e, 'response') and e.response: # More detailed error if available
            print(f"Gemini API Error Details: {e.response}")
        return None

def create_prompt_for_batch(batch_sentences_list, all_standardized_topics):
    sentences_json_for_prompt = json.dumps(batch_sentences_list, indent=2)
    prompt = f"""
        You are an expert AI assistant specialized in classifying student project preferences.
        Your task is to label a list of student preference sentences with relevant project topics, both positive and negative.
        You MUST use ONLY the topics from the provided standardized list.

        Standardized Topics List:
        {', '.join(all_standardized_topics)}

        Input Sentences for this batch (as a JSON array of objects):
        {sentences_json_for_prompt}

        Instructions:
        1.  For each sentence object in the input JSON array, analyze the "SentenceText".
        2.  Identify topics the student expresses a POSITIVE preference for.
        3.  Identify topics the student expresses a NEGATIVE preference for.
        4.  Topics MUST be chosen EXACTLY from the 'Standardized Topics List' above. Do not invent new topics or use variations. IF you are uncertain, label it as 'No Match'.
        5.  Your output MUST be a valid JSON array of objects.
        6.  Each object in your output array should correspond to an input sentence and have the following keys:
            *   "SentenceID": (string) The ID from the input sentence object.
            *   "Gemini_Positive_Topics": (comma separated values) A list of positive topics. If no positive topics, label it as 'No Match'.
            *   "Gemini_Negative_Topics": (comma separated values) A list of negative topics. If no negative topics, label it as 'No Match'.
        7.  Ensure every SentenceID from the input batch is present in your output JSON array.
        8.  Do NOT include the original 'SentenceText' in your output JSON, only the specified keys.

        Example of expected output JSON format:
        [
        {{
            "SentenceID": "S001",
            "Gemini_Positive_Topics": "Machine Learning", "Artificial Intelligence",
            "Gemini_Negative_Topics": "Web Development"
        }},
        {{
            "SentenceID": "S002",
            "Gemini_Positive_Topics": "Data Science",
            "Gemini_Negative_Topics": "No Match"
        }}
        ]

        Begin your JSON output now (ensure it's a single, valid JSON array for this batch):
        """
    return prompt

#region STANDARDISE TOPICS
# --- TASK 1: Standardize Topics ---
@shared_task
def standardize_all_topics():
    """
    Task 1: Extracts all supervisor expertise, gets a standardization map
    from Gemini, and saves it to the StandardisedTopic table.
    It no longer returns anything.
    """
    try:
        print("--- TASK: Standardize Topics [STARTED] ---")
        
        all_topics = set()
        supervisor_expertises = SupervisorProfile.objects.values_list('expertise', flat=True)
        print(f"Supervsisor Expertise: {supervisor_expertises}")
        pattern = r'"([^"]*)"'
        for expertise_str in supervisor_expertises:
            if expertise_str:
                topics_found = re.findall(pattern, expertise_str)
                for topic in topics_found:
                    topic = topic.strip()
                    if topic:
                        all_topics.add(topic)
        
        unique_terms_list = list(all_topics)
        print(f"Found {len(unique_terms_list)} unique topics to process.")

        model = genai.GenerativeModel("gemini-2.0-flash")
        
        standardisation_map = get_standardisation_map_from_gemini(unique_terms_list, model, prompt="")

        if not standardisation_map:
            raise Exception("Failed to generate standardisation map from Gemini.")

        for original_terms, standardised_term in standardisation_map.items():
            # Create or get the standardised topic
            standardised_topic, created = StandardisedTopic.objects.get_or_create(name=standardised_term)
            if created:
                print(f"Created new standardised topic: {standardised_term}")
            else:
                print(f"Standardised topic already exists: {standardised_term}")

            # Process each original term
            for original_term in original_terms.split(','):
                original_term = original_term.strip()
                if original_term:
                    original_topic, _ = OriginalTopic.objects.get_or_create(name=original_term)
                    standardised_topic.original_topics.add(original_topic)
                    print(f"Added '{original_term}' to standardised topic '{standardised_term}'.")

        with transaction.atomic():
            for supervisor in SupervisorProfile.objects.all():
                if supervisor.expertise:
                    # Find all original topic strings from the supervisor's expertise field
                    supervisor_topics = re.findall(pattern, supervisor.expertise)
                    
                    # Find the corresponding StandardisedTopic objects
                    topics_queryset = StandardisedTopic.objects.filter(
                        original_topics__name__in=supervisor_topics
                    ).distinct()
                    supervisor.standardised_expertise.set(topics_queryset)

        print("Topic mappings saved to the database.")
        print("--- TASK: Standardize Topics [SUCCESS] ---")

        # Final return value on success
        final_count = len(standardisation_map) if standardisation_map else 0
        message = f"Successfully standardized {final_count} topics."
        print(f"--- TASK: Standardize Topics [SUCCESS]: {message} ---")
        return {'status': 'SUCCESS', 'result': message}

    except Exception as e:
        print(f"!!! ERROR in standardize_all_topics task: {e}")
        raise

#region STUDENT LABELING
# --- TASK 2: Label Student Preferences ---
@shared_task
def label_student_preferences_for_semester(semester):
    """
    Task 2: Labels student preferences for a given semester.
    It now queries the database for standardized topics itself.
    """
    try:
        print(f"--- TASK: Label Preferences for semester {semester} [STARTED] ---")

        standardised_topics_qs = StandardisedTopic.objects.all()
        standardised_topics_list = list(standardised_topics_qs.values_list('name', flat=True))

        if not standardised_topics_list:
            raise ValueError("No standardized topics found in the database. "
                             "Please run the 'Standardize Topics' task first.")
        
        print(f"Loaded {len(standardised_topics_list)} standardized topics from the database.")

        students = StudentProfile.objects.filter(preference_text__isnull=False, semester=semester).order_by('user')
        if not students.exists():
            print("No students with preferences found for this semester. Task complete.")
            return

        # --- Configuration ---
        GEMINI_MODEL_NAME = "gemini-2.0-flash"
        API_RETRY_LIMIT = 3
        API_RETRY_DELAY_SECONDS = 5
        BATCH_SIZE = 50
        DELAY_BETWEEN_BATCHES_SECONDS = 2
        
        try:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set.")
            genai.configure(api_key=api_key)
        except Exception as e:
            print(f"Error configuring Gemini API: {e}")
            raise

        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        all_gemini_results = []

        num_batches = math.ceil(students.count() / BATCH_SIZE)
        print(f"Processing in {num_batches} batches of size up to {BATCH_SIZE}.")


        for i in range(num_batches):
            start_index = i * BATCH_SIZE
            end_index = start_index + BATCH_SIZE
            batch = students[start_index:end_index]

            print(f"\n--- Processing Batch {i+1}/{num_batches} ({len(batch)} sentences) ---")

            if not batch:
                print("Batch is empty, skipping.")
                continue

            # Prepare list of sentences for the current batch's prompt
            batch_sentences_to_label_list = []
            for student in batch:
                if not student.preference_text:
                    print(f"Warning: Student {student.student_id} has no preference text. Skipping.")
                    continue
                
                # Create a sentence object for the batch
                sentence_object = {
                    "SentenceID": str(student.student_id),
                    "SentenceText": student.preference_text.strip()
                }
                batch_sentences_to_label_list.append(sentence_object)

            batch_prompt = create_prompt_for_batch(batch_sentences_to_label_list, standardised_topics_list)
            gemini_output_json_str = None
            current_batch_results = None

            for attempt in range(API_RETRY_LIMIT):
                try:
                    print(f"Attempt {attempt + 1}/{API_RETRY_LIMIT} for batch {i+1}...")
                    response = model.generate_content(
                        batch_prompt,
                        generation_config=genai.types.GenerationConfig(
                            # temperature=0.1
                        )
                    )
                    if not response.parts:
                        if response.prompt_feedback and response.prompt_feedback.block_reason:
                            print(f"Warning: Prompt for batch {i+1} was blocked. Reason: {response.prompt_feedback.block_reason}")
                        else:
                            print(f"Warning: Gemini response for batch {i+1} has no parts.")
                        if attempt < API_RETRY_LIMIT - 1:
                            print(f"Retrying batch {i+1} in {API_RETRY_DELAY_SECONDS} seconds...")
                            time.sleep(API_RETRY_DELAY_SECONDS)
                            continue
                        else:
                            print(f"Max retries reached for problematic response for batch {i+1}. Skipping this batch.")
                            break # Break from retry loop for this batch

                    gemini_output_json_str = response.text.strip()

                    if gemini_output_json_str.startswith("```json"):
                        gemini_output_json_str = gemini_output_json_str[len("```json"):].strip()
                    if gemini_output_json_str.endswith("```"):
                        gemini_output_json_str = gemini_output_json_str[:-len("```")].strip()

                    first_char = gemini_output_json_str[0] if gemini_output_json_str else ''
                    last_char = gemini_output_json_str[-1] if gemini_output_json_str else ''
                    if not ((first_char == '[' and last_char == ']')):
                        json_start_index = gemini_output_json_str.find('[')
                        json_end_index = gemini_output_json_str.rfind(']')
                        if json_start_index != -1 and json_end_index > json_start_index :
                            gemini_output_json_str = gemini_output_json_str[json_start_index : json_end_index+1]
                        else:
                            raise ValueError("Could not reliably extract JSON array from Gemini response for this batch.")

                    current_batch_results = json.loads(gemini_output_json_str)
                    if not isinstance(current_batch_results, list):
                        raise ValueError("Gemini's output for batch was not a JSON list as expected.")
                    
                    print(f"Successfully processed batch {i+1}. Received {len(current_batch_results)} results.")
                    all_gemini_results.extend(current_batch_results)
                    break # Successful processing of this batch

                except json.JSONDecodeError as e:
                    print(f"Error parsing Gemini's JSON output for batch {i+1} (attempt {attempt+1}): {e}")
                    print("Raw output snippet:", gemini_output_json_str[:200] if gemini_output_json_str else "None")
                    if attempt < API_RETRY_LIMIT - 1:
                        time.sleep(API_RETRY_DELAY_SECONDS)
                    else:
                        print(f"Failed to parse JSON for batch {i+1} after {API_RETRY_LIMIT} attempts. Skipping this batch.")
                except Exception as e:
                    print(f"Error during Gemini API call or processing for batch {i+1} (attempt {attempt+1}): {e}")
                    if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                        print(f"Prompt Feedback: {response.prompt_feedback}")
                    if attempt < API_RETRY_LIMIT - 1:
                        time.sleep(API_RETRY_DELAY_SECONDS)
                    else:
                        print(f"Failed to process batch {i+1} after {API_RETRY_LIMIT} attempts. Skipping this batch.")
            
            # Optional: Add a small delay between batch calls to be polite to the API
            if i < num_batches - 1: # Don't sleep after the last batch
                print(f"Waiting {DELAY_BETWEEN_BATCHES_SECONDS}s before next batch...")
                time.sleep(DELAY_BETWEEN_BATCHES_SECONDS)

        if not all_gemini_results:
            print("\nNo results were successfully processed from Gemini. Exiting.")
            exit()

        print("\n--- Updating student profiles in the database ---")
        updated_student_count = 0
        with transaction.atomic():
            for result in all_gemini_results:
                sentence_id = result.get("SentenceID")
                
                # Get topic names as a list of strings, cleaning them up.
                # Handles both comma-separated strings and lists from the AI.
                raw_positive = result.get("Gemini_Positive_Topics", [])
                raw_negative = result.get("Gemini_Negative_Topics", [])

                positive_topic_names = [t.strip() for t in raw_positive.split(',') if t.strip()] if isinstance(raw_positive, str) else [t.strip() for t in raw_positive if t.strip()]
                negative_topic_names = [t.strip() for t in raw_negative.split(',') if t.strip()] if isinstance(raw_negative, str) else [t.strip() for t in raw_negative if t.strip()]

                if not sentence_id:
                    print("Warning: Result missing SentenceID, skipping this entry.")
                    continue

                try:
                    # Find the student profile. The `student_id` property is based on the email prefix.
                    student = StudentProfile.objects.get(user__email__startswith=f"{sentence_id}@")

                    # Find the StandardisedTopic objects that match the names from the AI
                    positive_topics_qs = standardised_topics_qs.filter(name__in=positive_topic_names)
                    negative_topics_qs = standardised_topics_qs.filter(name__in=negative_topic_names)

                    # Use .set() to update the ManyToMany relationships.
                    # This clears old relations and adds the new ones.
                    student.positive_preferences.set(positive_topics_qs)
                    student.negative_preferences.set(negative_topics_qs)
                    
                    updated_student_count += 1

                except StudentProfile.DoesNotExist:
                    print(f"Warning: Student with ID '{sentence_id}' does not exist. Skipping.")
                except StudentProfile.MultipleObjectsReturned:
                    print(f"Warning: Multiple students found for ID prefix '{sentence_id}'. Skipping to avoid data corruption.")
        
        print(f"Successfully updated preferences for {updated_student_count} students.")

        # Return the results
        print("--- TASK: Label Preferences [SUCCESS] ---")
        message = f"Successfully labeled preferences for {students.count()} students in semester {semester}."
        print(f"--- TASK: Label Preferences [SUCCESS]: {message} ---")
        return {'status': 'SUCCESS', 'result': message}

    except Exception as e:
        print(f"!!! ERROR in label_student_preferences task: {e}")
        raise

#region OPTIMAL MATCHING
from pulp import LpProblem, LpVariable, LpMaximize, lpSum, LpBinary
import pandas as pd

def get_preferences_list(preferences_manager):
    return list(preferences_manager.all().values_list('name', flat=True))

#region OPTIMAL MATCHING
# --- TASK 3: Match Students to Supervisors ---
@shared_task
def match_students_for_semester(semester, weightage):
    try:
        print(f"--- TASK: Allocate Students for semester {Semester.objects.get(pk=semester)} [STARTED] ---")

        # Find unassigned students in the given semester who have a preference
        students = StudentProfile.objects.filter(
            semester=semester, 
            supervisor__isnull=True,
            preference_text__isnull=False
        ).distinct()

        if not students.exists():
            raise ValueError("No unassigned students with labeled preferences found for this semester. "
                             "Please run the 'Label Student Preferences' task first.")

        students_no_label_count = StudentProfile.objects.filter(
            semester=semester, 
            supervisor__isnull=True,
            positive_preferences__isnull=True
        ).count()

        if students_no_label_count > 0:
            print(f"Warning: There are {students_no_label_count} unassigned students who have no labels. They will be ignored in this matching process.")

        supervisors = SupervisorProfile.objects.filter(
            accepting_students=True
        ).annotate(
            current_student_count=Count('students'),
            remaining_capacity=F('supervision_capacity') - Count('students')
        ).filter(
            remaining_capacity__gt=0 # Only include supervisors with available slots
        )

        total_available_capacity = supervisors.aggregate(total_capacity=Sum('remaining_capacity'))['total_capacity'] or 0
        if total_available_capacity < students.count():
            raise ValueError(f"There is not enough supervisor capacity ({total_available_capacity}) to allocate all students ({students.count()}).")


        students_data = []
        for student in students:
            students_data.append({
                "student_id": student.student_id,
                "programme": student.programme.name,
                "positive_preferences": get_preferences_list(student.positive_preferences),
                "negative_preferences": get_preferences_list(student.negative_preferences)
            })
        students_df = pd.DataFrame(students_data)

        supervisors_data = []
        for supervisor in supervisors:
            supervisors_data.append({
                "supervisor_id": supervisor.user.email,
                "name": supervisor.user.full_name,
                "programme_first_choice": list(supervisor.preferred_programmes_first_choice.programme.all().values_list('name', flat=True)) if supervisor.preferred_programmes_first_choice else [],
                "programme_second_choice": list(supervisor.preferred_programmes_second_choice.programme.all().values_list('name', flat=True)) if supervisor.preferred_programmes_second_choice else [],
                "capacity": supervisor.remaining_capacity,
                "student_count": supervisor.current_student_count,
                "expertise": get_preferences_list(supervisor.standardised_expertise)
            })
        supervisors_df = pd.DataFrame(supervisors_data)
        assignments = optimal_matching(students_df,supervisors_df,float(weightage))
        all_topics_map = {topic.name: topic for topic in StandardisedTopic.objects.all()}

        assignments_df = pd.DataFrame(assignments)
        assignments_csv_path = f"assignments_semester_{semester}.csv"
        assignments_df.to_csv(assignments_csv_path, index=False)
        print(f"Assignments saved to {assignments_csv_path}")

        with transaction.atomic(): # Use a transaction for safer, faster updates
            for assignment in assignments:
                if not assignment.get('student_id') or not assignment.get('supervisor_id'):
                    print(f"Warning: Skipping assignment with missing student or supervisor ID: {assignment}")
                    continue
                try:
                    student = StudentProfile.objects.select_for_update().get(user__email__startswith=f"{assignment['student_id']}@")
                    supervisor = SupervisorProfile.objects.get(user__email=assignment['supervisor_id'])

                    matching_topic_names = assignment.get('matching_topics', [])
                    conflicting_topic_names = assignment.get('conflicting_topics', [])

                    matching_topic_objects = [all_topics_map[name] for name in matching_topic_names if name in all_topics_map]
                    conflicting_topic_objects = [all_topics_map[name] for name in conflicting_topic_names if name in all_topics_map]

                    student.matching_topics.set(matching_topic_objects)
                    student.conflicting_topics.set(conflicting_topic_objects)
                    
                    student.supervisor = supervisor
                    student.programme_match_type = assignment['programme_match']
                    
                    student.save()

                except StudentProfile.DoesNotExist:
                    print(f"Warning: Could not find student with ID {assignment['student_id']}. Skipping assignment.")
                except SupervisorProfile.DoesNotExist:
                    print(f"Warning: Could not find supervisor with ID {assignment['supervisor_id']}. Skipping assignment for student {assignment['student_id']}.")
            message = f"Successfully match {students.count()} students in semester {Semester.objects.get(pk=semester)} to {supervisors.count()} supervisors."
            return {'status': 'SUCCESS', 'result': message}
        
    except Exception as e:
        print(f"!!! ERROR in match_student_preferences task: {e}")
        raise
        
def optimal_matching(students_df, supervisors_df, balancing_penalty_weight=5, score_weights={
        'prog_first_choice': 20.0,
        'prog_second_choice': 10.0,
        'student_topic_satisfaction': 50.0
    }):

    # --- 1. Pre-calculate a Unified Score for Each (Student, Supervisor) Pair ---
    # This step implements the M_r and M_Sij logic before defining the optimization problem.
    all_pair_scores = {}
    for _, student in students_df.iterrows():
        s_id = student['student_id']
        for _, supervisor in supervisors_df.iterrows():
            v_id = supervisor['supervisor_id']
            
            # --- Supervisor's Program Preference Score (implements M_r) ---
            prog_score = 0
            # Treat "No Preference" as a universal match for that choice level.
            if not supervisor.get('programme_first_choice', []) or \
               student['programme'] in supervisor.get('programme_first_choice', []):
                prog_score = score_weights.get('prog_first_choice', 10.0)
            elif not supervisor.get('programme_second_choice', []) or \
                 student['programme'] in supervisor.get('programme_second_choice', []):
                prog_score = score_weights.get('prog_second_choice', 5.0)

            # --- Student's Topic Preference Score (implements M_Sij) ---
            # Positive Match Ratio = |P_i ∩ E_j| / |P_i|
            pos_prefs = student.get('positive_preferences', [])
            num_pos_prefs = len(pos_prefs)
            num_pos_matches = sum(1 for topic in pos_prefs if topic in supervisor.get('expertise', []))
            positive_match_ratio = (num_pos_matches / num_pos_prefs) if num_pos_prefs > 0 else 1.0

            # Negative Avoidance Success Rate = 1 - (|N_i ∩ E_j| / |N_i|)
            neg_prefs = student.get('negative_preferences', [])
            num_neg_prefs = len(neg_prefs)
            num_neg_violations = sum(1 for topic in neg_prefs if topic in supervisor.get('expertise', []))
            violation_rate = (num_neg_violations / num_neg_prefs) if num_neg_prefs > 0 else 0.0
            negative_avoidance_rate = 1.0 - violation_rate
            
            # The M_Sij score is the average of the two components above.
            m_sij_score = (positive_match_ratio + negative_avoidance_rate) / 2.0
            
            # Weight the student's overall topic satisfaction score.
            student_topic_score = score_weights.get('student_topic_satisfaction', 50.0) * m_sij_score

            # --- Final Combined Score for the pair (s_i, r_j) ---
            final_score = prog_score + student_topic_score
            all_pair_scores[(s_id, v_id)] = final_score

    # --- 2. Define the Optimization Problem ---
    problem = LpProblem("Optimal_Student_Supervisor_Matching", LpMaximize)

    # Decision Variables: x_ij = 1 if student i is assigned to supervisor j
    decision_vars = LpVariable.dicts("x", all_pair_scores.keys(), 0, 1, LpBinary)

    # --- 3. Workload Balancing (Soft Constraint) ---
    num_new_students = len(students_df)
    num_existing_students = supervisors_df['student_count'].sum()
    num_supervisors = len(supervisors_df)
    target_load = (num_existing_students + num_new_students) / num_supervisors if num_supervisors > 0 else 0
    print(f"\nTarget total load per supervisor (existing + new): {target_load:.2f}")

    # Variables to measure deviation from the target load (linearizes the penalty)
    dev_over = LpVariable.dicts("DeviationOver", [s['supervisor_id'] for _, s in supervisors_df.iterrows()], lowBound=0)
    dev_under = LpVariable.dicts("DeviationUnder", [s['supervisor_id'] for _, s in supervisors_df.iterrows()], lowBound=0)

    for _, supervisor in supervisors_df.iterrows():
        v_id = supervisor['supervisor_id']
        existing_load = supervisor.get('student_count', 0)
        newly_assigned_load = lpSum(decision_vars[(s_id, v_id)] for s_id in students_df['student_id'])
        problem += (existing_load + newly_assigned_load) - target_load == dev_over[v_id] - dev_under[v_id], f"Define_Deviation_{v_id}"

    # --- 4. Objective Function ---
    # Maximize the sum of scores for all assignments, minus a penalty for workload imbalance.
    satisfaction_score = lpSum(decision_vars[key] * all_pair_scores[key] for key in all_pair_scores)
    workload_penalty = balancing_penalty_weight * lpSum(dev_over[v_id] + dev_under[v_id] for v_id in supervisors_df['supervisor_id'])
    
    problem += satisfaction_score - workload_penalty, "Maximize_Satisfaction_and_Balance"

    # --- 5. Hard Constraints ---
    # Constraint 1: Each student must be assigned to exactly ONE supervisor.
    for s_id in students_df['student_id']:
        problem += lpSum(decision_vars[(s_id, v_id)] for v_id in supervisors_df['supervisor_id']) == 1, f"Assign_Student_{s_id}"

    # Constraint 2: Each supervisor cannot exceed their maximum capacity.
    for _, supervisor in supervisors_df.iterrows():
        v_id = supervisor['supervisor_id']
        # The number of *newly assigned* students cannot exceed the remaining capacity.
        remaining_capacity = supervisor.get('capacity', 0)
        problem += lpSum(decision_vars[(s_id, v_id)] for s_id in students_df['student_id']) <= remaining_capacity, f"Capacity_Supervisor_{v_id}"

    problem.solve()

    # --- Result Extraction ---
    assignments = []
    if problem.status == 1: # If an optimal solution was found
        for key, var in decision_vars.items():
            if var.value() > 0.5: # If assignment was made
                student_id, supervisor_id = key
                
                # Retrieve student and supervisor info for detailed reporting
                student = students_df[students_df['student_id'] == student_id].iloc[0]
                supervisor = supervisors_df[supervisors_df['supervisor_id'] == supervisor_id].iloc[0]

                # Determine match details for reporting
                programme_match_type = 0
                if not supervisor.get('programme_first_choice', []) or student['programme'] in supervisor.get('programme_first_choice', []):
                    programme_match_type = 1
                elif not supervisor.get('programme_second_choice', []) or student['programme'] in supervisor.get('programme_second_choice', []):
                    programme_match_type = 2

                matching_topics = [t for t in student.get('positive_preferences', []) if t in supervisor.get('expertise', [])]
                conflicting_topics = [t for t in student.get('negative_preferences', []) if t in supervisor.get('expertise', [])]
                
                assignments.append({
                    'student_id': student_id,
                    'supervisor_id': supervisor_id,
                    'supervisor_name': supervisor.get('name', 'N/A'),
                    'programme_match': programme_match_type, # 1 for first choice, 2 for second, 0 for other
                    'matching_topics': matching_topics if matching_topics else ["No Matches"],
                    'conflicting_topics': conflicting_topics if conflicting_topics else ["No Conflicts"],
                    'match_score': all_pair_scores[key] # Report the exact score used by the optimizer
                })
    return assignments

def safe_list(val):
    if isinstance(val, list):
        return val
    if isinstance(val, float) or pd.isna(val):
        return []
    if isinstance(val, str):
        try:
            # Try to parse stringified list
            if val.strip().startswith("[") and val.strip().endswith("]"):
                parsed = eval(val)
                if isinstance(parsed, list):
                    return [str(t).strip() for t in parsed if str(t).strip()]
            # Otherwise, split by comma or semicolon
            return [t.strip() for t in val.split(',') if t.strip()]
        except Exception:
            return [val.strip()] if val.strip() else []
    return []

#region RESET STUFF
@shared_task
def reset_students_for_semester(semester):
    """
    Resets student allocations for a given semester.
    """
    try:
        semester_instance = Semester.objects.get(pk=semester)
        print(f"--- TASK: Reset Students for semester {semester_instance} [STARTED] ---")

        students_to_reset = StudentProfile.objects.filter(semester=semester_instance)

        if not students_to_reset.exists():
            print(f"No students found for semester {semester_instance}. Task complete.")
            return {'status': 'SUCCESS', 'result': f"No students found for semester {semester_instance}."}

        with transaction.atomic():
            # Step 1: Clear the ManyToManyFields.
            MatchingTopicsThroughModel = StudentProfile.matching_topics.through # Get the intermediate model for the 'matching_topics' relationship
            MatchingTopicsThroughModel.objects.filter(studentprofile__in=students_to_reset).delete() # Delete all links where the student is in our target queryset
            ConflictingTopicsThroughModel = StudentProfile.conflicting_topics.through
            ConflictingTopicsThroughModel.objects.filter(studentprofile__in=students_to_reset).delete()
            
            # Step 2: Update the simple ForeignKey and IntegerField fields in a single bulk query.
            students_to_reset.update(
                supervisor=None,
                programme_match_type=None
            )
        
        message = f"Successfully reset allocations for {students_to_reset.count()} students in semester {semester_instance}."
        print(f"--- TASK [SUCCESS]: {message} ---")
        return {'status': 'SUCCESS', 'result': message}

    except Semester.DoesNotExist:
        message = f"!!! ERROR: Semester with ID {semester} does not exist."
        print(message)
        # Depending on if it's a Celery task, you might want to raise the error
        # or return a failure status. For now, just raising.
        raise
    except Exception as e:
        # The original code had a typo here, fixed to be more specific.
        print(f"!!! ERROR in reset_students_for_semester task: {e}")
        raise

@shared_task
def reset_topic_mappings():
    try:
        print(f"--- TASK: Reset Topic Mappings [STARTED] ---")
        StandardisedTopic.objects.all().delete()
        message = f"Successfully reset all topic mappings."
        return {'status': 'SUCCESS', 'result': message}

    except Exception as e:
        print(f"!!! ERROR in match_student_preferences task: {e}")
        raise