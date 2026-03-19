from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from .models import ContactList, Contact
import csv
import io


@login_required
def contacts_home(request):
    contact_lists = ContactList.objects.filter(user=request.user).annotate(contact_count=Count('contacts'))
    all_contacts = Contact.objects.filter(
        contact_list__user=request.user
    ).select_related('contact_list').order_by('-created_at')

    # Search
    search = request.GET.get('q', '').strip()
    if search:
        all_contacts = all_contacts.filter(email__icontains=search)

    total = Contact.objects.filter(contact_list__user=request.user).count()

    return render(request, 'contacts/contacts_home.html', {
        'contact_lists': contact_lists,
        'all_contacts': all_contacts,
        'total': total,
        'search': search,
    })


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
                _, was_created = Contact.objects.get_or_create(
                    contact_list=contact_list_obj,
                    email=email,
                    defaults={
                        'first_name': row.get('first_name', ''),
                        'last_name': row.get('last_name', ''),
                    }
                )
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

        _, created = Contact.objects.get_or_create(
            contact_list=contact_list,
            email=email,
            defaults={'first_name': first_name, 'last_name': last_name}
        )

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

