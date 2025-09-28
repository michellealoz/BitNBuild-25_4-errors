from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='users/login.html',
        redirect_authenticated_user=True,
        next_page='/user/dashboard/'
    ), name='user_login'),
    path('signup/', views.user_signup, name='user_signup'),
    path('setup/', views.user_profile_setup_view, name='user_profile_setup'),
    path('complete/', views.user_profile_complete, name='user_profile_complete'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('compare/', views.compare_product, name='compare'),
    path('analyzer/', views.analysis_view, name='analyzer'),
    path('records/', views.records_view, name='records'), 
    path('records/delete/<str:record_type>/<int:record_id>/', views.delete_record_view, name='delete_record'),
]