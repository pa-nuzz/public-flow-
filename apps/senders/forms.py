from django import forms
from .models import Sender

class SenderForm(forms.ModelForm):
    smtp_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'SMTP Password / App Password'}),
        label='SMTP Password'
    )
    
    class Meta:
        model = Sender
        fields = ['display_name', 'from_email', 'provider', 'smtp_host', 'smtp_port', 'username', 'use_tls', 'daily_limit']
    
    def clean_smtp_port(self):
        port = self.cleaned_data['smtp_port']
        if port not in [25, 465, 587, 2525]:
            raise forms.ValidationError("Port must be 25, 465, 587, or 2525.")
        return port
