#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
import json

User = get_user_model()
user = User.objects.first()
if not user:
    user = User.objects.create_user(email='test@ex.com', password='test')

client = Client()
client.force_login(user)

test_cases = [
    ("hello goodmorning", "SIMPLE GREETING", "Very Low", 30),
    ("hello big fan", "SHORT CASUAL", "Low", 55),
    ("Thanks for your interest", "PROFESSIONAL", "Very Low", 30),
    ("You won FREE money! Click NOW!", "OBVIOUS SPAM", "High", 80),
    ("URGENT: Claim your prize!!!", "AGGRESSIVE SPAM", "High", 80),
]

print("\n" + "="*70)
print("SPAM ANALYSIS TEST RESULTS - VERIFICATION")
print("="*70)

all_ok = True

for content, label, expected_risk, max_expected_score in test_cases:
    response = client.post(
        '/intelligence/api/analyze/',
        data=json.dumps({'content': content}),
        content_type='application/json'
    )

    if response.status_code != 200:
        all_ok = False
        print(f"\n{label}")
        print(f"  Message: '{content}'")
        print(f"  ERROR: API returned status {response.status_code}")
        continue

    data = response.json()
    score = data['spam_score']
    risk = data['risk_level']
    
    if score < 20:
        color = "🟢 GREEN"
    elif score < 40:
        color = "🟢 GREEN"
    elif score < 70:
        color = "🟡 ORANGE"
    else:
        color = "🔴 RED"
    
    print(f"\n{label}")
    print(f"  Message: '{content}'")
    print(f"  Score: {score}/100  {color}")
    print(f"  Risk Level: {risk}")

    if label in {"OBVIOUS SPAM", "AGGRESSIVE SPAM"}:
        passed = (risk == expected_risk and score >= max_expected_score)
    else:
        passed = (score <= max_expected_score)

    print(f"  Check: {'PASS' if passed else 'FAIL'}")
    all_ok = all_ok and passed

print("\n" + "="*70)
if all_ok:
    print("✅ SPAM DETECTION FIX VERIFIED")
else:
    print("⚠️ SPAM DETECTION NEEDS FURTHER TUNING")
print("="*70 + "\n")
