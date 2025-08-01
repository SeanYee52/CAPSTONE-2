# Generated by Django 5.2.1 on 2025-07-18 03:53

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_originaltopic_standardisedtopic_delete_topicmapping'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='standardisedtopic',
            name='original_topics',
        ),
        migrations.AddField(
            model_name='originaltopic',
            name='standardised_topic',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='original_topics', to='api.standardisedtopic'),
        ),
    ]
