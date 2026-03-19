from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from .models import ContactList, Contact
import csv
import io

@login_required
def contact_list(request):
    if request.method == 'POST':
        list_id = request.POST.get('list_id')
        contact_list_obj = ContactList.objects.filter(user=request.user, id=list_id).first()
        if contact_list_obj:
            list_name = contact_list_obj.name
            contact_list_obj.delete()
            messages.success(request, f'Contact list "{list_name}" deleted.')
        else:
            messages.error(request, 'Contact list not found.')
        return redirect('contacts:list')

    lists = ContactList.objects.filter(user=request.user).annotate(contact_count=Count('contacts'))
    total_contacts = sum(cl.contact_count for cl in lists)
    return render(request, 'contacts/list.html', {'contact_lists': lists, 'total_contacts': total_contacts})


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

            # Normalize headers
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
                # Normalize row keys
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
            return redirect('campaigns:campaign_create')

        except Exception as e:
            messages.error(request, f'Failed to import CSV: {e}')
            return redirect('contacts:import_csv')

    return render(request, 'contacts/import_csv.html')