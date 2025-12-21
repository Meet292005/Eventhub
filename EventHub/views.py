from django.shortcuts import render

# user/views.py
from django.shortcuts import render
from user.models import Event
from django.db.models import Q

def home(request):
    events = Event.objects.order_by("-id")[:3]  # latest 3 events
    return render(request, "home.html", {"events": events})
