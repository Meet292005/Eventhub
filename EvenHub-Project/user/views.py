from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from .models import Profile, Event, Organizer, Customer
from .form import UserForm, CustomerForm, OrganizerForm, EventForm
import razorpay
import hmac, hashlib, json
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from .models import Booking
from .form import BookingForm
import base64
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.core.mail import send_mail   # ✅ Import send_mail
import qrcode
from io import BytesIO
import base64
from django.utils.timezone import now
from io import BytesIO
from email.mime.image import MIMEImage
from django.db.models import Sum
from django.db.models import Count,Q
from decimal import Decimal, ROUND_HALF_UP
import random
from django.contrib.auth.models import User



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
            messages.error(request, "Passwords do not match.")
            return render(request, 'register.html')

        # Check for existing email
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return render(request, 'register.html')

        # Check for existing username
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
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



            messages.success(request, "Your account has been created successfully!")
            return redirect('login')

        except IntegrityError:
            messages.error(request, "Something went wrong. Try again.")
            return render(request, 'register.html')

    return render(request, 'register.html')

# ------------------------
# Forgot Password - Step 1 (Enter Email)
# ------------------------
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")
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

    return render(request, "auth/forgot_password.html")


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
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            # Find user by email
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)

            if user is not None:
                login(request, user)

                  # ✅ Send Login Notification Email
                 # ✅ Send Welcome Email
                print("✅ Email sent successfully")
                subject = "Welcome to EventHub 🎉"
                html_content = render_to_string("emails/login_email.html", {"username": user.username})
                msg = EmailMultiAlternatives(subject, "", to=[user.email])  # use different var name
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
                messages.error(request, 'Incorrect password.')
        except User.DoesNotExist:
            messages.error(request, 'Email not registered.')

    return render(request, 'login.html')


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
def profile(request):
    """
    Displays the user's profile page.
    """
    return render(request, 'profile/profile.html')


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
def all_events(request):
    """
    Shows all events to customers.
    """
    events = Event.objects.all().order_by('-date')
    return render(request, 'event.html', {'events': events})


# ------------------------
# Individual Event Detail (Customer Side)
# ------------------------
def user_event_detail(request, event_id):
    """
    Shows details of a single event for customers.
    """
    event = get_object_or_404(Event, id=event_id)
    return render(request, 'customer_event_details.html', {'event': event})


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
    """
    Displays the Contact page.
    """
    return render(request, 'contact.html')




# Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

# ------------------------
# Book Event & Create Payment Link
# ------------------------@login_required

def book_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    
    # ✅ Block booking if deadline has passed
    if event.registration_deadline and event.registration_deadline < now().date():
        messages.error(request, "⚠️ Registration deadline has passed. You cannot book this event.")
        return redirect("event_detail", event_id=event.id)

    # ❌ Block booking if event is full
    if event.is_full:
        messages.error(request, "This event is sold out! No seats available.")
        return redirect("event_detail", event_id=event.id)

    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.event = event
            booking.customer = request.user
            booking.booking_name = request.user.get_full_name() or request.user.username
            booking.customer_email = request.user.email
            booking.customer_phone = form.cleaned_data.get("customer_phone", "")
            booking.payment_status = "pending"

            # ❌ Prevent overbooking
            if booking.tickets_booked > event.available_seats:
                messages.error(request, f"Only {event.available_seats} seats left. Please reduce tickets.")
                return redirect("event_detail", event_id=event.id)

            booking.save()

            # ✅ Create Razorpay Payment Link
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            payment_link = client.payment_link.create({
                "amount": int(booking.total_price * 100),  # in paise
                "currency": "INR",
                "description": f"Booking for {event.title}",
                "customer": {
                    "name": booking.booking_name,
                    "email": booking.customer_email,
                    "contact": booking.customer_phone or "",
                },
                "notify": {"sms": True, "email": True},
                "callback_url": request.build_absolute_uri(reverse("payment_success")),
                "callback_method": "get"
            })

            # ✅ Save Razorpay Link ID
            booking.razorpay_link_id = payment_link["id"]
            booking.save()

            # ✅ Generate QR Code from short_url
            short_url = payment_link["short_url"]
            qr = qrcode.make(short_url)
            buffer = BytesIO()
            qr.save(buffer, format="PNG")
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()

            return render(request, "book_qr.html", {
                "booking": booking,
                "payment_link": short_url,
                "qr_code": qr_base64,
                "event": event
            })

    else:
        form = BookingForm()

    return render(request, "booking_form.html", {"form": form, "event": event})

@csrf_exempt
def razorpay_webhook(request):
    if request.method != "POST":
        return HttpResponse("Method Not Allowed", status=405)

    payload = request.body.decode("utf-8")
    received_sig = request.headers.get("X-Razorpay-Signature")

    # Verify signature (base64)
    generated_sig = base64.b64encode(
        hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    ).decode()

    if not hmac.compare_digest(generated_sig, received_sig):
        return HttpResponse("Invalid signature", status=400)

    data = json.loads(payload)
    event_type = data.get("event")

    if event_type == "payment.captured":
        payment_id = data["payload"]["payment"]["entity"]["id"]
        link_id = data["payload"]["payment"]["entity"]["payment_link_id"]

        booking = Booking.objects.filter(razorpay_link_id=link_id).first()
        if booking:
            booking.payment_status = "paid"
            booking.razorpay_payment_id = payment_id
            booking.save()

    elif event_type == "payment.failed":
        link_id = data["payload"]["payment"]["entity"]["payment_link_id"]
        booking = Booking.objects.filter(razorpay_link_id=link_id).first()
        if booking:
            booking.payment_status = "failed"
            booking.save()

    return HttpResponse("Webhook processed", status=200)


# ------------------------
# Payment Success Callback
# ------------------------
"""
def payment_success(request):
    payment_id = request.GET.get("razorpay_payment_id")
    link_id = request.GET.get("razorpay_payment_link_id")
    reference_id = request.GET.get("razorpay_payment_link_reference_id", "") or ""  # may be blank
    status = request.GET.get("razorpay_payment_link_status")
    signature = (request.GET.get("razorpay_signature") or "").lower()

    print("Callback params:", payment_id, link_id, reference_id, status, signature)

    booking = Booking.objects.filter(razorpay_link_id=link_id).first()
    if not booking:
        messages.error(request, "⚠️ Booking not found!")
        return render(request, "payment_failed.html")

    # ✅ Correct payload for Payment Links
    payload = f"{link_id}|{reference_id}|{status}|{payment_id}"

    generated_sig = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    print("Generated:", generated_sig)
    print("Received :", signature)

    # Signature verification
    if not hmac.compare_digest(generated_sig, signature):
        messages.error(request, "⚠️ Payment verification failed!")
        return render(request, "payment_failed.html")

    # ✅ Update booking if paid
    if status == "paid":
        booking.payment_status = "paid"
        booking.razorpay_payment_id = payment_id
        booking.razorpay_signature = signature
        booking.save()
        messages.success(request, "✅ Payment confirmed! Your booking is successful.")
        return render(request, "payment_success.html")
    elif status in ["failed", "cancelled"]:
         booking.payment_status = "failed"
         booking.save()
         return render(request, "payment_failed.html")

    else:  # pending or any unknown state
        booking.payment_status = "pending"
        booking.save()
        return render(request, "payment_failed.html")

        """
def payment_success(request):
    payment_id = request.GET.get("razorpay_payment_id")
    link_id = request.GET.get("razorpay_payment_link_id")
    reference_id = request.GET.get("razorpay_payment_link_reference_id", "") or ""
    status = request.GET.get("razorpay_payment_link_status")
    signature = (request.GET.get("razorpay_signature") or "").lower()

    booking = Booking.objects.filter(razorpay_link_id=link_id).first()
    if not booking:
        messages.error(request, "⚠️ Booking not found!")
        return render(request, "payment_failed.html")

    # Verify signature
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
        # mark booking as paid
        booking.payment_status = "paid"
        booking.razorpay_payment_id = payment_id
        booking.razorpay_signature = signature
        booking.save()

        # Generate QR (PNG bytes)
        ticket_url = request.build_absolute_uri(reverse("ticket_view", args=[booking.id]))
        qr_pil = qrcode.make(ticket_url)
        buffer = BytesIO()
        qr_pil.save(buffer, format="PNG")
        qr_png = buffer.getvalue()

        # Prepare email
        subject = f"🎟️ Your Ticket for {booking.event.title}"
        # email template should reference the inline image with: <img src="cid:qr_code" />
        html_content = render_to_string("emails/ticket_email.html", {
            "booking": booking,
            "event": booking.event,
            "qr_cid": "qr_code",  # used in template as cid:qr_code
        })

        # From email: fallback to DEFAULT_FROM_EMAIL or EMAIL_HOST_USER
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)

        msg = EmailMultiAlternatives(subject, "", from_email, [booking.customer_email])
        msg.attach_alternative(html_content, "text/html")

        # Ensure related/mixed subtype so inline images render
        msg.mixed_subtype = "related"

        # Attach inline image using MIMEImage (correct way)
        try:
            mime_img = MIMEImage(qr_png, _subtype="png")
            mime_img.add_header("Content-ID", "<qr_code>")
            # use keyword arg for filename to avoid tuple-style mistakes
            mime_img.add_header("Content-Disposition", "inline", filename="qr.png")
            msg.attach(mime_img)
        except Exception:
            # Fallback: attach as normal file (safe) AND embed base64 directly in an alternate HTML
            msg.attach("qr.png", qr_png, "image/png")
            html_with_datauri = html_content.replace("cid:qr_code", "data:image/png;base64," + base64.b64encode(qr_png).decode())
            # attach fallback HTML version so clients that don't show inline attachments can still display QR
            msg.attach_alternative(html_with_datauri, "text/html")

        # Send email
        msg.send(fail_silently=False)

        # Render success page and also show QR inline on webpage (base64)
        return render(request, "payment_success.html", {
            "booking": booking,
            "event": booking.event,
            "qr_code": base64.b64encode(qr_png).decode()
        })

    # not paid
    booking.payment_status = "failed"
    booking.save()
    return render(request, "payment_failed.html")


@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)

    if booking.payment_status != "paid":
        messages.error(request, "Only paid bookings can be canceled.")
        return redirect("my_bookings")

    if booking.payment_status == "canceled":
        messages.warning(request, "This booking is already canceled.")
        return redirect("my_bookings")

    # ✅ Adjust tickets
    booking.canceled_tickets = booking.tickets_booked
    booking.tickets_booked = 0
    booking.payment_status = "canceled"
    booking.save()

    messages.success(
        request,
        f"Booking for {booking.event.title} canceled. {booking.canceled_tickets} tickets released."
    )
    return redirect("my_bookings")


@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(customer=request.user).select_related("event").order_by("-created_at")
    return render(request, "profile/my_bookings.html", {"bookings": bookings})



def ticket_view(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    event = booking.event

    # Generate absolute URL for the ticket verification/view page
    ticket_url = request.build_absolute_uri(
        reverse("ticket_view", args=[booking.id])  # make sure "ticket_view" is in urls.py
    )

    # Generate QR with the ticket URL
    qr = qrcode.make(ticket_url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    return render(request, "profile/ticket.html", {
        "booking": booking,
        "event": event,
        "qr_code": qr_code_base64,
        "ticket_url": ticket_url,  # optional: display the link too
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