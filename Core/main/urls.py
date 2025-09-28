from django.urls import path
from . import views
from .views import sentiment_timeline_api

urlpatterns = [
	path('', views.landing_page, name='landing_page'),
    path('information/', views.information_view, name='information_page'),
]

urlpatterns = [
    path('sentiment-timeline/', sentiment_timeline_api, name='sentiment-timeline'),
    # ... other endpoints ...
]
