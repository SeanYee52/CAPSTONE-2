from django.db import models

# Create your models here.

class OriginalTopic(models.Model):
    name = models.CharField(max_length=255, unique=True)
    standardised_topic = models.ForeignKey(
        'StandardisedTopic',
        on_delete=models.SET_NULL,
        null=True,
        related_name='original_topics'
    )

    def __str__(self):
        return self.name
    
class StandardisedTopic(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
