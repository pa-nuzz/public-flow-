from django import forms
from apps.accounts.models import User
from django.contrib.auth.forms import PasswordChangeForm

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'company', 'bio', 'avatar']

class ChangePasswordForm(PasswordChangeForm):
    pass
