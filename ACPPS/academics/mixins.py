from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages

class CoordinatorRequiredMixin(UserPassesTestMixin):
    """
    Ensures the user is logged in and belongs to the 'Coordinator' group.
    """
    def test_func(self):
        return self.request.user.is_authenticated and \
               self.request.user.groups.filter(name='Coordinator').exists()

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to access this page.")
        if not self.request.user.is_authenticated:
            return redirect('login')
        return redirect('/')