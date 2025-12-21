"""
Main URL configuration for EventHub project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# ✅ If you have EventHub/views.py with a home function:
from . import views   # remove this line if home is inside "user/views.py"

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # Home page route
    path('', views.home, name='home'),  # 👈 If home is in user/views.py, replace with: from user import views

    # Routes from "user" app
    path('user/', include('user.urls')),
]

# ✅ Media serving in development (images, banners, etc.)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
