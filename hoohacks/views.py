from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.conf import settings
from users.models import User, EmailView
from pytz import timezone
from datetime import datetime

def receive_email(request, email_uuid):
    e = EmailView.objects.filter(uuid_confirmation=email_uuid).first()
    u = e.user
    e.viewed = datetime.now()
    if e.action == "verify":
        u.verified = True
    e.save()
    u.save()
    return redirect(e.redirect_url)
    
def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler500(request):
    return render(request, '500.html', status=500)
