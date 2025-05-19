from .models import Post
from django.views.generic import ListView

class HomeView(ListView):
    model = Post
    template_name = 'home.html'