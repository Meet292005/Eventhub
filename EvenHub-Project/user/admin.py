from django.contrib import admin
from .models import Profile, Customer, Organizer, Event, Booking


# Simple registrations
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    search_fields = ('user__username', 'user__email')
    list_filter = ('role',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'city', 'state', 'language', 'dob')
    search_fields = ('user__username', 'user__email', 'phone', 'city', 'state')
    list_filter = ('city', 'state', 'language')


@admin.register(Organizer)
class OrganizerAdmin(admin.ModelAdmin):
    list_display = ('user', 'organization_name', 'phone', 'city', 'state', 'website')
    search_fields = ('organization_name', 'user__username', 'phone', 'city', 'state')
    list_filter = ('city', 'state')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'organizer', 'date', 'time', 'location', 'category', 'price', 'capacity', 'registration_deadline')
    search_fields = ('title', 'location', 'organizer__organization_name')
    list_filter = ('category', 'date', 'location')
    ordering = ('-date',)

    
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_name', 'customer', 'event', 'tickets_booked', 'total_price', 'payment_status', 'booking_date')
    list_filter = ('payment_status', 'event')
    search_fields = ('booking_name', 'customer__username', 'customer_email')