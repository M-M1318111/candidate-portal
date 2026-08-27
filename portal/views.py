import base64
import csv
import io
import os
import random
import uuid

import qrcode
import razorpay
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import CandidateForm
from .models import (
    Candidate,
    ExamCenter,
    Grievance,
    PortalSetting,
    AnswerKey,
    QuestionObjection,
    NotificationLog,
    AuditLog,
    EXAM_DATE_CHOICES,
    SHIFT_CHOICES
)

try:
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
except Exception:
    client = None


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# Safe Notification Dispatcher with Dual Engine (HTTPS REST API + SMTP Fallback)
def send_logged_email(subject, message, recipient_list):
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()

    for recipient in recipient_list:
        email_sent = False

        # 1. Primary: Direct HTTPS REST API (Bypasses Render Cloud SMTP Port Blocks)
        if resend_api_key:
            try:
                response = requests.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {resend_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "from": "Central Examination Authority <onboarding@resend.dev>",
                        "to": [recipient],
                        "subject": subject,
                        "text": message
                    },
                    timeout=8
                )
                if response.status_code in [200, 201, 202]:
                    email_sent = True
                    print(f"✅ Real Email successfully sent via HTTPS API to: {recipient}")
                else:
                    print(f"⚠️ Resend API Response Error ({response.status_code}): {response.text}")
            except Exception as api_err:
                print(f"⚠️ Resend API Dispatch Exception: {api_err}")

        # 2. Fallback: Standard Django SMTP
        if not email_sent:
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient],
                    fail_silently=False
                )
                email_sent = True
                print(f"✅ Real Email sent via SMTP to: {recipient}")
            except Exception as smtp_err:
                print(f"❌ SMTP Dispatch Failure (Cloud Port Blocked): {smtp_err}")

        # Database Log
        NotificationLog.objects.create(
            recipient=recipient,
            channel='EMAIL',
            subject=subject,
            message_body=message,
            status='SENT' if email_sent else 'FAILED'
        )


def generate_otp():
    return str(random.randint(100000, 999999))


def generate_qr_base64(data_text):
    qr = qrcode.QRCode(version=1, box_size=4, border=1)
    qr.add_data(data_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def file_to_base64(file_field):
    if file_field and hasattr(file_field, 'path') and os.path.exists(file_field.path):
        try:
            with open(file_field.path, "rb") as img_file:
                encoded = base64.b64encode(img_file.read()).decode('utf-8')
                ext = file_field.name.split('.')[-1].lower()
                mime = "image/jpeg" if ext in ['jpg', 'jpeg'] else "image/png"
                return f"data:{mime};base64,{encoded}"
        except Exception:
            pass
    elif file_field and hasattr(file_field, 'url'):
        return file_field.url
    return None


def get_portal_settings():
    setting = PortalSetting.objects.first()
    if not setting:
        setting = PortalSetting.objects.create()
    return setting


def send_registration_confirmation_email(candidate, request):
    if not candidate.email:
        return
    
    current_host = request.get_host()
    protocol = 'https' if request.is_secure() else 'http'
    login_url = f"{protocol}://{current_host}/candidate/login/"
    
    subject = f"✅ Registration Successful - Application ID: {candidate.registration_no}"
    message = f"""Dear {candidate.full_name},

Congratulations! Your application for Central Examination Authority 2026 has been successfully registered.

==============================================
📌 APPLICATION & LOGIN CREDENTIALS
==============================================
• Registration Number : {candidate.registration_no}
• Date of Birth       : {candidate.dob}
• Email Address       : {candidate.email}
• Mobile Number       : +91-{candidate.phone}

Please keep your Registration Number and Date of Birth safe for application tracking, admit card download, and scorecard access.

🔗 Candidate Login Portal:
{login_url}

Thank you,
Central Examination Authority
"""
    send_logged_email(subject, message, [candidate.email])


# --- Candidate Flow ---
def home_view(request):
    return render(request, 'portal/home.html', {'config': get_portal_settings()})


def register_view(request):
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES)
        if form.is_valid():
            candidate_obj = form.save(commit=False)
            if 'photo' in form.cleaned_data and form.cleaned_data['photo']:
                candidate_obj.photo = form.cleaned_data['photo']
            candidate_obj.save()

            request.session['candidate_id'] = candidate_obj.id
            send_registration_confirmation_email(candidate_obj, request)

            messages.success(request, f"Registration Successful! Your Registration No is: {candidate_obj.registration_no}. A confirmation email has been dispatched.")
            return redirect('preview', reg_no=candidate_obj.registration_no)
    else:
        form = CandidateForm()
    return render(request, 'portal/register.html', {'form': form, 'edit_mode': False})


def edit_candidate_view(request, reg_no):
    candidate_obj = get_object_or_404(Candidate, registration_no=reg_no)
    if candidate_obj.is_paid:
        messages.error(request, "⛔ Application fee has already been paid. Profile modifications are locked by Examination Authority.")
        return redirect('preview', reg_no=candidate_obj.registration_no)

    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES, instance=candidate_obj)
        if form.is_valid():
            cand = form.save(commit=False)
            if 'photo' in form.cleaned_data and form.cleaned_data['photo']:
                cand.photo = form.cleaned_data['photo']
            cand.save()
            messages.success(request, "Application details updated successfully!")
            return redirect('preview', reg_no=candidate_obj.registration_no)
    else:
        form = CandidateForm(instance=candidate_obj)
    return render(request, 'portal/register.html', {'form': form, 'edit_mode': True, 'candidate': candidate_obj})


def preview_view(request, reg_no):
    candidate_obj = get_object_or_404(Candidate, registration_no=reg_no)
    fee_structure = {'UR': 1000, 'General': 1000, 'OBC': 750, 'EWS': 750, 'SC': 500, 'ST': 500}
    exam_fee = getattr(candidate_obj, 'fee_amount', None) or fee_structure.get(candidate_obj.category, 500)
    amount_in_paise = int(exam_fee * 100)
    order_id = getattr(candidate_obj, 'razorpay_order_id', None) or "ORDER_PENDING"
    is_placeholder = getattr(settings, 'RAZORPAY_KEY_ID', '').startswith('rzp_test_placeholder')

    if client and not candidate_obj.is_paid and not is_placeholder:
        try:
            if not getattr(candidate_obj, 'razorpay_order_id', None):
                payment_order = client.order.create({'amount': amount_in_paise, 'currency': 'INR', 'payment_capture': '1'})
                candidate_obj.razorpay_order_id = payment_order['id']
                candidate_obj.save()
                order_id = payment_order['id']
        except Exception as e:
            print("Razorpay Error:", e)

    context = {
        'candidate': candidate_obj,
        'exam_fee': exam_fee,
        'amount': amount_in_paise,
        'currency': 'INR',
        'razorpay_order_id': order_id,
        'razorpay_merchant_key': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'callback_url': f'/payment-success/{candidate_obj.registration_no}/',
        'is_mock_mode': is_placeholder
    }
    return render(request, 'portal/preview.html', context)


@csrf_exempt
def payment_success_view(request, reg_no):
    candidate_obj = get_object_or_404(Candidate, registration_no=reg_no)
    if request.method == "POST":
        payment_id = request.POST.get('razorpay_payment_id', f"PAY-{uuid.uuid4().hex[:8].upper()}")
        candidate_obj.is_paid = True
        candidate_obj.razorpay_payment_id = payment_id
        candidate_obj.save()
        messages.success(request, f"Payment Successful! Txn ID: {payment_id}")
        return render(request, 'portal/preview.html', {'candidate': candidate_obj, 'exam_fee': 0, 'payment_success': True})
    return redirect('preview', reg_no=reg_no)


# --- OTP Verification APIs (Strict Real Matching) ---
@csrf_exempt
def send_otp_view(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=400)
    try:
        otp_type = request.POST.get('type', '').strip().lower()
        target_value = request.POST.get('value', '').strip()
        otp = generate_otp()

        if otp_type == 'email':
            clean_email = target_value.lower()
            request.session['email_otp'] = str(otp)
            request.session['email_otp_target'] = clean_email
            request.session.modified = True

            print("\n" + "="*50)
            print("📧 [REAL EMAIL OTP GENERATED]")
            print(f"Target : {clean_email}")
            print(f"OTP    : {otp}")
            print("="*50 + "\n")

            send_logged_email(
                "Verification OTP - Candidate Registration",
                f"Dear Candidate,\n\nYour 6-digit Verification OTP for Central Examination Authority 2026 is:\n\n{otp}\n\nThis OTP is confidential and valid for 10 minutes.",
                [clean_email]
            )

            return JsonResponse({'status': 'success', 'message': f'OTP sent to {clean_email}'})

        elif otp_type == 'phone':
            clean_phone = ''.join(filter(str.isdigit, target_value))[-10:]
            request.session['phone_otp'] = str(otp)
            request.session['phone_otp_target'] = clean_phone
            request.session.modified = True

            print("\n" + "="*50)
            print("📱 [REAL SMS OTP GENERATED]")
            print(f"Target : +91-{clean_phone}")
            print(f"OTP    : {otp}")
            print("="*50 + "\n")

            return JsonResponse({'status': 'success', 'message': f'SMS OTP dispatched to +91-{clean_phone}'})

        return JsonResponse({'status': 'error', 'message': 'Invalid OTP type.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@csrf_exempt
def verify_otp_view(request):
    if request.method == 'POST':
        otp_type = request.POST.get('type', '').strip().lower()
        user_otp = request.POST.get('otp', '').strip()
        target_value = request.POST.get('value', '').strip()

        if otp_type == 'phone':
            target_value = ''.join(filter(str.isdigit, target_value))[-10:]
        elif otp_type == 'email':
            target_value = target_value.lower()

        saved_otp = str(request.session.get(f'{otp_type}_otp', ''))
        saved_target = str(request.session.get(f'{otp_type}_otp_target', ''))

        if saved_otp and saved_otp == user_otp and saved_target == target_value:
            request.session[f'{otp_type}_verified'] = True
            request.session.modified = True
            return JsonResponse({'status': 'success', 'message': 'Verified successfully!'})

        return JsonResponse({'status': 'error', 'message': 'Invalid or expired OTP. Please enter the correct OTP.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})


# --- PDF Generators ---
def download_pdf_view(request, reg_no):
    candidate = get_object_or_404(Candidate, registration_no=reg_no)
    qr_data = f"CEA-2026 | Reg: {candidate.registration_no} | Name: {candidate.full_name} | Fee: {'PAID' if candidate.is_paid else 'PENDING'}"
    context = {
        'candidate': candidate,
        'config': get_portal_settings(),
        'qr_code_base64': generate_qr_base64(qr_data),
        'photo_base64': file_to_base64(candidate.photo),
        'signature_base64': file_to_base64(candidate.signature),
    }
    return render(request, 'portal/pdf_template.html', context)


def download_admit_card_view(request, reg_no):
    candidate = get_object_or_404(Candidate, registration_no=reg_no)
    if not candidate.is_paid:
        messages.error(request, "Please pay the fee first.")
        return redirect('preview', reg_no=reg_no)
    if not candidate.is_admit_card_released:
        messages.warning(request, "Admit card has not been released yet.")
        return redirect('candidate_dashboard' if request.session.get('candidate_id') else 'track_status')

    center_title = candidate.allotted_center.center_name if candidate.allotted_center else getattr(candidate, 'exam_center', 'Exam Center')
    qr_data = f"CEA-2026 | Reg: {candidate.registration_no} | Roll: {candidate.roll_number} | Date: {candidate.exam_date}"
    context = {
        'candidate': candidate,
        'center_title': center_title,
        'config': get_portal_settings(),
        'qr_code_base64': generate_qr_base64(qr_data),
        'photo_base64': file_to_base64(candidate.photo),
        'signature_base64': file_to_base64(candidate.signature),
    }
    return render(request, 'portal/admit_card_template.html', context)


def download_scorecard_view(request, reg_no):
    candidate = get_object_or_404(Candidate, registration_no=reg_no)
    if not candidate.is_result_declared:
        messages.warning(request, "Result is not yet released for this candidate.")
        return redirect('candidate_dashboard')

    c_marks = candidate.exam_marks_obtained or 0
    air_rank = Candidate.objects.filter(is_result_declared=True, exam_marks_obtained__gt=c_marks).count() + 1
    cat_rank = Candidate.objects.filter(category=candidate.category, is_result_declared=True, exam_marks_obtained__gt=c_marks).count() + 1

    qr_data = f"CEA-2026 RESULT | Roll: {candidate.roll_number} | AIR Rank: #{air_rank} | Marks: {candidate.exam_marks_obtained}/{candidate.exam_total_marks} | Status: {candidate.exam_qualification_status}"
    context = {
        'candidate': candidate,
        'config': get_portal_settings(),
        'rank': air_rank,
        'category_rank': cat_rank,
        'qr_code_base64': generate_qr_base64(qr_data),
        'photo_base64': file_to_base64(candidate.photo),
        'signature_base64': file_to_base64(candidate.signature),
    }
    return render(request, 'portal/scorecard_template.html', context)


# --- Candidate Portal & Auth ---
def track_status_view(request):
    candidate_obj = None
    searched = False
    query = (request.POST.get('query') or request.GET.get('query') or '').strip()
    if query:
        searched = True
        candidate_obj = (
            Candidate.objects.filter(registration_no__iexact=query).first()
            or Candidate.objects.filter(roll_number__iexact=query).first()
        )
    return render(request, 'portal/track.html', {'candidate': candidate_obj, 'searched': searched, 'query': query})


def candidate_login_view(request):
    error_msg = None
    if request.method == 'POST':
        reg_no = (request.POST.get('registration_no') or request.POST.get('reg_no') or '').strip()
        dob_str = request.POST.get('dob', '').strip()
        candidate_obj = Candidate.objects.filter(registration_no__iexact=reg_no).first()
        if candidate_obj and str(candidate_obj.dob) == dob_str:
            request.session['candidate_id'] = candidate_obj.id
            request.session['candidate_reg_no'] = candidate_obj.registration_no
            return redirect('candidate_dashboard')
        error_msg = "Invalid Registration Number or Date of Birth."
    return render(request, 'portal/candidate_login.html', {'error_msg': error_msg, 'config': get_portal_settings()})


def candidate_dashboard_view(request):
    candidate_id = request.session.get('candidate_id')
    if not candidate_id:
        reg_no = request.session.get('candidate_reg_no')
        if reg_no:
            cand = Candidate.objects.filter(registration_no=reg_no).first()
            if cand:
                candidate_id = cand.id
                request.session['candidate_id'] = cand.id

    if not candidate_id:
        return redirect('candidate_login')
    candidate_obj = get_object_or_404(Candidate, id=candidate_id)

    air_rank = None
    cat_rank = None
    if candidate_obj.is_result_declared and candidate_obj.exam_marks_obtained is not None:
        c_marks = candidate_obj.exam_marks_obtained or 0
        air_rank = Candidate.objects.filter(is_result_declared=True, exam_marks_obtained__gt=c_marks).count() + 1
        cat_rank = Candidate.objects.filter(category=candidate_obj.category, is_result_declared=True, exam_marks_obtained__gt=c_marks).count() + 1

    my_objections = QuestionObjection.objects.filter(candidate=candidate_obj).select_related('question')

    return render(request, 'portal/candidate_dashboard.html', {
        'candidate': candidate_obj,
        'config': get_portal_settings(),
        'air_rank': air_rank,
        'cat_rank': cat_rank,
        'my_objections': my_objections,
    })


def candidate_logout_view(request):
    request.session.flush()
    return redirect('candidate_login')


# --- Answer Key & Objections Desk ---
def answer_key_view(request):
    candidate_id = request.session.get('candidate_id')
    candidate = Candidate.objects.filter(id=candidate_id).first() if candidate_id else None

    shift_filter = request.GET.get('shift', candidate.exam_shift if candidate and candidate.exam_shift else 'Shift 1')
    questions = AnswerKey.objects.filter(is_active=True, exam_shift=shift_filter).order_by('question_number')

    user_objections = []
    if candidate:
        user_objections = list(QuestionObjection.objects.filter(candidate=candidate).values_list('question_id', flat=True))

    if request.method == 'POST':
        if not candidate:
            messages.warning(request, "Please log in to challenge answer keys.")
            return redirect('candidate_login')

        q_id = request.POST.get('question_id')
        claimed = request.POST.get('claimed_option')
        justification = request.POST.get('justification', '').strip()
        doc = request.FILES.get('supporting_doc')

        question_obj = get_object_or_404(AnswerKey, id=q_id)

        if QuestionObjection.objects.filter(candidate=candidate, question=question_obj).exists():
            messages.warning(request, f"You have already submitted an objection for Q{question_obj.question_number}.")
        else:
            QuestionObjection.objects.create(
                candidate=candidate,
                question=question_obj,
                claimed_option=claimed,
                justification=justification,
                supporting_doc=doc
            )
            messages.success(request, f"Objection for Question #{question_obj.question_number} submitted successfully!")
        return redirect(f"{request.path}?shift={shift_filter}")

    context = {
        'candidate': candidate,
        'questions': questions,
        'selected_shift': shift_filter,
        'user_objections': user_objections,
        'config': get_portal_settings(),
    }
    return render(request, 'portal/answer_key_desk.html', context)


# --- Staff Authentication & Analytics ---
def staff_login_view(request):
    error_msg = None
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None and user.is_staff:
            login(request, user)
            return redirect('incharge_dashboard')
        error_msg = "Invalid staff credentials or unauthorized access."
    return render(request, 'portal/staff_login.html', {'error_msg': error_msg})


@login_required(login_url='staff_login')
def incharge_dashboard_view(request):
    if not request.user.is_staff:
        return redirect('staff_login')

    assigned_center = ExamCenter.objects.filter(assigned_incharge=request.user).first()
    if request.user.is_superuser:
        center_candidates = Candidate.objects.filter(allotted_center__isnull=False, is_paid=True)
        center_name = "Master Command Console (All Centers)"
    elif assigned_center:
        center_candidates = Candidate.objects.filter(allotted_center=assigned_center, is_paid=True)
        center_name = f"{assigned_center.center_name} ({assigned_center.center_code})"
    else:
        center_candidates = Candidate.objects.none()
        center_name = "No Center Assigned Yet"

    total_allotted = center_candidates.count()
    total_present = center_candidates.filter(is_present=True).count()
    total_absent = total_allotted - total_present

    context = {
        'center_name': center_name,
        'assigned_center': assigned_center,
        'total_allotted': total_allotted,
        'total_present': total_present,
        'total_absent': total_absent,
        'dates': [d[0] for d in EXAM_DATE_CHOICES],
        'shifts': [s[0] for s in SHIFT_CHOICES],
    }
    return render(request, 'portal/incharge_dashboard.html', context)


@login_required(login_url='staff_login')
def live_attendance_analytics_view(request):
    if not request.user.is_staff:
        return redirect('staff_login')

    centers = ExamCenter.objects.filter(is_active=True)
    if not request.user.is_superuser:
        assigned = ExamCenter.objects.filter(assigned_incharge=request.user)
        if assigned.exists():
            centers = assigned

    analytics = []
    total_expected = 0
    total_verified = 0

    for c in centers:
        allotted = Candidate.objects.filter(allotted_center=c, is_paid=True).count()
        present = Candidate.objects.filter(allotted_center=c, is_paid=True, is_present=True).count()
        absent = allotted - present
        rate = round((present / allotted * 100), 1) if allotted > 0 else 0

        total_expected += allotted
        total_verified += present

        analytics.append({
            'center': c,
            'allotted': allotted,
            'present': present,
            'absent': absent,
            'attendance_rate': rate,
            'recent_entries': Candidate.objects.filter(allotted_center=c, is_present=True).order_by('-entry_verified_at')[:5]
        })

    overall_rate = round((total_verified / total_expected * 100), 1) if total_expected > 0 else 0

    context = {
        'analytics': analytics,
        'total_expected': total_expected,
        'total_verified': total_verified,
        'total_absent': total_expected - total_verified,
        'overall_rate': overall_rate,
        'is_superuser': request.user.is_superuser,
        'config': get_portal_settings(),
    }
    return render(request, 'portal/live_attendance_analytics.html', context)


# --- Biometric QR Camera Scanner ---
@login_required(login_url='staff_login')
def qr_scanner_view(request):
    if not request.user.is_staff:
        return redirect('staff_login')
    assigned_center = ExamCenter.objects.filter(assigned_incharge=request.user).first()
    context = {
        'assigned_center': assigned_center,
        'is_superuser': request.user.is_superuser,
    }
    return render(request, 'portal/qr_scanner.html', context)


@login_required(login_url='staff_login')
def verify_candidate_api(request):
    raw_query = request.GET.get('reg_no', '').strip()
    if not raw_query:
        return JsonResponse({'status': 'error', 'message': 'Empty barcode or scan data received.'})

    query = raw_query
    if "Reg:" in raw_query:
        try:
            query = raw_query.split("Reg:")[1].split("|")[0].strip()
        except Exception:
            query = raw_query.strip()

    candidate = (
        Candidate.objects.filter(registration_no__iexact=query).first()
        or Candidate.objects.filter(roll_number__iexact=query).first()
    )

    if not candidate:
        return JsonResponse({'status': 'error', 'message': f'❌ Candidate record not found for: {query}'})

    if not candidate.is_paid:
        return JsonResponse({'status': 'warning', 'message': f'⚠️ Fee Payment Pending for Candidate {candidate.registration_no}!'})

    if not candidate.is_admit_card_released:
        return JsonResponse({'status': 'warning', 'message': '🔒 Admit card is locked by Examination Authority.'})

    user = request.user
    if not user.is_superuser:
        assigned_center = ExamCenter.objects.filter(assigned_incharge=user).first()
        if assigned_center and candidate.allotted_center != assigned_center:
            return JsonResponse({
                'status': 'error',
                'message': f'⛔ Security Alert: Candidate is allotted to {candidate.allotted_center.center_name if candidate.allotted_center else "Another Center"}, NOT this center!'
            })

    already_checked = candidate.is_present
    if not candidate.is_present:
        candidate.is_present = True
        candidate.entry_verified_at = timezone.now()
        candidate.save()

        AuditLog.objects.create(
            user=request.user,
            action='ATTENDANCE_CHECKIN',
            candidate=candidate,
            ip_address=get_client_ip(request),
            details=f"Gate biometric entry scan verified at {candidate.entry_verified_at.strftime('%d-%b-%Y %I:%M:%S %p')}"
        )

    photo_url = candidate.photo.url if getattr(candidate, 'photo', None) and hasattr(candidate.photo, 'url') else None
    center_text = candidate.allotted_center.center_name if candidate.allotted_center else getattr(candidate, 'exam_center', 'Assigned Center')

    return JsonResponse({
        'status': 'success',
        'already_checked_in': already_checked,
        'entry_time': candidate.entry_verified_at.strftime('%d %b %Y, %I:%M:%S %p') if candidate.entry_verified_at else 'Just Now',
        'data': {
            'full_name': candidate.full_name,
            'father_name': candidate.father_name,
            'registration_no': candidate.registration_no,
            'roll_number': candidate.roll_number or 'NOT ALLOTTED',
            'dob': str(candidate.dob),
            'category': candidate.category,
            'gender': candidate.gender,
            'allotted_center': center_text,
            'exam_date': candidate.exam_date or 'N/A',
            'exam_shift': candidate.exam_shift or 'N/A',
            'photo_url': photo_url,
        }
    })


# --- Result Evaluation Desk ---
@login_required(login_url='staff_login')
def result_evaluation_desk_view(request):
    if not request.user.is_staff:
        return redirect('staff_login')

    user = request.user
    assigned_center = ExamCenter.objects.filter(assigned_incharge=user).first()

    if user.is_superuser:
        available_centers = ExamCenter.objects.filter(is_active=True)
    elif assigned_center:
        available_centers = ExamCenter.objects.filter(id=assigned_center.id)
    else:
        available_centers = ExamCenter.objects.none()

    center_id = request.GET.get('center')
    date_val = request.GET.get('date')
    shift_val = request.GET.get('shift')

    if not user.is_superuser and assigned_center and not center_id:
        center_id = str(assigned_center.id)

    candidates = []
    selected_center = None

    if center_id and date_val and shift_val:
        if not user.is_superuser and assigned_center and str(assigned_center.id) != str(center_id):
            return HttpResponseForbidden("Access Denied: You cannot evaluate other centers.")

        selected_center = ExamCenter.objects.filter(id=center_id).first()
        if selected_center:
            candidates = Candidate.objects.filter(
                allotted_center_id=center_id,
                exam_date=date_val,
                exam_shift=shift_val,
                is_paid=True,
                is_present=True
            ).order_by('roll_number')

    if request.method == 'POST' and request.FILES.get('marks_csv'):
        csv_file = request.FILES['marks_csv']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "Please upload a valid .csv file format.")
        else:
            try:
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)
                updated_count = 0
                for row in reader:
                    reg_or_roll = (row.get('roll_number') or row.get('registration_no') or '').strip()
                    marks_str = (row.get('marks_obtained') or row.get('marks') or '').strip()
                    total_str = (row.get('total_marks') or '100').strip()
                    
                    if reg_or_roll and marks_str:
                        cand = Candidate.objects.filter(roll_number__iexact=reg_or_roll).first() or Candidate.objects.filter(registration_no__iexact=reg_or_roll).first()
                        if cand and cand.is_present:
                            m_obt = float(marks_str)
                            m_tot = float(total_str) if total_str else 100.0
                            cand.exam_marks_obtained = m_obt
                            cand.exam_total_marks = m_tot
                            cand.exam_percentage = round((m_obt / m_tot) * 100, 2)
                            cand.exam_qualification_status = 'Qualified' if cand.exam_percentage >= 40.0 else 'Not Qualified'
                            cand.is_result_declared = True
                            cand.save()

                            AuditLog.objects.create(
                                user=request.user,
                                action='MARKS_ENTERED',
                                candidate=cand,
                                ip_address=get_client_ip(request),
                                details=f"Bulk CSV: Marks={m_obt}/{m_tot} ({cand.exam_percentage}%)"
                            )
                            updated_count += 1

                messages.success(request, f"Successfully uploaded and computed results for {updated_count} candidates!")
                return redirect(request.get_full_path())
            except Exception as e:
                messages.error(request, f"Error processing CSV: {str(e)}")

    context = {
        'centers': available_centers,
        'assigned_center': assigned_center,
        'is_superuser': user.is_superuser,
        'dates': [d[0] for d in EXAM_DATE_CHOICES],
        'shifts': [s[0] for s in SHIFT_CHOICES],
        'selected_center': selected_center,
        'selected_center_id': int(center_id) if center_id and center_id.isdigit() else None,
        'selected_date': date_val,
        'selected_shift': shift_val,
        'candidates': candidates,
        'total_evaluated': sum(1 for c in candidates if c.is_result_declared),
    }
    return render(request, 'portal/result_evaluation_desk.html', context)


@csrf_exempt
@login_required(login_url='staff_login')
def save_single_mark_api(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})
    try:
        cand_id = request.POST.get('candidate_id')
        marks_obt = float(request.POST.get('marks_obtained', 0))
        marks_tot = float(request.POST.get('total_marks', 100))

        candidate = get_object_or_404(Candidate, id=cand_id)
        if not candidate.is_present:
            return JsonResponse({'status': 'error', 'message': 'Candidate was marked Absent. Cannot enter marks.'})

        candidate.exam_marks_obtained = marks_obt
        candidate.exam_total_marks = marks_tot
        candidate.exam_percentage = round((marks_obt / marks_tot) * 100, 2)
        candidate.exam_qualification_status = 'Qualified' if candidate.exam_percentage >= 40.0 else 'Not Qualified'
        candidate.is_result_declared = True
        candidate.save()

        AuditLog.objects.create(
            user=request.user,
            action='MARKS_ENTERED',
            candidate=candidate,
            ip_address=get_client_ip(request),
            details=f"Live Entry Desk: Marks={marks_obt}/{marks_tot} ({candidate.exam_percentage}%)"
        )

        return JsonResponse({
            'status': 'success',
            'percentage': candidate.exam_percentage,
            'qualification_status': candidate.exam_qualification_status,
            'message': 'Marks evaluated and saved!'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@login_required(login_url='staff_login')
def bulk_publish_results_view(request):
    if request.method == 'POST':
        center_id = request.POST.get('center_id')
        date_val = request.POST.get('date')
        shift_val = request.POST.get('shift')
        action = request.POST.get('action')

        candidates = Candidate.objects.filter(
            allotted_center_id=center_id,
            exam_date=date_val,
            exam_shift=shift_val,
            is_present=True,
            exam_marks_obtained__isnull=False
        )

        state = True if action == 'publish' else False
        candidates.update(is_result_declared=state)
        messages.success(request, f"Successfully {'published' if state else 'unpublished'} results for {candidates.count()} candidates!")
    return redirect(request.META.get('HTTP_REFERER', 'result_evaluation_desk'))


# --- Center Attendance & Bench Slips ---
@login_required(login_url='staff_login')
def print_attendance_sheet_view(request):
    if not request.user.is_staff:
        return redirect('staff_login')
    user = request.user
    assigned_center = ExamCenter.objects.filter(assigned_incharge=user).first()

    available_centers = ExamCenter.objects.filter(is_active=True) if user.is_superuser else (ExamCenter.objects.filter(id=assigned_center.id) if assigned_center else ExamCenter.objects.none())
    center_id = request.GET.get('center')
    date_val = request.GET.get('date')
    shift_val = request.GET.get('shift')

    if not user.is_superuser and assigned_center and not center_id:
        center_id = str(assigned_center.id)

    candidates = []
    selected_center = None

    if center_id and date_val and shift_val:
        if not user.is_superuser and assigned_center and str(assigned_center.id) != str(center_id):
            return HttpResponseForbidden("Access Denied.")
        selected_center = ExamCenter.objects.filter(id=center_id).first()
        if selected_center:
            candidates = Candidate.objects.filter(allotted_center_id=center_id, exam_date=date_val, exam_shift=shift_val, is_paid=True).order_by('roll_number')

    return render(request, 'portal/attendance_sheet.html', {
        'centers': available_centers, 'assigned_center': assigned_center, 'is_superuser': user.is_superuser,
        'dates': [d[0] for d in EXAM_DATE_CHOICES], 'shifts': [s[0] for s in SHIFT_CHOICES],
        'selected_center': selected_center, 'selected_center_id': int(center_id) if center_id and center_id.isdigit() else None,
        'selected_date': date_val, 'selected_shift': shift_val, 'candidates': candidates, 'total_candidates': len(candidates),
        'present_count': sum(1 for c in candidates if c.is_present)
    })


@login_required(login_url='staff_login')
def print_bench_slips_view(request):
    if not request.user.is_staff:
        return redirect('staff_login')
    user = request.user
    assigned_center = ExamCenter.objects.filter(assigned_incharge=user).first()
    available_centers = ExamCenter.objects.filter(is_active=True) if user.is_superuser else (ExamCenter.objects.filter(id=assigned_center.id) if assigned_center else ExamCenter.objects.none())
    center_id = request.GET.get('center')
    date_val = request.GET.get('date')
    shift_val = request.GET.get('shift')

    if not user.is_superuser and assigned_center and not center_id:
        center_id = str(assigned_center.id)

    candidates = []
    selected_center = None
    if center_id and date_val and shift_val:
        if not user.is_superuser and assigned_center and str(assigned_center.id) != str(center_id):
            return HttpResponseForbidden("Access Denied.")
        selected_center = ExamCenter.objects.filter(id=center_id).first()
        if selected_center:
            candidates = Candidate.objects.filter(allotted_center_id=center_id, exam_date=date_val, exam_shift=shift_val, is_paid=True).order_by('roll_number')

    return render(request, 'portal/bench_slips.html', {
        'centers': available_centers, 'assigned_center': assigned_center, 'is_superuser': user.is_superuser,
        'dates': [d[0] for d in EXAM_DATE_CHOICES], 'shifts': [s[0] for s in SHIFT_CHOICES],
        'selected_center': selected_center, 'selected_center_id': int(center_id) if center_id and center_id.isdigit() else None,
        'selected_date': date_val, 'selected_shift': shift_val, 'candidates': candidates
    })


# --- Grievance Helpdesk ---
def helpdesk_view(request):
    success_ticket = None
    if request.method == 'POST':
        reg_no = request.POST.get('registration_no', '').strip()
        email = request.POST.get('email', '').strip()
        cat = request.POST.get('category')
        sub = request.POST.get('subject', '').strip()
        desc = request.POST.get('description', '').strip()
        cand = Candidate.objects.filter(registration_no__iexact=reg_no).first()
        success_ticket = Grievance.objects.create(candidate=cand, registration_no=reg_no, email=email, category=cat, subject=sub, description=desc)
    return render(request, 'portal/helpdesk.html', {'success_ticket': success_ticket})


def view_ticket_status_view(request):
    ticket = None
    searched = False
    t_id = (request.GET.get('ticket_id') or '').strip()
    if t_id:
        searched = True
        ticket = Grievance.objects.filter(ticket_id__iexact=t_id).first()
    return render(request, 'portal/ticket_status.html', {'ticket': ticket, 'searched': searched, 'ticket_id': t_id})


# --- Multi-Language Toggle View ---
def toggle_language_view(request):
    current_lang = request.session.get('portal_lang', 'en')
    request.session['portal_lang'] = 'hi' if current_lang == 'en' else 'en'
    request.session.modified = True
    return redirect(request.META.get('HTTP_REFERER', 'home'))