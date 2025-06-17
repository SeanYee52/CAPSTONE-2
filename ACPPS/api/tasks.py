# api/tasks.py
from celery import shared_task
import google.generativeai as genai
import json
import os
import re
import math
import time

from .models import TopicMapping
from users.models import StudentProfile, SupervisorProfile

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
        4.  Topics MUST be chosen EXACTLY from the 'Standardized Topics List' above. Do not invent new topics or use variations. IF there is NO MATCH, label it as 'No Match'.
        5.  Your output MUST be a valid JSON array of objects.
        6.  Each object in your output array should correspond to an input sentence and have the following keys:
            *   "SentenceID": (string) The ID from the input sentence object.
            *   "Gemini_Positive_Topics": (array of strings) A list of positive topics. If no positive topics, label it as 'No Match'.
            *   "Gemini_Negative_Topics": (array of strings) A list of negative topics. If no negative topics, label it as 'No Match'.
        7.  Ensure every SentenceID from the input batch is present in your output JSON array.
        8.  Do NOT include the original 'SentenceText' in your output JSON, only the specified keys.

        Example of expected output JSON format:
        [
        {{
            "SentenceID": "S001",
            "Gemini_Positive_Topics": ["Machine Learning", "Artificial Intelligence"],
            "Gemini_Negative_Topics": ["Web Development"]
        }},
        {{
            "SentenceID": "S002",
            "Gemini_Positive_Topics": ["Data Science"],
            "Gemini_Negative_Topics": []
        }}
        ]

        Begin your JSON output now (ensure it's a single, valid JSON array for this batch):
        """
    return prompt

# --- TASK 1: Standardize Topics ---
@shared_task
def standardize_all_topics():
    """
    Task 1: Extracts all supervisor expertise, gets a standardization map
    from Gemini, and saves it to the TopicMapping table.
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

        for original_term, standardised_term in standardisation_map.items():
            TopicMapping.objects.update_or_create(
                topic=original_term,
                defaults={'standardised_topic': standardised_term}
            )
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

# --- TASK 2: Label Student Preferences ---
@shared_task
def label_student_preferences_for_semester(semester):
    """
    Task 2: Labels student preferences for a given semester.
    It now queries the database for standardized topics itself.
    """
    try:
        print(f"--- TASK: Label Preferences for semester {semester} [STARTED] ---")

        standardised_topics = list(TopicMapping.objects.values_list('standardised_topic', flat=True).distinct())

        if not standardised_topics:
            raise ValueError("No standardized topics found in the database. "
                             "Please run the 'Standardize Topics' task first.")
        
        print(f"Loaded {len(standardised_topics)} standardized topics from the database.")

        students = StudentProfile.objects.filter(preference_text__isnull=False, semester=semester).order_by('id')
        if not students.exists():
            print("No students with preferences found for this semester. Task complete.")
            return

        # --- Configuration ---
        GEMINI_MODEL_NAME = "gemini-2.0-flash"
        # STUDENT_PREFERENCES_CSV = "data\\claude_sentences.csv"
        # STANDARDIZED_TOPICS_CSV = "data\\unique_standardised_topics.csv"
        # OUTPUT_CSV_WITH_GEMINI_LABELS = "data\\gemini_labeled_preferences.csv"
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
        all_gemini_results = [] # To store results from all batches

        num_batches = math.ceil(students.count() / BATCH_SIZE)
        print(f"Processing in {num_batches} batches of size up to {BATCH_SIZE}.")


        for i in range(num_batches):
            start_index = i * BATCH_SIZE
            end_index = start_index + BATCH_SIZE
            batch = students[start_index:end_index]

            print(f"\n--- Processing Batch {i+1}/{num_batches} ({len(batch)} sentences) ---")

            if batch.empty:
                print("Batch is empty, skipping.")
                continue

            # Prepare list of sentences for the current batch's prompt
            batch_sentences_to_label_list = []
            for student in batch:
                if not student.preference:
                    print(f"Warning: Student {student.id} has no preference text. Skipping.")
                    continue
                
                # Create a sentence object for the batch
                sentence_object = {
                    "SentenceID": str(student.id),
                    "SentenceText": student.preference.strip()
                }
                batch_sentences_to_label_list.append(sentence_object)

            batch_prompt = create_prompt_for_batch(batch_sentences_to_label_list, standardised_topics)

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

        for result in all_gemini_results:
            sentence_id = result.get("SentenceID")
            positive_topics = result.get("Gemini_Positive_Topics", [])
            negative_topics = result.get("Gemini_Negative_Topics", [])

            if not sentence_id:
                print("Warning: Result missing SentenceID, skipping this entry.")
                continue

            try:
                student = StudentProfile.objects.get(id=sentence_id)
                student.positive_preferences = positive_topics
                student.negative_preferences = negative_topics
                student.save()
            except StudentProfile.DoesNotExist:
                print(f"Warning: Student with ID {sentence_id} does not exist. Skipping this entry.")

        # Return the results
        print("--- TASK: Label Preferences [SUCCESS] ---")
        message = f"Successfully labeled preferences for {student_count} students in semester {semester}."
        print(f"--- TASK: Label Preferences [SUCCESS]: {message} ---")
        return {'status': 'SUCCESS', 'result': message}

    except Exception as e:
        print(f"!!! ERROR in label_student_preferences task: {e}")
        raise