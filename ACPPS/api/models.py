from django.db import models

# Create your models here.
class TopicMapping(models.Model):
    topic = models.CharField(max_length=255, unique=True)
    standardised_topic = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.topic