from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.

# create a function
def home(request):
    
    return HttpResponse("<h1>Welcome to GeeksforGeeks</h1>")