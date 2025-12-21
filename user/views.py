# ==============================
# 🔹 Django Core Imports
# ==============================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.urls import reverse
from .models import Booking, Event, Review
from .form import ReviewForm
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives, send_mail   # ✅ Emails
from django.utils.timezone import now
from urllib.parse import urlparse
import threading
# Correct imports at the top of your views.py
import datetime
from datetime import datetime, timedelta, time
from django.utils import timezone
from django.core.files.storage import default_storage

from razorpay.errors import BadRequestError

# ==============================
# 🔹 Django Models & Forms
# ==============================
from django.contrib.auth.models import User
from .models import *     # ✅ Import all models (Profile, Event, Organizer, Customer, Booking, etc.)
from .form import *       # ✅ Import all forms (UserForm, CustomerForm, OrganizerForm, EventForm, BookingForm, etc.)

# ==============================
# 🔹 Database & ORM
# ==============================
from django.db import IntegrityError, transaction
from django.db.models import Sum, Count, Q

# ==============================
# 🔹 External Libraries
# ==============================
import razorpay
import hmac, hashlib, json
import base64
import random
import qrcode
from decimal import Decimal, ROUND_HALF_UP

# ==============================
# 🔹 Email & File Handling
# ==============================
from io import BytesIO
from email.mime.image import MIMEImage
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string





# ------------------------
# User Registration View
# ------------------------
def register(request):
    """
    Handles user registration for both customers and organizers.
    - Validates passwords match.
    - Checks if email or username already exists.
    - Creates User and associated Profile, Customer, or Organizer entry.
    """
    if request.method == 'POST':
        username = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        role = request.POST.get('role', '').lower()
        pass1 = request.POST.get('password1')
        pass2 = request.POST.get('password2')

        # Check if passwords match
        if pass1 != pass2:
            messages.error(request, "Passwords do not match.", extra_tags="register")
            return render(request, 'register.html')

        # Check for existing email
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.", extra_tags="register")
            return render(request, 'register.html')

        # Check for existing username
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.", extra_tags="register")
            return render(request, 'register.html')

        try:
            # Create new user
            my_user = User.objects.create_user(username=username, email=email, password=pass1)
            profile = my_user.profile
            profile.role = role
            profile.save()

            # Create either a Customer or Organizer entry
            if role == 'customer':
                Customer.objects.create(user=my_user, phone=phone, city='', state='')
            elif role == 'organizer':
                Organizer.objects.create(
                    user=my_user, phone=phone, organization_name='Organization Name Here',
                    city='', state='', description=''
                )

           # ✅ Send Welcome Email
            print("✅ Email sent successfully")
            subject = "Welcome to EventHub 🎉"
            html_content = render_to_string("emails/register_email.html", {"username": username})
            msg = EmailMultiAlternatives(subject, "", to=[email])  # use different var name
            msg.attach_alternative(html_content, "text/html")
            msg.send()



            messages.success(request, "Your account has been created successfully!",extra_tags="login")
            return redirect('login')

        except IntegrityError:
            messages.error(request, "Something went wrong. Try again.")
            return render(request, 'register.html')

    return render(request, 'register.html')

# ------------------------
# Forgot Password - Step 1 (Enter Email)
# ------------------------
def forgot_password(request):
    email = request.GET.get("email", "")  # prefill from query if available

    if request.method == "POST":
        email = request.POST.get("email")  # overwrite with form value
        try:
            user = User.objects.get(email=email)

            # Generate OTP
            otp = random.randint(100000, 999999)
            request.session["reset_email"] = email
            request.session["reset_otp"] = str(otp)

            # Send OTP email
            subject = "🔑 EventHub Password Reset OTP"
            html_content = render_to_string("emails/otp_email.html", {
                "otp": otp,
                "username": user.username,
            })
            msg = EmailMultiAlternatives(subject, "", to=[email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()

            messages.success(request, "✅ OTP sent to your email.")
            return redirect("verify_otp")

        except User.DoesNotExist:
            messages.error(request, "❌ No account with that email.")

    return render(request, "auth/forgot_password.html", {"email": email})


# ------------------------
# Forgot Password - Step 2 (Verify OTP)
# ------------------------
def verify_otp(request):
    if request.method == "POST":
        otp = request.POST.get("otp")
        if otp == request.session.get("reset_otp"):
            messages.success(request, "✅ OTP verified. Reset your password.")
            return redirect("reset_password")
        else:
            messages.error(request, "❌ Invalid OTP.")
    return render(request, "auth/verify_otp.html")


# ------------------------
# Forgot Password - Step 3 (Reset Password)
# ------------------------
def reset_password(request):
    if request.method == "POST":
        pass1 = request.POST.get("password1")
        pass2 = request.POST.get("password2")

        if pass1 != pass2:
            messages.error(request, "❌ Passwords don’t match.")
            return redirect("reset_password")

        email = request.session.get("reset_email")
        try:
            user = User.objects.get(email=email)
            user.set_password(pass1)   # ✅ hashes the password
            user.save()

            # Clear session
            request.session.pop("reset_email", None)
            request.session.pop("reset_otp", None)

            messages.success(request, "✅ Password reset successful. Please login.")
            return redirect("login")

        except User.DoesNotExist:
            messages.error(request, "❌ Something went wrong.")

    return render(request, "auth/reset_password.html")


# ------------------------
# User Login View
# ------------------------
def login_user(request):
    """
    Authenticates and logs in a user using email and password.
    - Redirects based on user role.
    - Keeps entered email in form if login fails.
    """
    email = ""  # default empty

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            # Find user by email
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)

            if user is not None:
                login(request, user)

                # ✅ Send Welcome Email
                subject = "Welcome to EventHub 🎉"
                html_content = render_to_string("emails/login_email.html", {"username": user.username})
                msg = EmailMultiAlternatives(subject, "", to=[user.email])
                msg.attach_alternative(html_content, "text/html")
                msg.send()

                # Redirect according to role
                role = user.profile.role
                if role == 'admin':
                    return redirect('/admin/')
                elif role == 'organizer':
                    return redirect('organizer_dashboard')
                else:
                    return redirect('home')
            else:
                messages.error(request, 'Incorrect password.',extra_tags="login")
        except User.DoesNotExist:
            messages.error(request, 'Email not registered.',extra_tags="login")

    # always return template with email context
    return render(request, 'login.html', {"email": email})

# ------------------------
# Logout View
# ------------------------
def logout_user(request):
    """
    Logs out the currently logged-in user.
    """
    if request.method == 'POST':
        logout(request)
        return redirect('home')


# ------------------------
# Dashboard View
# ------------------------
def dashboard(request):
    """
    Shows user profile dashboard if logged in,
    otherwise redirects to login page.
    """
    if request.user.is_authenticated:
        return render(request, 'profile/profile.html')
    else:
        messages.error(request, "You need to login first.")
        return redirect('login')


# ------------------------
# Profile Page
# ------------------------
@login_required
def profile(request):
    today = now().date()

    # Upcoming events (booked & paid)
    upcoming_bookings = Booking.objects.filter(
        customer=request.user,
        event__date__gte=today,
        payment_status="paid"
    ).select_related("event")[:3]

    # Saved events
    saved_events = SavedEvent.objects.filter(
        user=request.user
    ).select_related("event")[:3]

    # Suggested events
    customer_obj = getattr(request.user, "customer", None)
    suggested_events = Event.objects.none()
    if customer_obj and customer_obj.interests:
        interests_list = [i.strip().lower() for i in customer_obj.interests.split(',')]
        suggested_events = Event.objects.filter(
            category__in=interests_list
        ).exclude(
            bookings__customer=request.user
        ).exclude(
            saved_by__user=request.user
        )[:3]

    if not suggested_events.exists():
        suggested_events = Event.objects.order_by("-date")[:3]

    return render(request, "profile/profile.html", {
        "upcoming_bookings": upcoming_bookings,
        "saved_events": saved_events,
        "suggested_events": suggested_events,
    })



# ------------------------
# Edit Profile View (Customer)
# ------------------------
@login_required
def edit_profile(request):
    """
    Allows a logged-in user to update their profile.
    - Customers can update their personal and profile info.
    - Organizers are redirected to organizer edit page.
    """
    user = request.user
    role = user.profile.role

    u_form = UserForm(request.POST or None, instance=user)

    if role == 'customer':
        # Get or create customer profile
        try:
            customer = user.customer
        except Customer.DoesNotExist:
            customer = Customer.objects.create(user=user)

        c_form = CustomerForm(request.POST or None, request.FILES or None, instance=customer)

        if request.method == 'POST':
            if u_form.is_valid() and c_form.is_valid():
                u_form.save()
                c_form.save()
                messages.success(request, '✅ Profile updated successfully.')
                return redirect('edit_profile')
            else:
                messages.error(request, '❌ Please correct the errors below.')

        return render(request, 'profile/edit_profile.html', {
            'u_form': u_form,
            'c_form': c_form,
            'role': role,
        })

    elif role == 'organizer':
        return redirect('organizer_edit_profile')

    else:
        messages.error(request, "Unsupported role.")
        return redirect('home')


# ------------------------
# Organizer Dashboard
# ------------------------
@login_required
def organizer_dashboard(request):
    """
    Redirects organizer users to their profile page.
    """
    if request.user.profile.role == 'organizer':
        return redirect('organizer_profile')
    else:
        return redirect('home')


# ------------------------
# Organizer Profile View
# ------------------------

@login_required
def organizer_profile(request):
    """
    Shows the organizer's profile page with insights and events.
    """
    if request.user.profile.role != 'organizer':
        messages.error(request, "You need to be an organizer to access this page.")
        return redirect('home')

    try:
        organizer = request.user.organizer
    except Organizer.DoesNotExist:
        messages.error(request, "Organizer profile not found.")
        return redirect('login')

    # Get all events by this organizer
    events = Event.objects.filter(organizer=organizer).order_by('-date')

    # Calculate insights
    total_events = events.count()
    # ✅ Count only PAID bookings across all events
    total_registrations = Booking.objects.filter(
        event__in=events,
        payment_status="paid"
    ).count()
 # ✅ Find most popular event based on paid bookings
    most_popular_event = (
    events.annotate(
        paid_count=Count("bookings", filter=Q(bookings__payment_status="paid"))
    )
    .order_by("-paid_count")
    .first()
)
    context = {
        "organizer": organizer,
        "user": request.user,
        "events": events,
        "total_events": total_events,
        "total_registrations": total_registrations,
        "most_popular_event": most_popular_event,
    }

    return render(request, "organizer_profile/profile.html", context)
# ------------------------
# Edit Organizer Profile
# ------------------------
@login_required
def organizer_edit_profile(request):
    """
    Allows an organizer to update their profile.
    """
    try:
        organizer = request.user.organizer
    except Organizer.DoesNotExist:
        messages.error(request, "Organizer profile does not exist.")
        return redirect('organizer_profile')

    if request.method == 'POST':
        o_form = OrganizerForm(request.POST, request.FILES, instance=organizer)
        if o_form.is_valid():
            o_form.save()
            messages.success(request, "Your organizer profile has been updated.")
            return redirect('organizer_edit_profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        o_form = OrganizerForm(instance=organizer)

    return render(request, 'organizer_profile/organizer_edit_profile.html', {
        'o_form': o_form,
        'organizer': organizer,
    })


# ------------------------
# Create Event View
# ------------------------

@login_required
def create_event(request):
    if not hasattr(request.user, 'organizer'):
        return redirect('not_authorized')

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = Organizer.objects.get(user=request.user)

            # ✅ Round to 6 decimals max
            lat = request.POST.get("latitude")
            lng = request.POST.get("longitude")

            if lat and lng:
                event.latitude = Decimal(str(lat)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                event.longitude = Decimal(str(lng)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

            event.save()
            messages.success(request, '✅ Event created successfully!')
            return redirect('create_event')
        else:
            print(form.errors)
    else:
        form = EventForm()

    return render(request, 'organizer_profile/create_event.html', {'form': form})
# Organizer's Event List
# ------------------------
@login_required
def event_list(request):
    """
    Shows a list of events created by the logged-in organizer.
    """
    if not hasattr(request.user, 'organizer'):
        return HttpResponse('Not Allow')

    events = Event.objects.filter(organizer__user=request.user)
    return render(request, 'organizer_profile/event_list.html', {'events': events})


# ------------------------
# Event Detail View (Organizer)
# ------------------------
@login_required
def event_detail(request, event_id):
    """
    Shows details of a specific event for the organizer.
    """
    event = get_object_or_404(Event, id=event_id, organizer__user=request.user)
    next_event = (
        Event.objects.filter(id__gt=event.id, organizer=event.organizer)
        .order_by('id')
        .first()
    )

    return render(request, 'organizer_profile/event_detail.html', {
        'event': event,
        'next_event': next_event,
    })


# ------------------------
# Update Event View
# ------------------------
@login_required
def update_event(request, event_id):
    """
    Allows an organizer to update details of an existing event.
    """
    event = get_object_or_404(Event, id=event_id, organizer__user=request.user)

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully.')
            return redirect('update_event', event_id=event.id)
    else:
        form = EventForm(instance=event)

    return render(request, 'organizer_profile/update_event.html', {'form': form, 'event': event})


# ------------------------
# Select Event to Update
# ------------------------
@login_required
def select_event_to_update(request):
    """
    Lets organizer choose which event to update.
    """
    if not hasattr(request.user, 'organizer'):
        return redirect('not_authorized')

    organizer = request.user.organizer
    events = Event.objects.filter(organizer=organizer)

    return render(request, 'organizer_profile/select_event_update.html', {'events': events})


# ------------------------
# Delete Event
# ------------------------
@login_required
def delete_event(request, event_id):
    """
    Deletes an event created by the organizer.
    """
    event = get_object_or_404(Event, id=event_id)

    if not hasattr(request.user, 'organizer') or event.organizer != request.user.organizer:
        return redirect('not_authorized')

    if request.method == 'POST':
        event.delete()
        messages.success(request, f"✅ Event '{event.title}' deleted successfully.")
        return redirect('select_event_to_update')

    return redirect('confirm_delete_event', event_id=event.id)


# ------------------------
# Confirm Delete Event
# ------------------------
@login_required
def confirm_delete_event(request, event_id):
    """
    Shows a confirmation page before deleting an event.
    """
    event = get_object_or_404(Event, id=event_id)
    
    if not hasattr(request.user, 'organizer') or event.organizer != request.user.organizer:
        return redirect('not_authorized')

    return render(request, 'organizer_profile/confirm_event_delete.html', {'event': event})


# ------------------------
# All Events (Customer Side)
# ------------------------
from django.core.paginator import Paginator
def all_events(request):
    today = timezone.localdate()
    cutoff_date = today - timedelta(days=4)

    selected_category = request.GET.get("category", "").strip().lower()

    events_qs = Event.objects.filter(date__gte=cutoff_date)

    if selected_category:
        events_qs = events_qs.filter(category__iexact=selected_category)

    events_qs = events_qs.order_by("date")

    # ✅ CLEAN & NORMALIZE CATEGORIES HERE
    raw_categories = Event.objects.values_list("category", flat=True)
    categories = sorted(
        set(cat.strip().lower() for cat in raw_categories if cat)
    )

    paginator = Paginator(events_qs, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "event.html", {
        "events": page_obj,
        "page_obj": page_obj,
        "today": today,
        "categories": categories,
        "selected_category": selected_category,
    })


# ------------------------
# Individual Event Detail (Customer Side)
# ------------------------
def user_event_detail(request, event_id):
    """
    Shows details of a single event for customers.
    """
    event = get_object_or_404(Event, id=event_id)
    today = now().date()   # ✅ Current date
    return render(request, 'customer_event_details.html', {
        'event': event,
        'today': today,
    })


@login_required

def recommended_events(request):
    """Suggest future events based on categories of user's past paid bookings."""
    user = request.user

    # --- Step 1: Find user's past booking categories ---
    past_categories = (
        Event.objects.filter(
            bookings__customer=user,
            bookings__payment_status__iexact="paid"
        )
        .values("category")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    if not past_categories.exists():
        messages.info(request, "No past paid bookings found — recommendations unavailable.")
        return render(request, "recommended_events.html", {"recommended_events": []})

    # --- Step 2: Get top 2 most frequent categories ---
    top_categories = [c["category"].lower() for c in past_categories[:2]]

    # --- Step 3: Get future events from those categories ---
    recommended = (
        Event.objects.filter(
            Q(category__in=top_categories),
            date__gte=timezone.now().date(),
        )
        .exclude(bookings__customer=user)  # exclude already booked events
        .distinct()
    )

    # --- Step 4: Handle results + fallback ---
    if not recommended.exists():
        # fallback: show 4 random upcoming events
        recommended = Event.objects.filter(date__gte=timezone.now().date()).order_by("?")[:4]
        messages.info(request, "No personalized events — here are some upcoming ones instead.")
    else:
        messages.success(request, "Here are some events recommended for you!")

    return render(request, "recommended_events.html", {"recommended_events": recommended})

# ------------------------
# About Us Page
# ------------------------
def about_us(request):
    """
    Displays the About Us page.
    """
    return render(request, 'about_us.html')


# ------------------------
# Contact Page
# ------------------------
def contact(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        message = request.POST.get("message")

        try:
            # ✅ Send message to EventHub admin
            admin_subject = f"New Contact Message from {name}"
            admin_html = render_to_string("emails/contact_email.html", {
                "name": name,
                "email": email,
                "message": message,
            })
            admin_msg = EmailMultiAlternatives(admin_subject, "", settings.DEFAULT_FROM_EMAIL, ["eventhubmk@gmail.com"])
            admin_msg.attach_alternative(admin_html, "text/html")
            admin_msg.send()

            # ✅ Auto reply to customer
            user_subject = "Thanks for Contacting EventHub 💬"
            user_html = render_to_string("emails/contact_reply.html", {
                "name": name,
                "message": message,
            })
            user_msg = EmailMultiAlternatives(user_subject, "", settings.DEFAULT_FROM_EMAIL, [email])
            user_msg.attach_alternative(user_html, "text/html")
            user_msg.send()

            messages.success(request, "✅ Your message has been sent successfully! Please check your email for confirmation.")
            print("✅ Contact message and auto-reply sent successfully.")

        except Exception as e:
            print("❌ Email sending failed:", e)
            messages.error(request, "⚠️ Failed to send your message. Please try again later.")

        return redirect("contact")

    return render(request, "contact.html")




# Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

# ------------------------
# Book Event & Create Payment Link
# ------------------------

# Token reward rate: 1 token per ₹50 spent
HUB_TOKEN_RATE = Decimal('50.0')


# ============================
# Seat allocation helpers
# ============================

@transaction.atomic
def assign_seats_for_booking(booking):
    """
    Allocate concrete seat numbers for this booking.

    ✅ Works only for PAID bookings
    ✅ If seats already assigned, do nothing
    ✅ Tries to find ONE CONTINUOUS BLOCK of `required` seats

    Example:
      Free seats:  [9, 10, 21, 22, 23, 24, 25, 26, 27, 28, ...]
      required=10

      → Skips [9,10] (only 2 seats)
      → Finds [21..30] (10 seats) and assigns those
    """
    from .models import Seat  # local import to avoid circulars

    # Only for paid bookings
    if booking.payment_status != "paid":
        return

    # prevent double assignment
    if booking.seats.exists():
        return

    event = booking.event

    # You already use this in your code:
    # active_tickets = tickets_booked - canceled_tickets
    required = booking.active_tickets

    if required <= 0:
        return

    # lock free seats for this event
    free_qs = (
        Seat.objects
        .select_for_update()
        .filter(event=event, booking__isnull=True)
        .order_by("seat_no")
    )
    free_seats = list(free_qs)

    if len(free_seats) < required:
        # safety guard – should not happen since we check capacity
        raise ValueError("Not enough free seats to assign for this booking.")

    # ---------------------------------------
    # 1️⃣ Try to find ONE continuous block
    # ---------------------------------------
    n = len(free_seats)
    best_start_idx = None
    run_start_idx = 0
    run_length = 1

    for i in range(1, n):
        if free_seats[i].seat_no == free_seats[i - 1].seat_no + 1:
            # still consecutive
            run_length += 1
        else:
            # gap here → close previous run
            if run_length >= required:
                best_start_idx = run_start_idx
                break  # we found first big-enough block
            # start new run from current index
            run_start_idx = i
            run_length = 1

    # after loop, also check the last run
    if best_start_idx is None and run_length >= required:
        best_start_idx = n - run_length

    if best_start_idx is not None:
        # ✅ Assign one continuous block
        chosen_seats = free_seats[best_start_idx: best_start_idx + required]
    else:
        # ---------------------------------------
        # 2️⃣ Fallback: not enough continuous block
        #    but enough total seats → just take first N
        # ---------------------------------------
        chosen_seats = free_seats[:required]

    Seat.objects.filter(id__in=[s.id for s in chosen_seats]).update(booking=booking)


@transaction.atomic
def release_last_n_seats(booking, cancel_count):
    """
    Free the LAST N seat numbers from this booking.
    Example: user has 50–54, cancels 3 → free 52,53,54.
    """
    if cancel_count <= 0:
        return

    seats_qs = booking.seats.select_for_update().order_by("seat_no")
    seats = list(seats_qs)

    if cancel_count > len(seats):
        raise ValueError("Cannot cancel more seats than assigned to this booking.")

    to_release = seats[-cancel_count:]  # last N seats
    from .models import Seat
    Seat.objects.filter(id__in=[s.id for s in to_release]).update(booking=None)

import uuid

@login_required
def book_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    profile = Profile.objects.get(user=request.user)

    if event.registration_deadline and event.registration_deadline < now().date():
        messages.error(request, "⚠️ Registration deadline has passed.")
        return redirect("event_detail", event_id=event.id)

    if event.is_full:
        messages.error(request, "This event is sold out!")
        return redirect("event_detail", event_id=event.id)

    available_tokens = profile.hub_tokens

    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.event = event
            booking.customer = request.user

            booking.booking_name = (
                form.cleaned_data.get("booking_name")
                or request.user.get_full_name()
                or request.user.username
            )
            booking.customer_email = (
                form.cleaned_data.get("customer_email") or request.user.email
            )

            # -----------------------------
            # ✅ Clean + validate phone
            # -----------------------------
            raw_phone = (
                form.cleaned_data.get("customer_phone")
                or getattr(profile, "phone_number", "")
                or ""
            )
            # keep only digits
            digits = "".join(ch for ch in str(raw_phone) if ch.isdigit())

            # Must be 10 digits and not all same (e.g., 1111111111)
            if len(digits) != 10 or len(set(digits)) == 1:
                messages.error(
                    request,
                    "Please enter a valid 10-digit mobile number (not all same digits).",
                )
                return render(
                    request,
                    "booking_form.html",
                    {
                        "form": form,
                        "event": event,
                        "profile": profile,
                        "available_tokens": profile.hub_tokens,
                    },
                )

            booking.customer_phone = digits  # store cleaned mobile

            tokens_used = int(request.POST.get("hub_tokens_used", 0))

            if booking.tickets_booked > event.available_seats:
                messages.error(
                    request, f"Only {event.available_seats} seats left."
                )
                return redirect("event_detail", event_id=event.id)

            # First save: total_price auto-calculated in model
            booking.save()

            # 👉 default: no tokens used → final price = total_price
            total_price_pay = booking.total_price

            if not booking.order_id:
                     booking.order_id = f"EVT-{uuid.uuid4().hex[:10].upper()}"
                     booking.save()

            # 🪙 Apply HUB tokens
            if tokens_used > 0:
                if tokens_used > available_tokens:
                    messages.error(
                        request,
                        f"⚠️ You only have {available_tokens} HUB tokens.",
                    )
                    # Optional: undo booking if you don't want it pending
                    # booking.delete()
                    return redirect("event_detail", event_id=event.id)

                discount_value = Decimal(tokens_used)
                booking.hub_tokens_used = tokens_used
                booking.total_price = max(
                    booking.total_price - discount_value, 0
                )
                booking.amount_to_pay = booking.total_price
                total_price_pay = booking.total_price  # final after discount

                messages.info(
                    request,
                    f"🪙 {tokens_used} HUB tokens will be applied after successful payment.",
                )
            else:
                booking.amount_to_pay = booking.total_price

            booking.payment_status = "pending"
            booking.save()

            # If amount is fully covered by tokens → mark as paid immediately
            if booking.amount_to_pay == 0:
                booking.payment_status = "paid"
                booking.save()
                if tokens_used > 0:
                    profile.hub_tokens = max(
                        profile.hub_tokens - tokens_used, 0
                    )
                    profile.save()
                messages.success(
                    request,
                    "🎟 Booking successful using HUB tokens!",
                )
                return redirect("payment_success")

            # -----------------------------
            # ✅ Razorpay call with try/except
            # -----------------------------
            try:
                payment_link = client.payment_link.create(
                    {
                        "amount": int(booking.amount_to_pay * 100),
                        "currency": "INR",
                        "description": f"Booking for {event.title}",
                        "customer": {
                            "name": booking.booking_name,
                            "email": booking.customer_email,
                            "contact": booking.customer_phone,  # cleaned 10-digit
                        },
                        "notify": {"sms": True, "email": True},
                        "callback_url": request.build_absolute_uri(
                            reverse("payment_success")
                        ),
                        "callback_method": "get",
                    }
                )
            except BadRequestError as e:
                # Razorpay rejected the data (e.g., contact, email, etc.)
                messages.error(
                    request,
                    "Payment provider rejected the details. "
                    "Please check your mobile number / email and try again.",
                )
                # Optional: mark booking as failed or delete:
                # booking.payment_status = "failed"
                # booking.save()
                return render(
                    request,
                    "booking_form.html",
                    {
                        "form": form,
                        "event": event,
                        "profile": profile,
                        "available_tokens": profile.hub_tokens,
                    },
                )

            booking.razorpay_link_id = payment_link["id"]
            booking.save()

            short_url = payment_link["short_url"]
            qr = qrcode.make(short_url)
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()

            return render(
                request,
                "book_qr.html",
                {
                    "booking": booking,
                    "payment_link": short_url,
                    "qr_code": qr_base64,
                    "event": event,
                    "available_tokens": profile.hub_tokens,
                    "final": total_price_pay,
                },
            )

    else:
        form = BookingForm(initial={"customer_email": request.user.email})

    return render(
        request,
        "booking_form.html",
        {
            "form": form,
            "event": event,
            "profile": profile,
            "available_tokens": profile.hub_tokens,
        },
    )


@csrf_exempt
def razorpay_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    payload = request.body
    received_signature = request.headers.get("X-Razorpay-Signature")

    secret = settings.RAZORPAY_WEBHOOK_SECRET.encode()

    generated_signature = hmac.new(
        secret,
        payload,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(generated_signature, received_signature):
        return HttpResponse("Invalid signature", status=400)

    data = json.loads(payload)
    event_type = data.get("event")

    if event_type == "payment.captured":
        payment = data["payload"]["payment"]["entity"]

        payment_id = payment["id"]
        link_id = payment.get("payment_link_id")
        method = payment.get("method")   # 👈 PAYMENT METHOD (upi/card/etc)

        booking = Booking.objects.filter(razorpay_link_id=link_id).first()
        if booking:
            booking.payment_status = "paid"
            booking.razorpay_payment_id = payment_id
            booking.payment_method = method
            booking.save()

    elif event_type == "payment.failed":
        payment = data["payload"]["payment"]["entity"]
        link_id = payment.get("payment_link_id")

        booking = Booking.objects.filter(razorpay_link_id=link_id).first()
        if booking:
            booking.payment_status = "failed"
            booking.save()

    return HttpResponse("OK", status=200)

# ------------------------
# Payment Success Callback
# ------------------------
@login_required
def payment_success(request):
    link_id = request.GET.get("razorpay_payment_link_id")
    payment_id = request.GET.get("razorpay_payment_id")
    reference_id = request.GET.get("razorpay_payment_link_reference_id", "") or ""
    status = request.GET.get("razorpay_payment_link_status")
    signature = (request.GET.get("razorpay_signature") or "").lower()

    booking = None

    if link_id:
        booking = Booking.objects.filter(razorpay_link_id=link_id).first()

    if not booking:
        booking = Booking.objects.filter(customer=request.user).order_by("-id").first()

    if not booking:
        messages.error(request, "⚠️ Booking not found!")
        return render(request, "payment_failed.html")

    # ================= FREE / TOKEN EVENT =================
    if booking.event.price == 0 or booking.amount_to_pay == 0:
        if booking.payment_status != "paid":
            booking.payment_status = "paid"
            booking.save()

        profile = getattr(request.user, "profile", None)
        if profile and booking.hub_tokens_used > 0:
            profile.hub_tokens = max(profile.hub_tokens - booking.hub_tokens_used, 0)
            profile.save()

        try:
            assign_seats_for_booking(booking)
        except ValueError as e:
            messages.error(request, f"Seat allocation failed: {e}")

        # 🔥 POPULAR EVENT CHECK
        _check_and_mark_popular_event(booking.event)

        return _render_ticket(request, booking)

    # ================= PAID EVENT =================
    if not link_id or not payment_id:
        messages.error(request, "⚠️ Invalid payment callback!")
        return render(request, "payment_failed.html")

    payload = f"{link_id}|{reference_id}|{status}|{payment_id}"
    generated_sig = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(generated_sig, signature):
        messages.error(request, "⚠️ Payment verification failed!")
        return render(request, "payment_failed.html")

    if status == "paid":
        booking.payment_status = "paid"
        booking.razorpay_payment_id = payment_id
        booking.razorpay_signature = signature

        payment = client.payment.fetch(payment_id)
        booking.payment_method = payment.get("method", "Unknown")
        booking.save()

        profile = getattr(request.user, "profile", None)
        if profile and booking.hub_tokens_used > 0:
            profile.hub_tokens = max(profile.hub_tokens - booking.hub_tokens_used, 0)

        tokens_earned = (float(booking.amount_to_pay) / 500) * 10
        profile.hub_tokens += Decimal(tokens_earned)
        profile.save()

        try:
            assign_seats_for_booking(booking)
        except ValueError as e:
            messages.error(request, f"Seat allocation failed: {e}")

        # 🔥 POPULAR EVENT CHECK
        _check_and_mark_popular_event(booking.event)

        messages.success(
            request,
            f"🎁 You earned {tokens_earned:.0f} HUB tokens for this booking!"
        )
        return _render_ticket(request, booking)

    booking.payment_status = "failed"
    booking.save()
    return render(request, "payment_failed.html")


def _check_and_mark_popular_event(event):
    """
    Create ONE popular-event notification
    when >= 50% seats are booked (paid).
    """

    paid_bookings = Booking.objects.filter(
        event=event,
        payment_status="paid"
    ).count()

    threshold = int(event.capacity * 0.5)

    if paid_bookings >= threshold:
        already_created = SiteNotification.objects.filter(
            event=event,
            notification_type="popular_event"
        ).exists()

        if not already_created:
            SiteNotification.objects.create(
                title="🔥 Popular Event",
                message=f"{event.title} is filling fast! Limited seats remaining.",
                notification_type="popular_event",
                event=event
            )


from decimal import Decimal  # make sure this is imported

def _render_ticket(request, booking):
    """Generate QR that organizer can scan directly to verify"""

    host = request.get_host()
    verify_path = reverse("verify_ticket_qr", args=[booking.id])
    verify_url = f"http://{host}{verify_path}"

    # QR
    qr_pil = qrcode.make(verify_url)
    buffer = BytesIO()
    qr_pil.save(buffer, format="PNG")
    qr_png = buffer.getvalue()
    qr_base64 = base64.b64encode(qr_png).decode()

    # 🔹 HUB token + price info
    tokens_used = booking.hub_tokens_used or 0

    # original ticket cost (without tokens)
    original_amount = booking.event.price * booking.tickets_booked

    # final amount after discount (1 token = ₹1)
    final_amount = original_amount - Decimal(tokens_used)

    # 🔹 Seat numbers (ordered)
    seat_numbers = list(
        booking.seats.order_by("seat_no").values_list("seat_no", flat=True)
    )

    subject = f"🎟 Your Ticket for {booking.event.title}"
    message = render_to_string("emails/ticket_email.html", {
        "booking": booking,
        "event": booking.event,
        "verify_url": verify_url,
        "seat_numbers": seat_numbers,  # for email template
    })

    email = EmailMessage(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [booking.customer_email],
    )
    email.content_subtype = "html"
    email.attach("ticket_qr.png", qr_png, "image/png")

    try:
        email.send()
    except Exception as e:
        print("❌ Email sending failed:", e)

    return render(request, "payment_success.html", {
        "booking": booking,
        "event": booking.event,
        "qr_code": qr_base64,
        "verify_url": verify_url,
        "tokens_used": tokens_used,
        "original_amount": original_amount,
        "final_amount": final_amount,
        "seat_numbers": seat_numbers,   # 👉 ticket page
    })


@login_required
def cancel_tickets(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)

    total_tickets = booking.tickets_booked
    already_canceled = booking.canceled_tickets
    available_to_cancel = total_tickets - already_canceled

    if request.method == "POST":
        cancel_count = int(request.POST.get("cancel_count", 0))

        if cancel_count <= 0 or cancel_count > available_to_cancel:
            messages.error(request, "⚠️ Invalid number of tickets to cancel.")
            return redirect("cancel_tickets", booking_id=booking.id)

        with transaction.atomic():
            # lock booking row
            booking = Booking.objects.select_for_update().get(id=booking.id)

            # 👉 Free LAST N seats: e.g. 50–54, cancel 3 → 52,53,54
            try:
                release_last_n_seats(booking, cancel_count)
            except ValueError as e:
                messages.error(request, f"⚠️ Seat cancellation error: {str(e)}")
                return redirect("cancel_tickets", booking_id=booking.id)

            # Update canceled tickets
            booking.canceled_tickets += cancel_count

            # Calculate refund (only for paid bookings)
            if booking.payment_status == "paid" and booking.razorpay_payment_id:
                ticket_price = booking.total_price / booking.tickets_booked
                refund_amount = ticket_price * cancel_count * Decimal("0.90")  # deduct 10%

                # If LIVE mode → issue refund from Razorpay
                if not settings.RAZORPAY_KEY_ID.startswith("rzp_test"):
                    try:
                        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                        refund = client.payment.refund(
                            booking.razorpay_payment_id,
                            {"amount": int(refund_amount * 100), "speed": "optimum"}
                        )
                        booking.razorpay_refund_id = refund["id"]
                        booking.refund_status = "refunded"
                    except Exception as e:
                        booking.refund_status = "failed"
                        messages.error(request, f"⚠️ Refund failed: {str(e)}")
                else:
                    # In Test Mode, just mark refund as done
                    booking.refund_status = "refunded"

                booking.refund_amount = (booking.refund_amount or 0) + refund_amount

            # If all tickets are canceled → mark booking canceled
            if booking.canceled_tickets == booking.tickets_booked:
                booking.payment_status = "canceled"
            else:
                booking.payment_status = "paid"   # keep it paid until all are canceled

            booking.save()

        messages.success(request, f"✅ {cancel_count} tickets canceled successfully.")
        return redirect("my_bookings")

    return render(request, "profile/cancel_tickets.html", {
        "booking": booking,
        "available_to_cancel": available_to_cancel
    })

@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(customer=request.user).select_related("event").order_by("-created_at")
    return render(request, "profile/my_bookings.html", {"bookings": bookings})


def ticket_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    event = booking.event

    # Calculate tickets remaining (after cancellations)
    active_tickets = booking.tickets_booked - booking.canceled_tickets

    # ------------------------------
    # Dynamic QR URL
    # ------------------------------
    host = request.get_host()
    verify_path = reverse("verify_ticket_qr", args=[booking.id])
    verify_url = f"http://{host}{verify_path}"

    qr = qrcode.make(verify_url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    seat_numbers = list(
        booking.seats.order_by("seat_no").values_list("seat_no", flat=True)
    )

    return render(request, "profile/ticket.html", {
        "booking": booking,
        "event": event,
        "qr_code": qr_code_base64,
        "verify_url": verify_url,  # manual backup link
        "active_tickets": active_tickets,
        "seat_numbers": seat_numbers,
    })



@login_required
def organizer_bookings(request):
    organizer = request.user.organizer
    bookings = Booking.objects.filter(event__organizer=organizer)

    # Prepare grouped data with totals
    event_data = {}
    for booking in bookings:
        event = booking.event
        if event.id not in event_data:
            event_data[event.id] = {
                "event": event,
                "bookings": [],
                "total_tickets": 0,
                "total_canceled": 0,
                "total_revenue": 0,
            }
        event_data[event.id]["bookings"].append(booking)
        event_data[event.id]["total_tickets"] += booking.tickets_booked
        event_data[event.id]["total_canceled"] += getattr(booking, "canceled_tickets", 0)
        if booking.payment_status == "paid":
            event_data[event.id]["total_revenue"] += booking.total_price

    return render(request, "organizer_profile/organizer_bookings.html", {
        "event_data": event_data.values(),
    })


from django.utils import timezone
from datetime import datetime, timedelta, time

@login_required
def save_event(request, event_id):
    """
    Save event, send immediate email with inline banner,
    and schedule reminder emails (10,5,1 days before registration deadline)
    """
    event = get_object_or_404(Event, id=event_id)

    # Remove previous saved instance (allow resave)
    SavedEvent.objects.filter(user=request.user, event=event).delete()
    saved = SavedEvent.objects.create(user=request.user, event=event)
    messages.success(request, "✅ Event saved successfully!")

    # -----------------------------
    # 1️⃣ Immediate email with inline banner
    # -----------------------------
    def send_email():
        subject = f"🎉 Event Saved: {event.title}"
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = [request.user.email]

        html_content = render_to_string("emails/saved_event_email.html", {
            "user": request.user,
            "event": event,
            "banner_cid": "banner.jpg"
        })

        msg = EmailMultiAlternatives(subject, "", from_email, to_email)
        msg.attach_alternative(html_content, "text/html")

        # Attach banner image inline
        if event.banner:
            with default_storage.open(event.banner.name, "rb") as f:
                banner_data = f.read()
            msg.attach("banner.jpg", banner_data, "image/jpeg")
            msg.mixed_subtype = 'related'

        msg.send()

    threading.Thread(target=send_email).start()

    # -----------------------------
    # 2️⃣ Schedule reminders (10, 5, 1 days before registration deadline)
    # -----------------------------
    if event.registration_deadline:
        today = timezone.now().date()
        reminder_days = [10, 5, 1]

        for days_before in reminder_days:
            reminder_date = event.registration_deadline - timedelta(days=days_before)
            if reminder_date > today:
                # Combine date & time (9:00 AM) and make timezone-aware
                naive_dt = datetime.combine(reminder_date, time(9, 0))
                reminder_datetime = timezone.make_aware(naive_dt, timezone.get_default_timezone())
                delay_seconds = (reminder_datetime - timezone.now()).total_seconds()
                if delay_seconds > 0:
                    # Threaded reminder function
                    def send_reminder(user_id=request.user.id, event_id=event.id):
                        from django.contrib.auth.models import User
                        user = User.objects.get(id=user_id)
                        event_obj = Event.objects.get(id=event_id)
                        subject = f"⏰ Reminder: Event '{event_obj.title}'"
                        from_email = settings.DEFAULT_FROM_EMAIL
                        to_email = [user.email]

                        html_content = render_to_string("emails/saved_event_email.html", {
                            "user": user,
                            "event": event_obj,
                            "banner_cid": "banner.jpg"
                        })

                        msg = EmailMultiAlternatives(subject, "", from_email, to_email)
                        msg.attach_alternative(html_content, "text/html")

                        if event_obj.banner:
                            with default_storage.open(event_obj.banner.name, "rb") as f:
                                banner_data = f.read()
                            msg.attach("banner.jpg", banner_data, "image/jpeg")
                            msg.mixed_subtype = 'related'

                        msg.send()

                    threading.Timer(delay_seconds, send_reminder).start()

    return redirect("user_event_detail", event_id=event.id)


@login_required
def remove_saved_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    SavedEvent.objects.filter(user=request.user, event=event).delete()
    messages.success(request, "❌ Event removed from saved list.")
    return redirect("saved_events")

@login_required
def saved_events(request):
    saved = SavedEvent.objects.filter(user=request.user).select_related("event")
    return render(request, "profile/saved_events.html", {"saved_events": saved})

''''

import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

def get_collaborative_recommendations(user):
    # 1️⃣ Load bookings
    bookings = Booking.objects.all().values('customer_id', 'event_id')
    df = pd.DataFrame(bookings)

    if df.empty:
        return Event.objects.none()

    # 2️⃣ Build user-event matrix
    user_event_matrix = df.pivot_table(index='customer_id', columns='event_id', aggfunc='size', fill_value=0)

    # 3️⃣ Compute cosine similarity between users
    user_sim = pd.DataFrame(cosine_similarity(user_event_matrix), 
                            index=user_event_matrix.index, 
                            columns=user_event_matrix.index)

    # 4️⃣ Find similar users
    similar_users = user_sim[user.id].sort_values(ascending=False).index[1:6]  # top 5 similar users

    # 5️⃣ Events booked by similar users
    similar_users_events = df[df['customer_id'].isin(similar_users)]['event_id'].unique()

    # 6️⃣ Exclude events already booked by the current user
    user_booked_events = df[df['customer_id'] == user.id]['event_id'].unique()
    recommended_event_ids = [eid for eid in similar_users_events if eid not in user_booked_events]

    return Event.objects.filter(id__in=recommended_event_ids)
'''

# -------------------------------
# Step 1: Show all events of organizer
# -------------------------------
@login_required
def verify_customers(request):
    if not hasattr(request.user, "organizer"):
        messages.error(request, "Only organizers can access this page.")
        return redirect("dashboard")

    events = Event.objects.filter(organizer=request.user.organizer).order_by("-date")
    return render(request, "organizer_profile/verify_events.html", {
        "events": events
    })


# -------------------------------
# Step 2: Show bookings for one event
# -------------------------------
@login_required
def verify_event_customers(request, event_id):
    event = get_object_or_404(Event, id=event_id, organizer=request.user.organizer)
    bookings = Booking.objects.filter(event=event, payment_status="paid").select_related("customer")

    return render(request, "organizer_profile/verify_customers.html", {
        "event": event,
        "bookings": bookings
    })


# -------------------------------
# Mark attendance manually
# -------------------------------
@login_required
def mark_attended(request, booking_id):
    booking = get_object_or_404(
        Booking,
        id=booking_id,
        event__organizer__user=request.user
    )

    if booking.payment_status == "paid":
        booking.attended = True
        booking.save()
        messages.success(request, f"✅ {booking.customer.username} marked as attended.")
    else:
        messages.error(request, "⚠️ Only paid bookings can be verified.")

    return redirect("verify_event_customers", event_id=booking.event.id)


@login_required
def scan_qr_page(request, event_id):
    event = get_object_or_404(Event, id=event_id, organizer=request.user.organizer)

    return render(request, "organizer_profile/scan_qr.html", {
        "event": event
    })


# -------------------------------
# QR verification endpoint
# -------------------------------
@login_required
def verify_ticket_qr(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    # Organizer ownership check
    if booking.event.organizer.user != request.user:
        return render(request, "organizer_profile/verify_result.html", {
            "status": "error",
            "message": "⚠️ You are not authorized to verify this ticket.",
            "booking": booking,
        })

    # Only paid tickets can be verified
    if booking.payment_status == "paid":
        if not booking.attended:
            booking.attended = True
            booking.save()
            status = "success"
            message = f"✅ Ticket for {booking.customer.username} verified successfully!"
        else:
            status = "info"
            message = f"ℹ️ Ticket for {booking.customer.username} was already verified."
    else:
        status = "error"
        message = "⚠️ Cannot verify unpaid ticket."

    return render(request, "organizer_profile/verify_result.html", {
        "status": status,
        "message": message,
        "booking": booking,
    })


@login_required
def verify_ticket(request):
    code = request.GET.get("code")

    if not code:
        messages.error(request, "❌ Invalid QR code.")
        return redirect("organizer_dashboard")

    try:
        booking_id = int(code.strip("/").split("/")[-1])
    except Exception:
        messages.error(request, "❌ QR code is not valid.")
        return redirect("organizer_dashboard")

    booking = get_object_or_404(Booking, id=booking_id)

    # Organizer check
    if booking.event.organizer.user != request.user:
        messages.error(request, "⚠️ You are not authorized to verify this ticket.")
        return redirect("organizer_dashboard")

    # Check payment + attendance
    if booking.payment_status == "paid":
        if not booking.attended:
            booking.attended = True
            booking.save()
            messages.success(request, f"✅ Ticket for {booking.booking_name or booking.customer.username} verified!")
        else:
            messages.info(request, f"ℹ️ Ticket for {booking.booking_name or booking.customer.username} already verified.")
    else:
        messages.error(request, "❌ Cannot verify unpaid ticket.")

    # ✅ Redirect to the customer list page of this booking's event
    return redirect("verify_event_customers", event_id=booking.event.id)


@login_required
def scan_qr_dashboard(request):
    # Only for organizers
    if not hasattr(request.user, "organizer"):
        messages.error(request, "Only organizers can scan tickets.")
        return redirect("dashboard")

    return render(request, "organizer_profile/scan_qr_dashboard.html")

@login_required
def review_events_list(request):
   
    attended_bookings = list(
        Booking.objects.filter(
            customer=request.user,
            payment_status="paid",   # show all paid bookings
        ).select_related("event")
    )


    # ✅ Prefetch this user’s existing reviews for these events
    event_ids = [b.event_id for b in attended_bookings]
    existing_reviews = Review.objects.filter(
        user=request.user,
        event_id__in=event_ids
    )
    review_map = {r.event_id: r for r in existing_reviews}

    # attach .review attribute on each booking so template can use booking.review
    for b in attended_bookings:
        b.review = review_map.get(b.event_id)

    context = {
        "attended_bookings": attended_bookings,
        "review_form": ReviewForm(),
    }
    return render(request, "profile/review_events_list.html", context)

@login_required
def submit_review(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    # User must have PAID & attended booking for this event
    attended = Booking.objects.filter(
        customer=request.user,
        event=event,
        payment_status="paid",
        attended=True,
    ).exists()

    if not attended:
        messages.error(request, "You can only review events you actually attended.")
        return redirect("user-review-events")

    # ❌ If review already exists, don't allow another one
    if Review.objects.filter(user=request.user, event=event).exists():
        messages.error(request, "You have already reviewed this event.")
        return redirect("user-review-events")

    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            Review.objects.create(
                user=request.user,
                event=event,
                text=form.cleaned_data["text"],
            )
            messages.success(request, "✅ Your review has been submitted.")
        else:
            for field_errors in form.errors.values():
                for err in field_errors:
                    messages.error(request, err)

        return redirect("user-review-events")

    return redirect("user-review-events")

@login_required
def organizer_reviews(request):
    # ✅ Only organizers can see this
    if not hasattr(request.user, "organizer"):
        messages.error(request, "Only organizers can view reviews.")
        return redirect("dashboard")

    # Events owned by this organizer (note organizer__user)
    events = Event.objects.filter(organizer__user=request.user)

    reviews = Review.objects.filter(
        event__in=events
    ).select_related("user", "event").order_by("-created_at")

    context = {"reviews": reviews}
    return render(request, "organizer_profile/organizer_reviews.html", context)

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import SiteNotification

@login_required
def fetch_site_notifications(request):
    user = request.user

    # Only unseen notifications
    notifications = SiteNotification.objects.exclude(
        seen_by=user
    ).order_by("-created_at")[:3]  # max 3 only

    data = []

    for n in notifications:
        data.append({
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.notification_type,
        })
        n.seen_by.add(user)  # mark as seen immediately

    return JsonResponse({"notifications": data})


def upcoming_features(request):
    return render(request, "upcoming_features.html")

def privacy_policy(request):
    return render(request, "privacy_policy.html")
