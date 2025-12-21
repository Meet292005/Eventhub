from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timedelta

# -------------------------------
# Profile Model
# Stores the role of each user (Admin, Organizer, Customer)
# This helps in role-based redirection and permissions.
# -------------------------------
class Profile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('organizer', 'Organizer'),
        ('customer', 'Customer'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    hub_tokens = models.PositiveIntegerField(default=0)  # 🪙 new field for HUB tokens


    def __str__(self):
        return f'{self.user.username} Profile'


# -------------------------------
# Customer Model
# Stores additional information for customers (profile image, contact details, preferences)
# This is separate from Profile so that only customers have these fields.
# -------------------------------
class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.jpg')
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=50, blank=True)
    interests = models.TextField(blank=True)
    dob = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return f'{self.user.username} (Customer)'


# -------------------------------
# Organizer Model
# Stores details about event organizers, including payment/payout information
# for receiving ticket sales revenue.
# -------------------------------
class Organizer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organization_name = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to='organizer_profiles/', default='organizer_profiles/default.jpg', blank=True, null=True)
    website = models.URLField(blank=True)
    phone = models.CharField(max_length=15)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    # Payment/Payout details for receiving ticket money
    bank_account_number = models.CharField(max_length=50, blank=True, help_text="Organizer's bank account number")
    bank_ifsc_code = models.CharField(max_length=20, blank=True, help_text="IFSC code for bank transfers")
    bank_name = models.CharField(max_length=100, blank=True, null=True)

    
    upi_id = models.CharField(max_length=100, blank=True, help_text="UPI ID for instant payments")
 
    def __str__(self):
        return self.organization_name or self.user.username


# -------------------------------
# Event Model
# Stores details about events created by organizers, including category, capacity,
# pricing, and registration deadlines.
# -------------------------------from django.db import models

class Event(models.Model):
    CATEGORY_CHOICES = [
        ('music', 'Music'),
        ('sports', 'Sports'),
        ('tech', 'Technology'),
        ('art', 'Art'),
        ('education', 'Education'),
        ('other', 'Other'),
        ('health', 'Health & Wellness'),
        ('food', 'Food & Drink'),
    ]

    organizer = models.ForeignKey("user.Organizer", on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    host = models.CharField(max_length=255, blank=True, null=True)
    special_attractions = models.TextField(blank=True, null=True)

    # 🕒 Event schedule
    date = models.DateField()
    time = models.TimeField()  # Start time
    end_time = models.TimeField(blank=True, null=True)  # ✅ Added end time

    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    banner = models.ImageField(upload_to='event_banners/', default='event_banners/event_default.jpg', blank=True, null=True)
    capacity = models.PositiveIntegerField(default=100)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    created_at = models.DateTimeField(auto_now_add=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    terms_and_conditions = models.TextField(blank=True, null=True)
    registration_deadline = models.DateField(blank=True, null=True)
    registrations_count = models.PositiveIntegerField(default=0)  # auto-updated when someone registers

    def __str__(self):
        return self.title

    @property
    def total_registrations(self):
        """
        Count seats that are actually assigned to PAID bookings.
        This automatically respects cancellations, because we free seats.
        """
        return self.seats.filter(
            booking__isnull=False,
            booking__payment_status="paid",
        ).count()

    @property
    def available_seats(self):
        """Remaining seats based on Seat allocation."""
        used = self.total_registrations
        return max(0, self.capacity - used)


    @property
    def is_full(self):
        return self.available_seats <= 0

    @property
    def duration(self):
        """🕒 Calculate event duration in hours and minutes"""
        if not self.end_time:
            return None

        start_dt = datetime.combine(self.date, self.time)
        end_dt = datetime.combine(self.date, self.end_time)

        # Handle case where event crosses midnight
        if end_dt < start_dt:
            end_dt += timedelta(days=1)

        delta = end_dt - start_dt
        hours, remainder = divmod(delta.seconds, 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"
    


# --- add this TokenTransaction model (anywhere in models.py, e.g. after Profile) ---
class TokenTransaction(models.Model):
    """
    Track HUB token earnings / usage for auditing and displaying history.
    `change` is positive when earned, negative when used.
    """
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="token_transactions")
    booking = models.ForeignKey("Booking", on_delete=models.SET_NULL, null=True, blank=True)
    change = models.IntegerField()  # +ve earned, -ve used
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.profile.user.username}: {self.change} ({self.reason})"


# -------------------------------
# Booking Model
# Stores ticket booking details for customers, linked to events.
# Includes automatic total price calculation and payment status.
# -------------------------------
class Booking(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="bookings")
    customer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    order_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    booking_name = models.CharField(max_length=255, blank=True, null=True)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    tickets_booked = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0.00)
    booking_date = models.DateTimeField(auto_now_add=True)
    canceled_tickets = models.PositiveIntegerField(default=0)  # ✅ new field
     # NEW fields
    hub_tokens_used = models.PositiveIntegerField(default=0)  # reserved/used tokens for this booking
    hub_tokens_awarded = models.PositiveIntegerField(default=0)  # Tokens earned from this booking

    amount_to_pay = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))  # after discount




    payment_status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("paid", "Paid"),("canceled", "Canceled"),],
        default="pending",
    )

     # ✅ New field for refund tracking
    REFUND_STATUS_CHOICES = [
        ("not_applicable", "Not Applicable"),
        ("pending", "Pending"),
        ("refunded", "Refunded"),
        ("failed", "Failed"),
    ]
    refund_status = models.CharField(
        max_length=20,
        choices=REFUND_STATUS_CHOICES,
        default="not_applicable",
    )


    razorpay_link_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)

    razorpay_refund_id = models.CharField(max_length=100, blank=True, null=True)  
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    attended = models.BooleanField(default=False)  # Track attendance


    def save(self, *args, **kwargs):
        if self.event and self.tickets_booked:
            # Check seat availability (for paid bookings)
            if self.payment_status == "paid" and self.tickets_booked > self.event.available_seats:
                raise ValueError("Not enough seats available for this booking.")

            # Auto calculate price
            self.total_price = Decimal(self.tickets_booked) * Decimal(self.event.price)

        super().save(*args, **kwargs)

    @property
    def active_tickets(self):
         return self.tickets_booked - self.canceled_tickets


    def __str__(self):
        return f"{self.booking_name} - {self.event.title} ({self.tickets_booked} tickets)"
    
class Seat(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="seats")
    seat_no = models.PositiveIntegerField()  # 1..capacity
    booking = models.ForeignKey(
        Booking,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seats",
    )

    class Meta:
        unique_together = ("event", "seat_no")
        ordering = ["seat_no"]

    def __str__(self):
        return f"{self.event.title} - Seat {self.seat_no}"


class SavedEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_events")
    event = models.ForeignKey("Event", on_delete=models.CASCADE, related_name="saved_by")
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "event")  # Prevent saving same event twice

    def __str__(self):
        return f"{self.user.username} saved {self.event.title}"
    
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    event = models.ForeignKey('Event', on_delete=models.CASCADE, related_name='reviews')
    text = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'event')  # 1 review per user per event
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} – {self.event.title}"
    
class SiteNotification(models.Model):
    NOTIFICATION_TYPES = (
        ("new_event", "New Event"),
        ("popular_event", "Popular Event"),
    )

    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # users who already saw this notification
    seen_by = models.ManyToManyField(User, blank=True, related_name="seen_notifications")

    def __str__(self):
        return f"{self.title} ({self.notification_type})"
    
