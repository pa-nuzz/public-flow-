from django.test import Client
from django.contrib.auth import get_user_model
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

User = get_user_model()
c = Client()

# Create a user
try:
    user = User.objects.create_user(username='testuser', email='test@example.com', password='password123', full_name='Test User')
    print("User created")
except Exception as e:
    print("User creation failed or already exists:", e)

# Test login page
r = c.get('/accounts/login/')
print("Login Page Status:", r.status_code)

# Login
login_success = c.login(username='testuser', password='password123')
print("Login successful:", login_success)

# Test dashboard
r = c.get('/accounts/dashboard/')
print("Dashboard Status:", r.status_code)

if r.status_code == 200:
    print("Dashboard rendered successfully")
else:
    print("Dashboard render failed with status:", r.status_code)
