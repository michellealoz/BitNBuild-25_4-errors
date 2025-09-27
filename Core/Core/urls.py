# Core/urls.py

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('user/', include('users.urls')),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('', include('main.urls')),
]