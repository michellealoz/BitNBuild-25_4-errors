from django.urls import path
from . import views

urlpatterns = [
	path('', views.landing_page, name='landing_page'),
    path('information/', views.information_view, name='information_page'),
    path('about/', views.about_view, name='about_page'),
]