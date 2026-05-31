from django.contrib import admin
from apps.contacts.models import Contact, ContactList, ContactTag


@admin.register(ContactList)
class ContactListAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'contact_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'user']
    search_fields = ['name', 'user__email', 'description']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']

    def contact_count(self, obj):
        return obj.contacts.count()
    contact_count.short_description = 'Contacts'


@admin.register(ContactTag)
class ContactTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'contact_count', 'created_at']
    list_filter = ['created_at', 'user']
    search_fields = ['name', 'user__email']
    ordering = ['name']

    def contact_count(self, obj):
        return obj.contacts.count()
    contact_count.short_description = 'Contacts'


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['email', 'first_name', 'last_name', 'contact_list', 'is_active', 'tag_list', 'created_at']
    list_filter = ['is_active', 'created_at', 'contact_list', 'tags']
    search_fields = ['email', 'first_name', 'last_name', 'contact_list__name']
    ordering = ['-created_at']
    filter_horizontal = ['tags']
    readonly_fields = ['created_at']

    def tag_list(self, obj):
        return ', '.join(tag.name for tag in obj.tags.all())
    tag_list.short_description = 'Tags'
