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


class ContactTag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='contact_tags')
    name = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name


class Contact(models.Model):
    contact_list = models.ForeignKey(ContactList, on_delete=models.CASCADE, related_name='contacts')
    email = models.EmailField()
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    tags = models.ManyToManyField(ContactTag, blank=True, related_name='contacts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('contact_list', 'email')
        ordering = ['email']

    def __str__(self):
        return self.email

    @staticmethod
    def parse_tags(raw_tags: str) -> list[str]:
        if not raw_tags:
            return []
        cleaned: list[str] = []
        for token in raw_tags.replace(';', ',').split(','):
            tag = token.strip()
            if not tag:
                continue
            normalized = ' '.join(tag.split())
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned