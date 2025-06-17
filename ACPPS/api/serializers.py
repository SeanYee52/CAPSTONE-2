from rest_framework import serializers
from users.models import StudentProfile, SupervisorProfile
from .models import TopicMapping

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentProfile
        fields = ['student_id', 'preference_text', 'positive_preferences', 'negative_preferences']
        read_only_fields = ['student_id', 'preference_text']

    def update(self, instance, validated_data):
        # Ensure that student_id and preference_text are not updated
        validated_data.pop('student_id', None)
        validated_data.pop('preference_text', None)
        return super().update(instance, validated_data)

class SupervisorSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupervisorProfile
        fields = [
            'user', 
            'preferred_programmes_first_choice', 
            'preferred_programmes_second_choice', 
            'expertise', 
            'supervision_capacity',
            'standardised_expertise'
        ]
        read_only_fields = ['user', 'preferred_programmes_first_choice', 'preferred_programmes_second_choice', 'expertise', 'supervision_capacity'] 
        

class TopicMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicMapping
        fields = ['topic', 'standardised_topic']
        read_only_fields = ['topic'] 