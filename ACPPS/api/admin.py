from django.contrib import admin
from .models import TopicMapping

# Register your models here.
admin.site.register(
    [
        TopicMapping,
    ]
)