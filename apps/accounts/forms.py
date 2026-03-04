from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary",
            "placeholder": "Email"
        })
    )

    class Meta:
        model = User
        fields = ["email", "password1", "password2"]


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary",
            "placeholder": "Email"
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary",
            "placeholder": "Password"
        })
    )