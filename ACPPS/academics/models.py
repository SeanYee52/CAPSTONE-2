from django.db import models

# Create your models here.

class Faculty(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class School(models.Model):
    name = models.CharField(max_length=100)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='schools', null=True, blank=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=100)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='departments', null=True, blank=True)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='departments', null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.school.name if self.school else self.faculty.name if self.faculty else 'No School or Faculty'})"


class Programme(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='programmes')

    def __str__(self):
        return f"{self.name} ({self.department.name})"
    

class ProgrammePreferenceGroup(models.Model):
    name = models.CharField(max_length=100)
    programme = models.ManyToManyField(Programme, blank=True, related_name='preference_groups')

    def __str__(self):
        return f"{self.name}"