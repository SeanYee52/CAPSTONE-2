from django.db import models

# Create your models here.

class School(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Department(models.Model):
    name = models.CharField(max_length=100)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='departments')

    def __str__(self):
        return f"{self.name} ({self.school.name})"


class Programme(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='programmes')

    def __str__(self):
        return f"{self.name} ({self.department.name})"
