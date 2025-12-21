
from django.urls import path,include
from . import views
from django.conf import settings
from django.conf.urls.static import static
from .admin import eventhub_admin  # adjust import path as needed

urlpatterns = [
   
     path('admin/', eventhub_admin.urls),

    # ==========================
    # 🔹 Authentication URLs
    # ==========================
    path("", views.register, name="register"),        # User registration
    path("login/", views.login_user, name="login"),   # User login
    path("logout/", views.logout_user, name="logout"),# User logout

    # --------------------------
    # Forgot password / OTP flow
    # --------------------------
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("reset-password/", views.reset_password, name="reset_password"),


    # ==========================
    # 🔹 User Dashboard & Profile
    # ==========================
    path("dashboard/", views.dashboard, name="dashboard"),           # User dashboard
    path("profile/", views.profile, name="profile"),                 # User profile view
    path("edit_profile/", views.edit_profile, name="edit_profile"),  # Edit user profile

    # ==========================
    # 🔹 Organizer Dashboard & Profile
    # ==========================
    path("organizer/dashboard/", views.organizer_dashboard, name="organizer_dashboard"),    # Organizer dashboard
    path("organizer/profile", views.organizer_profile, name="organizer_profile"),           # Organizer profile view
    path("organizer/edit_profile/", views.organizer_edit_profile, name="organizer_edit_profile"),  # Edit organizer profile

    # ==========================
    # 🔹 Organizer Event Management
    # ==========================
    path("organizer/events/create/", views.create_event, name="create_event"),     # Create new event
    path("organizer/events/list/", views.event_list, name="event_list"),           # List all events
    path("organizer/event/<int:event_id>/", views.event_detail, name="event_detail"),  # Event details
    path("organizer/event/<int:event_id>/update/", views.update_event, name="update_event"),  # Update event
    path("organizer/events/select-update/", views.select_event_to_update, name="select_event_to_update"), # Select event to update
    path("organizer/event/<int:event_id>/delete/", views.delete_event, name="delete_event"),  # Delete event
    path("organizer/event/<int:event_id>/delete/confirm/", views.confirm_delete_event, name="confirm_delete_event"), # Confirm delete
    path("organizer/bookings/", views.organizer_bookings, name="organizer_bookings"),
    path("organizer/reviews/", views.organizer_reviews, name="organizer_reviews"),



    # ==========================
    # 🔹 Customer Events & Booking
    # ==========================
    path("events/", views.all_events, name="all_events"),                   # All events listing
    path("event/<int:event_id>/", views.user_event_detail, name="user_event_detail"), # Event details for customer
    path("event/<int:event_id>/book/", views.book_event, name="book_event"), # Book event (customer)
    path("about/", views.about_us, name="about_us"),                        # About us page
    path("contact/", views.contact, name="contact"),                        # Contact page
    path("event/<int:event_id>/save/", views.save_event, name="save_event"),
    path('reviews/', views.review_events_list, name='user-review-events'),
    path('reviews/<int:event_id>/', views.submit_review, name='submit-review'),
path("event/<int:event_id>/remove/", views.remove_saved_event, name="remove_saved_event"),
path("saved-events/", views.saved_events, name="saved_events"),
path('user/recommended/', views.recommended_events, name='recommended_events'),


    # ==========================
    # 🔹 Payment & Razorpay Integration
    # ==========================
    path("book/<int:event_id>/", views.book_event, name="book_event"),    # Duplicate booking route (can merge later)
    path("webhook/razorpay/", views.razorpay_webhook, name="razorpay_webhook"), # Razorpay webhook endpoint
    path("book_success/", views.payment_success, name="payment_success"), # Payment success callback

    # ==========================
    # 🔹 My Bookings & Tickets
    # ==========================
    path("my_bookings/", views.my_bookings, name="my_bookings"),         # Show all user bookings
    path("ticket/<int:booking_id>/", views.ticket_view, name="ticket_view"), # Ticket view page
    path("cancel-booking/<int:booking_id>/", views.cancel_tickets, name="cancel_tickets"), #cancel ticket

    # path("verify_ticket/<int:booking_id>/", views.verify_ticket, name="verify_ticket"), # (Optional) ticket verification



    # urls.py

    path("organizer/verify-customers/", views.verify_customers, name="verify_customers"),
    path("organizer/verify-customers/<int:event_id>/", views.verify_event_customers, name="verify_event_customers"),
    path("organizer/verify-customers/mark/<int:booking_id>/", views.mark_attended, name="mark_attended"),
    path("organizer/verify-customers/qr/<int:booking_id>/", views.verify_ticket_qr, name="verify_ticket_qr"),
    path("organizer/scan-qr/<int:event_id>/", views.scan_qr_page, name="scan_qr_page"),
    path("organizer/verify-ticket/", views.verify_ticket, name="verify_ticket"),
    path('user/organizer/reviews/', views.organizer_reviews, name='organizer-reviews'),
    path("organizer/scan-qr/", views.scan_qr_dashboard, name="scan_qr_dashboard"),

    path("notifications/fetch/", views.fetch_site_notifications, name="fetch_site_notifications"),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),

    path("upcoming-features/", views.upcoming_features, name="upcoming_features"),
    path("payment/webhook/", views.razorpay_webhook, name="razorpay_webhook")


] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)