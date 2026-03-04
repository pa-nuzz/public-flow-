from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            "class": "auth-input",
            "placeholder": "First Name"
        })
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            "class": "auth-input",
            "placeholder": "Last Name"
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "auth-input",
            "placeholder": "Email Address"
        })
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"] # Set username to email
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "class": "auth-input",
            "placeholder": "Email"
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "auth-input",
            "placeholder": "Password"
        })
    )