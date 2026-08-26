from django.urls import path
from . import views
from .views import toggle_language_view  # (Agar imported nahi hai to)
urlpatterns = [
    # Candidate Flow
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('edit/<str:reg_no>/', views.edit_candidate_view, name='edit_candidate'),
    path('preview/<str:reg_no>/', views.preview_view, name='preview'),
    path('payment-success/<str:reg_no>/', views.payment_success_view, name='payment_success'),
    
    # OTP Verification APIs
    path('api/send-otp/', views.send_otp_view, name='send_otp'),
    path('api/verify-otp/', views.verify_otp_view, name='verify_otp'),
    
    # Candidate Portal & Downloads
    path('track/', views.track_status_view, name='track_status'),
    path('candidate/login/', views.candidate_login_view, name='candidate_login'),
    path('candidate/dashboard/', views.candidate_dashboard_view, name='candidate_dashboard'),
    path('candidate/logout/', views.candidate_logout_view, name='candidate_logout'),
    
    # Document Downloads & Aliases
    path('download/slip/<str:reg_no>/', views.download_pdf_view, name='download_slip'),
    path('download/pdf/<str:reg_no>/', views.download_pdf_view, name='download_pdf'),
    path('download/admit-card/<str:reg_no>/', views.download_admit_card_view, name='download_admit_card'),
    path('download/scorecard/<str:reg_no>/', views.download_scorecard_view, name='download_scorecard'),

    # Grievance Helpdesk
    path('helpdesk/', views.helpdesk_view, name='helpdesk'),
    path('helpdesk/status/', views.view_ticket_status_view, name='ticket_status'),

    # Staff & Center Incharge Operations Desk
    path('staff/login/', views.staff_login_view, name='staff_login'),
    path('staff/dashboard/', views.incharge_dashboard_view, name='incharge_dashboard'),
    path('staff/scanner/', views.qr_scanner_view, name='qr_scanner'),
    path('staff/api/verify-candidate/', views.verify_candidate_api, name='verify_candidate_api'),
    path('staff/attendance-sheet/', views.print_attendance_sheet_view, name='print_attendance_sheet'),
    path('staff/bench-slips/', views.print_bench_slips_view, name='print_bench_slips'),
    
    # Result Evaluation Desk
    path('staff/evaluation-desk/', views.result_evaluation_desk_view, name='result_evaluation_desk'),
    path('staff/evaluation-desk/save-single/', views.save_single_mark_api, name='save_single_mark_api'),
    path('staff/evaluation-desk/bulk-publish/', views.bulk_publish_results_view, name='bulk_publish_results'),
    path('answer-key/', views.answer_key_view, name='answer_key'),
    path('staff/analytics/', views.live_attendance_analytics_view, name='live_attendance_analytics'),
    path('toggle-language/', toggle_language_view, name='toggle_language'),
]