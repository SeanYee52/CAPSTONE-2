from django.contrib import admin
from .models import OriginalTopic, StandardisedTopic

# Register your models here.
admin.site.register(
    [
        OriginalTopic,
        StandardisedTopic,
    ]
)