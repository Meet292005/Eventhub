# user/admin.py
"""
Custom EventHub admin site with a simple dashboard at /admin/.

- Uses Chart.js in the template (no matplotlib, no base64 images).
- Shows global stats: users, events, bookings, revenue, etc.
"""

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils import timezone
from django.apps import apps
from django.db.models import Sum, Count
from django.urls import path, reverse
from django.utils.http import urlencode
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import (
    Profile,
    Customer,
    Organizer,
    Event,
    Booking,
    TokenTransaction,
    SavedEvent,
)
from django.contrib.auth.models import User

from .form import ProfileWithUserForm


class EventHubAdminSite(AdminSite):
    site_header = "EventHub Admin"
    site_title = "EventHub Admin"
    index_title = "Dashboard"

    def get_urls(self):
        """
        Keep the normal admin URLs, but ensure "" (index) goes
        through our custom index() so we can inject dashboard context.
        """
        urls = super().get_urls()
        custom = [path("", self.admin_view(self.index), name="index")]
        return custom + urls

    def index(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}

        # ---------- BASIC COUNTS ----------
        total_users = Profile.objects.count()
        total_customers = Profile.objects.filter(role="customer").count()
        total_organizers = Profile.objects.filter(role="organizer").count()

        total_events = Event.objects.count()
        today = timezone.localdate()
        upcoming_events_count = Event.objects.filter(date__gte=today).count()

        # ---------- BOOKINGS / REVENUE ----------
        paid_bookings = Booking.objects.filter(payment_status__iexact="paid")

        tickets_sold = paid_bookings.aggregate(
            total=Sum("tickets_booked")
        )["total"] or 0

        total_revenue = paid_bookings.aggregate(
            total=Sum("total_price")
        )["total"] or 0

        total_capacity = Event.objects.aggregate(
            total=Sum("capacity")
        )["total"] or 0

        total_available = max((total_capacity or 0) - (tickets_sold or 0), 0)

        avg_tickets_per_event = 0
        if total_events > 0:
            avg_tickets_per_event = round(tickets_sold / total_events, 1)

        # ---------- REVENUE LAST 6 MONTHS ----------
        today_date = timezone.now().date()
        month_labels = []
        month_values = []

        # last 6 calendar months (including current)
        for i in range(5, -1, -1):
            year = today_date.year
            month = today_date.month - i
            while month <= 0:
                month += 12
                year -= 1

            month_labels.append(
                timezone.datetime(year, month, 1).strftime("%b")
            )

            month_start = timezone.datetime(year, month, 1).date()
            if month == 12:
                next_month = timezone.datetime(year + 1, 1, 1).date()
            else:
                next_month = timezone.datetime(year, month + 1, 1).date()

            month_end = next_month - timezone.timedelta(days=1)

            month_sum = paid_bookings.filter(
                booking_date__date__gte=month_start,
                booking_date__date__lte=month_end,
            ).aggregate(total=Sum("total_price"))["total"] or 0

            month_values.append(float(month_sum))

        # ---------- POPULAR EVENTS (TOP 4 BY TICKETS) ----------
        popular_events_qs = (
            paid_bookings.values("event")
            .annotate(total_tickets=Sum("tickets_booked"))
            .order_by("-total_tickets")[:4]
        )

        popular_events = []
        for row in popular_events_qs:
            try:
                ev = Event.objects.get(pk=row["event"])
                popular_events.append(
                    {
                        "title": ev.title,
                        "tickets": row["total_tickets"] or 0,
                        "date": ev.date,
                    }
                )
            except Event.DoesNotExist:
                continue

        # ---------- NEXT UPCOMING EVENT ----------
        upcoming_event = (
            Event.objects.filter(date__gte=today)
            .order_by("date")
            .first()
        )

        extra_context.update(
            {
                # cards
                "total_users": total_users,
                "total_customers": total_customers,
                "total_organizers": total_organizers,
                "total_events": total_events,
                "upcoming_events_count": upcoming_events_count,
                "tickets_sold": tickets_sold,
                "total_capacity": total_capacity,
                "total_available": total_available,
                "total_revenue": total_revenue,
                "avg_tickets_per_event": avg_tickets_per_event,
                # charts
                "revenue_labels": month_labels,
                "revenue_values": month_values,
                # lists
                "popular_events": popular_events,
                "upcoming_event": upcoming_event,
            }
        )
        return super().index(request, extra_context=extra_context)


# ---------- instantiate custom admin site ----------
eventhub_admin = EventHubAdminSite(name="eventhub_admin")


# ---------- MODEL ADMINS WITH CUSTOM TEMPLATES ----------

class EventAdmin(admin.ModelAdmin):
    """
    Admin for Event model using custom list + form templates.
    Templates live in templates/admin/:
      - event_change_list.html
      - event_change_form.html
    """
    change_list_template = "admin/event_change_list.html"
    change_form_template = "admin/event_change_form.html"

    list_display = ("title", "organizer", "category", "date", "time", "price")
    # 💡 IMPORTANT: allow filtering by organizer
    list_filter = ("organizer", "category", "date")
    search_fields = ("title", "organizer__organization_name", "organizer__user__username")

    def changelist_view(self, request, extra_context=None):
        """
        We pass `today` into the template so the event cards
        can compare deadlines / seats with current date.
        """
        extra_context = extra_context or {}
        extra_context["today"] = timezone.localdate()
        return super().changelist_view(request, extra_context=extra_context)


class BookingAdmin(admin.ModelAdmin):
    """
    Admin for Booking model using custom list + form templates.
    Templates:
      - admin/booking_change_list.html
      - admin/booking_change_form.html
    """
    change_list_template = "admin/booking_change_list.html"
    change_form_template = "admin/booking_change_form.html"

    list_display = (
        "event",
        "booking_name",
        "customer_email",
        "tickets_booked",
        "total_price",
        "payment_status",
        "booking_date",
    )
    list_filter = ("customer", "event", "payment_status", "refund_status", "created_at")
    search_fields = ("booking_name", "customer_email", "customer__username")
class ProfileAdmin(admin.ModelAdmin):
    """
    Admin for Profile model using custom list + form templates.

    Templates:
      - profile_change_list.html  -> card grid of users/profiles
      - profile_change_form.html  -> header card + customer/organizer detail cards
    """

    change_list_template = "admin/profile_change_list.html"
    change_form_template = "admin/profile_change_form.html"

    # 🔹 use our custom form that also edits auth.User
    form = ProfileWithUserForm

    # these are the fields that appear in the right-side form
    # (must match fields defined on ProfileWithUserForm)
    fields = (
        "user",           # read-only relation (disabled in form)
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "hub_tokens",
    )

    search_fields = ("user__username", "user__email")
    list_select_related = ("user",)

    list_display = ("user", "role", "hub_tokens",
                    "booking_count_display", "event_count_display")

    # ---------- annotate queryset with counts ----------
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            booking_count=Count("user__booking", distinct=True),
            event_count=Count("user__organizer__event", distinct=True),
        )

    def booking_count_display(self, obj):
        return getattr(obj, "booking_count", 0)
    booking_count_display.short_description = "Bookings"

    def event_count_display(self, obj):
        return getattr(obj, "event_count", 0)
    event_count_display.short_description = "Events"

    # ---------- list view extra context (unchanged) ----------
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        booking_changelist = reverse(
            f"admin:{Booking._meta.app_label}_{Booking._meta.model_name}_changelist"
        )
        event_changelist = reverse(
            f"admin:{Event._meta.app_label}_{Event._meta.model_name}_changelist"
        )

        extra_context["booking_changelist_base"] = booking_changelist
        extra_context["event_changelist_base"] = event_changelist

        return super().changelist_view(request, extra_context=extra_context)

    # ---------- change view context (unchanged) ----------
    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        profile = self.get_object(request, object_id)

        if profile:
            user = profile.user

            customer = getattr(user, "customer", None)
            organizer = getattr(user, "organizer", None)

            extra_context["customer_obj"] = customer
            extra_context["organizer_obj"] = organizer

            booking_qs = Booking.objects.filter(customer=user)
            booking_count = booking_qs.count()

            event_qs = Event.objects.none()
            if organizer:
                event_qs = Event.objects.filter(organizer=organizer)
            event_count = event_qs.count()

            booking_changelist = reverse(
                f"admin:{Booking._meta.app_label}_{Booking._meta.model_name}_changelist"
            )
            event_changelist = reverse(
                f"admin:{Event._meta.app_label}_{Event._meta.model_name}_changelist"
            )

            if booking_count:
                extra_context["customer_booking_count"] = booking_count
                extra_context["customer_bookings_url"] = (
                    f"{booking_changelist}?{urlencode({'customer__id__exact': user.id})}"
                )

            if organizer and event_count:
                extra_context["organizer_event_count"] = event_count
                extra_context["organizer_events_url"] = (
                    f"{event_changelist}?{urlencode({'organizer__id__exact': organizer.id})}"
                )

            extra_context["is_customer_role"] = profile.role == "customer"
            extra_context["is_organizer_role"] = profile.role == "organizer"

        return super().change_view(
            request, object_id, form_url=form_url, extra_context=extra_context
        )


# -

# ---------- Register models on custom admin site ----------

# models that just use default views
BASIC_MODELS = (Customer, Organizer, TokenTransaction, SavedEvent)

for model in BASIC_MODELS:
    try:
        eventhub_admin.register(model)
    except admin.sites.AlreadyRegistered:
        pass

# models with custom ModelAdmin
try:
    eventhub_admin.register(Event, EventAdmin)
except admin.sites.AlreadyRegistered:
    pass

try:
    eventhub_admin.register(Booking, BookingAdmin)
except admin.sites.AlreadyRegistered:
    pass

try:
    eventhub_admin.register(Profile, ProfileAdmin)
except admin.sites.AlreadyRegistered:
    pass
