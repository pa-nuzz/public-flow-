from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.core.paginator import Paginator
from .models import Contact, ContactList, ContactTag
import csv
import io


@login_required
def contacts_home(request):
    contact_lists = ContactList.objects.filter(user=request.user).annotate(contact_count=Count('contacts'))
    available_tags = ContactTag.objects.filter(user=request.user)

    # Base queryset with optimized queries
    contacts_qs = Contact.objects.filter(
        contact_list__user=request.user
    ).select_related('contact_list').prefetch_related('tags').order_by('-created_at')

    # List filter (from clicking on a list card)
    selected_list_id = request.GET.get('list_id', '').strip()
    selected_list = None
    if selected_list_id and selected_list_id.isdigit():
        selected_list = get_object_or_404(ContactList, id=selected_list_id, user=request.user)
        contacts_qs = contacts_qs.filter(contact_list=selected_list)

    # Tag filter
    selected_tag_id = request.GET.get('tag_id', '').strip()
    selected_tag = None
    if selected_tag_id and selected_tag_id.isdigit():
        selected_tag = get_object_or_404(ContactTag, id=selected_tag_id, user=request.user)
        contacts_qs = contacts_qs.filter(tags=selected_tag)

    # Search filter
    search = request.GET.get('q', '').strip()
    if search:
        contacts_qs = contacts_qs.filter(email__icontains=search)

    total = contacts_qs.count()

    # Pagination
    paginator = Paginator(contacts_qs, 25)  # 25 contacts per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'contacts/contacts_home.html', {
        'contact_lists': contact_lists,
        'available_tags': available_tags,
        'all_contacts': page_obj.object_list,
        'page_obj': page_obj,
        'total': total,
        'search': search,
        'selected_list': selected_list,
        'selected_tag': selected_tag,
    })


@login_required
def tags_manager(request):
    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()

        if action == 'create':
            name = (request.POST.get('name') or '').strip()
            if not name:
                messages.error(request, 'Tag name is required.')
                return redirect('contacts:tags_manager')

            tag_obj, created = ContactTag.objects.get_or_create(user=request.user, name=name)
            if created:
                messages.success(request, f'Tag "{tag_obj.name}" created.')
            else:
                messages.warning(request, f'Tag "{tag_obj.name}" already exists.')
            return redirect('contacts:tags_manager')

        if action == 'rename':
            tag_id = request.POST.get('tag_id')
            new_name = (request.POST.get('new_name') or '').strip()
            if not tag_id or not new_name:
                messages.error(request, 'Tag and new name are required.')
                return redirect('contacts:tags_manager')

            tag_obj = get_object_or_404(ContactTag, id=tag_id, user=request.user)
            if ContactTag.objects.filter(user=request.user, name=new_name).exclude(id=tag_obj.id).exists():
                messages.error(request, f'Tag "{new_name}" already exists.')
                return redirect('contacts:tags_manager')

            old_name = tag_obj.name
            tag_obj.name = new_name
            tag_obj.save(update_fields=['name'])
            messages.success(request, f'Tag "{old_name}" renamed to "{new_name}".')
            return redirect('contacts:tags_manager')

        if action == 'delete':
            tag_id = request.POST.get('tag_id')
            if not tag_id:
                messages.error(request, 'Tag is required.')
                return redirect('contacts:tags_manager')

            tag_obj = get_object_or_404(ContactTag, id=tag_id, user=request.user)
            name = tag_obj.name
            tag_obj.delete()
            messages.success(request, f'Tag "{name}" deleted.')
            return redirect('contacts:tags_manager')

        messages.error(request, 'Invalid action.')
        return redirect('contacts:tags_manager')

    tags = ContactTag.objects.filter(user=request.user).annotate(contact_count=Count('contacts')).order_by('name')
    return render(request, 'contacts/tags_manager.html', {'tags': tags})


@login_required
def bulk_update_contact_tags(request):
    if request.method != 'POST':
        return redirect('contacts:list')

    operation = (request.POST.get('operation') or '').strip()
    raw_ids = (request.POST.get('selected_contact_ids') or '').strip()
    tag_ids = request.POST.getlist('tag_ids')

    if not raw_ids:
        messages.error(request, 'Select at least one contact.')
        return redirect('contacts:list')

    selected_ids: list[int] = []
    for token in raw_ids.split(','):
        token = token.strip()
        if not token:
            continue
        if token.isdigit():
            selected_ids.append(int(token))

    if not selected_ids:
        messages.error(request, 'Select at least one valid contact.')
        return redirect('contacts:list')

    contacts = Contact.objects.filter(id__in=selected_ids, contact_list__user=request.user).distinct()
    selected_count = contacts.count()
    if selected_count == 0:
        messages.error(request, 'No valid contacts found for this action.')
        return redirect('contacts:list')

    selected_tags = ContactTag.objects.filter(user=request.user, id__in=tag_ids)
    selected_tag_count = selected_tags.count()

    if operation in {'add', 'replace', 'remove'} and selected_tag_count == 0:
        messages.error(request, 'Select at least one tag for this action.')
        return redirect('contacts:list')

    if operation == 'add':
        for contact in contacts:
            contact.tags.add(*selected_tags)
        messages.success(request, f'Added {selected_tag_count} tag(s) to {selected_count} contact(s).')
        return redirect('contacts:list')

    if operation == 'replace':
        for contact in contacts:
            contact.tags.set(selected_tags)
        messages.success(request, f'Replaced tags for {selected_count} contact(s).')
        return redirect('contacts:list')

    if operation == 'remove':
        for contact in contacts:
            contact.tags.remove(*selected_tags)
        messages.success(request, f'Removed selected tag(s) from {selected_count} contact(s).')
        return redirect('contacts:list')

    if operation == 'clear':
        for contact in contacts:
            contact.tags.clear()
        messages.success(request, f'Cleared all tags from {selected_count} contact(s).')
        return redirect('contacts:list')

    messages.error(request, 'Invalid tag action selected.')
    return redirect('contacts:list')


@login_required
def import_csv(request):
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        list_name = request.POST.get('list_name', '').strip()

        if not csv_file or not list_name:
            messages.error(request, 'Please provide both a list name and a CSV file.')
            return redirect('contacts:import_csv')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'File must be a .csv')
            return redirect('contacts:import_csv')

        try:
            decoded = csv_file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(decoded))
            headers = [h.strip().lower() for h in (reader.fieldnames or [])]

            if 'email' not in headers:
                messages.error(request, 'CSV must have an "email" column.')
                return redirect('contacts:import_csv')

            contact_list_obj = ContactList.objects.create(
                user=request.user,
                name=list_name,
                description=f'Imported from {csv_file.name}',
            )

            created = 0
            skipped = 0
            for row in reader:
                row = {k.strip().lower(): v.strip() for k, v in row.items()}
                email = row.get('email', '').strip().lower()
                if not email or '@' not in email:
                    skipped += 1
                    continue
                contact_obj, was_created = Contact.objects.get_or_create(
                    contact_list=contact_list_obj,
                    email=email,
                    defaults={
                        'first_name': row.get('first_name', ''),
                        'last_name': row.get('last_name', ''),
                    }
                )

                tag_values = Contact.parse_tags(row.get('tags', ''))
                if tag_values:
                    tag_objects = []
                    for tag_name in tag_values:
                        tag_obj, _ = ContactTag.objects.get_or_create(user=request.user, name=tag_name)
                        tag_objects.append(tag_obj)
                    contact_obj.tags.add(*tag_objects)

                if was_created:
                    created += 1
                else:
                    skipped += 1

            messages.success(request, f'List "{list_name}" created with {created} contacts ({skipped} skipped).')
            return redirect('contacts:list')

        except Exception as e:
            messages.error(request, f'Failed to import CSV: {e}')
            return redirect('contacts:import_csv')

    return render(request, 'contacts/import_csv.html')


@login_required
def add_contact(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        list_id = request.POST.get('list_id', '').strip()
        tags_raw = request.POST.get('tags', '').strip()

        if not email or '@' not in email:
            messages.error(request, 'Please enter a valid email address.')
            return redirect('contacts:list')

        if list_id:
            contact_list = get_object_or_404(ContactList, id=list_id, user=request.user)
        else:
            contact_list, _ = ContactList.objects.get_or_create(
                user=request.user,
                name='Default List',
                defaults={'description': 'Auto-created default list'}
            )

        contact_obj, created = Contact.objects.get_or_create(
            contact_list=contact_list,
            email=email,
            defaults={'first_name': first_name, 'last_name': last_name}
        )

        tag_values = Contact.parse_tags(tags_raw)
        if tag_values:
            tag_objects = []
            for tag_name in tag_values:
                tag_obj, _ = ContactTag.objects.get_or_create(user=request.user, name=tag_name)
                tag_objects.append(tag_obj)
            contact_obj.tags.add(*tag_objects)

        if created:
            messages.success(request, f'{email} added to "{contact_list.name}".')
        else:
            messages.warning(request, f'{email} already exists in "{contact_list.name}".')

    return redirect('contacts:list')


@login_required
def delete_contact(request, contact_id):
    contact = get_object_or_404(Contact, id=contact_id, contact_list__user=request.user)
    if request.method == 'POST':
        contact.delete()
        messages.success(request, f'{contact.email} deleted.')
    return redirect('contacts:list')


@login_required
def delete_list(request, list_id):
    contact_list = get_object_or_404(ContactList, id=list_id, user=request.user)
    if request.method == 'POST':
        name = contact_list.name
        contact_list.delete()
        messages.success(request, f'List "{name}" and all its contacts deleted.')
    return redirect('contacts:list')


@login_required
def create_list(request):
    """Create a new contact list - renders form for GET, handles creation for POST."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            messages.error(request, 'List name is required.')
            return render(request, 'contacts/create_list.html')

        if ContactList.objects.filter(user=request.user, name=name).exists():
            messages.error(request, f'A list named "{name}" already exists.')
            return render(request, 'contacts/create_list.html')

        contact_list = ContactList.objects.create(
            user=request.user,
            name=name,
            description=description or None
        )
        messages.success(request, f'List "{name}" created successfully. Add contacts now!')
        return redirect('contacts:list')

    return render(request, 'contacts/create_list.html')
