# Generated by Django 5.2.1 on 2025-07-18 02:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
        ('users', '0009_remove_coordinatorprofile_role_scope_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='supervisorprofile',
            name='standardised_expertise',
        ),
        migrations.AddField(
            model_name='supervisorprofile',
            name='standardised_expertise',
            field=models.ManyToManyField(blank=True, related_name='supervisors', to='api.topicmapping'),
        ),
    ]
