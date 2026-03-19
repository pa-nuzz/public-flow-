from django.db import models
from django.conf import settings

class ContactList(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contact_lists')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_email_list(self):
        return list(self.contacts.filter(is_active=True).values_list('email', flat=True))


class Contact(models.Model):
    contact_list = models.ForeignKey(ContactList, on_delete=models.CASCADE, related_name='contacts')
    email = models.EmailField()
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('contact_list', 'email')
        ordering = ['email']

    def __str__(self):
        return self.email