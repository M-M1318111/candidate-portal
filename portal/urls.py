from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('edit/<str:reg_no>/', views.edit_candidate_view, name='edit_candidate'),
    path('preview/<str:reg_no>/', views.preview_view, name='preview'),
    path('payment-success/<str:reg_no>/', views.payment_success_view, name='payment_success'),
    path('download-slip/<str:reg_no>/', views.download_pdf_view, name='download_pdf'),
    path('download-admit-card/<str:reg_no>/', views.download_admit_card_view, name='download_admit_card'),
    path('track/', views.track_status_view, name='track_status'),
    # Candidate Auth & Dashboard URLs
    path('login/', views.candidate_login_view, name='candidate_login'),
    path('dashboard/', views.candidate_dashboard_view, name='candidate_dashboard'),
    path('logout/', views.candidate_logout_view, name='candidate_logout'),
    path('helpdesk/', views.helpdesk_view, name='helpdesk'),
    path('helpdesk/status/', views.view_ticket_status_view, name='ticket_status'),
    path('api/send-otp/', views.send_otp_view, name='send_otp'),
    path('api/verify-otp/', views.verify_otp_view, name='verify_otp'), 
    path('logout/', views.candidate_logout_view, name='candidate_logout'),
    path('admin-dashboard/', views.executive_admin_dashboard_view, name='executive_admin_dashboard'),
    
    
]