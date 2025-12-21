# signals.py
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Organizer, Profile
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Event, Booking, SiteNotification


@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        instance.profile.save()





# ===============================
# NEW EVENT NOTIFICATION
# ===============================
@receiver(post_save, sender=Event)
def notify_new_event(sender, instance, created, **kwargs):
    """
    Create notification when organizer adds a new event
    """
    if created:
        SiteNotification.objects.get_or_create(
            event=instance,
            notification_type="new_event",
            defaults={
                "title": "🎉 New Event Live",
                "message": f"{instance.title} is now open for registration."
            }
        )


# ===============================
# POPULAR EVENT NOTIFICATION
# ===============================
@receiver(post_save, sender=Booking)
def notify_popular_event(sender, instance, created, **kwargs):
    """
    Trigger when event becomes popular (based on PAID bookings)
    """
    if instance.payment_status != "paid":
        return

    event = instance.event

    # Count real paid bookings
    paid_count = Booking.objects.filter(
        event=event,
        payment_status="paid"
    ).count()

    event.registrations_count = paid_count
    event.save(update_fields=["registrations_count"])

    POPULAR_THRESHOLD = 50  # change if needed

    if paid_count >= POPULAR_THRESHOLD:
        SiteNotification.objects.get_or_create(
            event=event,
            notification_type="popular_event",
            defaults={
                "title": "🔥 Popular Event",
                "message": f"{event.title} is filling fast. Book now!"
            }
        )
