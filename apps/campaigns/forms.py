from django import forms
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import Campaign
from apps.senders.models import Sender

class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ['name', 'subject', 'from_name', 'reply_to', 'recipient_emails', 'body_text', 'sender', 'scheduled_at']
        widgets = {
            'recipient_emails': forms.Textarea(attrs={'rows': 4}),
            'body_text': forms.Textarea(attrs={'rows': 7}),
            'scheduled_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['scheduled_at'].input_formats = ['%Y-%m-%dT%H:%M']
        if user:
            self.fields['sender'].queryset = Sender.objects.filter(user=user, is_active=True)

    def clean_recipient_emails(self):
        value = (self.cleaned_data.get('recipient_emails') or '').strip()
        if not value:
            return ''

        cleaned = []
        for item in value.replace(';', ',').replace('\n', ',').split(','):
            email = item.strip().lower()
            if not email:
                continue
            try:
                validate_email(email)
            except ValidationError:
                raise forms.ValidationError(f'Invalid recipient email: {email}')
            if email not in cleaned:
                cleaned.append(email)
        return ', '.join(cleaned)

    def clean(self):
        cleaned_data = super().clean()
        body_text = (cleaned_data.get('body_text') or '').strip()
        if not body_text:
            raise forms.ValidationError('Message content is required.')
        return cleaned_data
