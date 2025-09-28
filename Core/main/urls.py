from django.urls import path
from . import views
from .views import sentiment_timeline_api

urlpatterns = [
	path('', views.landing_page, name='landing_page'),
    path('information/', views.information_view, name='information_page'),
<<<<<<< HEAD
    path('about/', views.about_view, name='about_page'),
]
=======
]

urlpatterns = [
    path('sentiment-timeline/', sentiment_timeline_api, name='sentiment-timeline'),
    # ... other endpoints ...
]
>>>>>>> b5b45be919248d34ce22af5e5e9d16b0f8ea9c95
