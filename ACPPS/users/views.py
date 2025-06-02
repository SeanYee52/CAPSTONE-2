from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.contrib.auth import authenticate

# Create your views here.
def register(request):
    if request.method == 'POST':
        # Handle registration logic here
        pass
    return render(request, 'users/register.html')

def login(request):
    if request.method == 'POST':
        # Handle login logic here
        pass
    return render(request, 'users/login.html')