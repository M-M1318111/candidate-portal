import base64
import io
import os
import random
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import qrcode
import razorpay
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import EmailMessage, get_connection
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from .forms import CandidateForm
from .models import Candidate, ExamCenter, Grievance

# --- Razorpay Client Setup ---
try:
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
except Exception:
    client = None


# --- Utility Functions ---
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
    """File ko direct base64 string me convert karta hai taaki slip/admit card me 100% load ho"""
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


def send_admin_registration_email(candidate):
    """Naye registration par admin ko alert email bhejta hai"""
    subject = f"🚨 New Candidate Registration: {candidate.registration_no}"
    
    body = f"""Hello Admin,

A new candidate has successfully registered on the portal:

• Registration No : {candidate.registration_no}
• Candidate Name  : {candidate.full_name}
• Father's Name   : {candidate.father_name}
• Category        : {candidate.category}
• Mobile Number   : +91-{candidate.phone}
• Email Address   : {candidate.email}
• Center Choice 1 : {candidate.center_choice_1}
• Applied Date    : {candidate.created_at.strftime('%d %b %Y, %I:%M %p') if candidate.created_at else 'Just Now'}

Log in to the Admin Console to verify documents:
http://127.0.0.1:8000/admin/portal/candidate/

— Central Examination Authority System
"""
    try:
        connection = get_connection()
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.ADMIN_NOTIFICATION_EMAIL],
            connection=connection
        )
        email.send(fail_silently=True)
    except Exception as e:
        print(f"Admin Email Alert Error: {e}")


# --- Home & Registration ---
def home_view(request):
    return render(request, 'portal/home.html')


def register_view(request):
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES)
        if form.is_valid():
            candidate_obj = form.save()
            
            # --- Send Instant Admin Alert Email ---
            send_admin_registration_email(candidate_obj)
            
            request.session['candidate_id'] = candidate_obj.id
            return redirect('preview', reg_no=candidate_obj.registration_no)
    else:
        form = CandidateForm()
    return render(request, 'portal/register.html', {'form': form})


def edit_candidate_view(request, reg_no):
    candidate_obj = get_object_or_404(Candidate, registration_no=reg_no)

    if candidate_obj.is_paid:
        messages.warning(request, "Application fee has already been paid. Details cannot be modified.")
        return redirect('preview', reg_no=candidate_obj.registration_no)

    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES, instance=candidate_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Application details updated successfully!")
            return redirect('preview', reg_no=candidate_obj.registration_no)
    else:
        form = CandidateForm(instance=candidate_obj)

    return render(request, 'portal/edit_candidate.html', {'form': form, 'candidate': candidate_obj})


# --- Preview & Payment Gateway (Razorpay) ---
def preview_view(request, reg_no):
    candidate_obj = get_object_or_404(Candidate, registration_no=reg_no)

    fee_structure = {
        'General': 1000,
        'OBC': 750,
        'EWS': 750,
        'SC': 500,
        'ST': 500,
    }
    exam_fee = getattr(candidate_obj, 'fee_amount', None) or fee_structure.get(candidate_obj.category, 1000)
    amount_in_paise = int(exam_fee * 100)

    order_id = getattr(candidate_obj, 'razorpay_order_id', None) or "ORDER_PENDING"
    is_placeholder = getattr(settings, 'RAZORPAY_KEY_ID', '').startswith('rzp_test_placeholder')

    # Razorpay Order Create
    if client and not candidate_obj.is_paid and not is_placeholder:
        try:
            if not getattr(candidate_obj, 'razorpay_order_id', None):
                payment_order = client.order.create({
                    'amount': amount_in_paise,
                    'currency': 'INR',
                    'payment_capture': '1'
                })
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
        order_id = request.POST.get('razorpay_order_id', getattr(candidate_obj, 'razorpay_order_id', ''))
        signature = request.POST.get('razorpay_signature', '')

        is_placeholder = getattr(settings, 'RAZORPAY_KEY_ID', '').startswith('rzp_test_placeholder')

        if not is_placeholder and client and signature:
            try:
                client.utility.verify_payment_signature({
                    'razorpay_order_id': order_id,
                    'razorpay_payment_id': payment_id,
                    'razorpay_signature': signature
                })
            except Exception:
                return HttpResponseBadRequest("Payment Signature Verification Failed!")

        # Payment Successful Update
        candidate_obj.is_paid = True
        candidate_obj.razorpay_payment_id = payment_id
        if not candidate_obj.roll_number:
            candidate_obj.roll_number = f"CBT-{random.randint(100000, 999999)}"
        candidate_obj.save()

        messages.success(request, f"Payment Successful! Txn ID: {payment_id}")
        return render(request, 'portal/preview.html', {
            'candidate': candidate_obj,
            'exam_fee': 0,
            'payment_success': True
        })

    # Direct GET access fallback
    if candidate_obj.is_paid:
        return redirect('preview', reg_no=reg_no)

    return redirect('preview', reg_no=reg_no)


# --- REAL EMAIL & REAL MOBILE SMS OTP ---
@csrf_exempt
def send_otp_view(request):
    if request.method == 'POST':
        otp_type = request.POST.get('type')
        target_value = request.POST.get('value', '').strip()

        if not target_value:
            return JsonResponse({'status': 'error', 'message': f'Please enter a valid {otp_type}.'})

        otp = generate_otp()

        # 1. Real Email OTP
        if otp_type == 'email':
            request.session['email_otp'] = otp
            request.session['email_otp_target'] = target_value
            # settings.py ya .env se values uthayega
            SENDER_EMAIL = settings.MAILERS["default"]["mayanksingh9889659765@gmail.com"]
            APP_PASSWORD = settings.MAILERS["default"]["apualbvhfuzrquzk"]


            try:
                msg = MIMEMultipart()
                msg['From'] = f"Central Examination Portal <{SENDER_EMAIL}>"
                msg['To'] = target_value
                msg['Subject'] = "Verification OTP - Candidate Registration"

                body = (
                    f"Hello,\n\n"
                    f"Your One-Time Password (OTP) for Candidate Registration is: {otp}\n\n"
                    f"This OTP is valid for 10 minutes. Please do not share it with anyone."
                )
                msg.attach(MIMEText(body, 'plain'))

                server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10)
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.sendmail(SENDER_EMAIL, target_value, msg.as_string())
                server.quit()

                return JsonResponse({'status': 'success', 'message': f'Real OTP sent successfully to {target_value}!'})
            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'Failed to send email: {str(e)}'})

        # 2. Real Mobile SMS OTP
        elif otp_type == 'phone':
            request.session['phone_otp'] = otp
            request.session['phone_otp_target'] = target_value
            FAST2SMS_API_KEY = os.getenv('kIMPCKaYwg0sDrFQGmfyZchUNxbe92RioJzjW7dOvLp3uq8SAEfYLTtwk1DZIOvJVQprUGzy2e9CB7W8Y')
            sms_url = "https://www.fast2sms.com/dev/bulkV2"
            
            payload = {
                "message": f"Your Candidate Registration OTP is {otp}. Valid for 10 minutes.",
                "language": "english",
                "route": "q",
                "numbers": target_value,
            }
            headers = {
                'authorization': FAST2SMS_API_KEY,
                'Content-Type': "application/x-www-form-urlencoded"
            }

            try:
                response = requests.post(sms_url, data=payload, headers=headers, timeout=8)
                res_data = response.json()

                if res_data.get('return'):
                    return JsonResponse({
                        'status': 'success',
                        'message': f'Real SMS OTP sent successfully to +91-{target_value}!'
                    })
                else:
                    err_msg = res_data.get('message', 'Failed to send SMS.')
                    return JsonResponse({'status': 'error', 'message': f'SMS Gateway Error: {err_msg}'})

            except Exception as e:
                return JsonResponse({'status': 'error', 'message': f'SMS Gateway Connection Error: {str(e)}'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})


@csrf_exempt
def verify_otp_view(request):
    if request.method == 'POST':
        otp_type = request.POST.get('type')
        user_otp = request.POST.get('otp', '').strip()
        target_value = request.POST.get('value', '').strip()

        saved_otp = request.session.get(f'{otp_type}_otp')
        saved_target = request.session.get(f'{otp_type}_otp_target')

        if saved_otp and str(saved_otp) == user_otp and saved_target == target_value:
            request.session[f'{otp_type}_verified'] = True
            return JsonResponse({'status': 'success', 'message': f'{otp_type.capitalize()} verified successfully!'})

        return JsonResponse({'status': 'error', 'message': 'Invalid OTP. Please enter the correct code.'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request.'})


# --- PDF Generation (Slip & Admit Card) ---
def download_pdf_view(request, reg_no):
    candidate = get_object_or_404(Candidate, registration_no=reg_no)
    qr_data = f"CEA-2026 | Reg: {candidate.registration_no} | Name: {candidate.full_name} | Fee: PAID"
    
    context = {
        'candidate': candidate,
        'qr_code_base64': generate_qr_base64(qr_data),
        'photo_base64': file_to_base64(candidate.photo),
        'signature_base64': file_to_base64(candidate.signature),
    }
    return render(request, 'portal/pdf_template.html', context)


def download_admit_card_view(request, reg_no):
    candidate = get_object_or_404(Candidate, registration_no=reg_no)
    qr_data = f"ADMIT-CARD-2026 | Roll: {candidate.roll_number} | Reg: {candidate.registration_no} | Center: {candidate.center_choice_1}"
    
    context = {
        'candidate': candidate,
        'qr_code_base64': generate_qr_base64(qr_data),
        'photo_base64': file_to_base64(candidate.photo),
        'signature_base64': file_to_base64(candidate.signature),
    }
    return render(request, 'portal/admit_card_template.html', context)


# --- Candidate Login & Dashboard ---
def track_status_view(request):
    candidate_obj = None
    searched = False
    query = (request.POST.get('query') or request.GET.get('query') or request.POST.get('reg_no') or '').strip()

    if query:
        searched = True
        candidate_obj = (
            Candidate.objects.filter(registration_no__iexact=query).first()
            or Candidate.objects.filter(roll_number__iexact=query).first()
            or Candidate.objects.filter(email__iexact=query).first()
            or Candidate.objects.filter(phone__iexact=query).first()
        )

    return render(request, 'portal/track.html', {'candidate': candidate_obj, 'searched': searched, 'query': query})


def candidate_login_view(request):
    error_msg = None
    if request.method == 'POST':
        reg_no = request.POST.get('reg_no', '').strip()
        dob_str = request.POST.get('dob', '').strip()

        if reg_no and dob_str:
            candidate_obj = Candidate.objects.filter(registration_no__iexact=reg_no).first()
            if candidate_obj and str(candidate_obj.dob) == dob_str:
                request.session['candidate_id'] = candidate_obj.id
                return redirect('candidate_dashboard')
            error_msg = "Invalid Registration Number or Date of Birth."
        else:
            error_msg = "Please enter both credentials."

    return render(request, 'portal/candidate_login.html', {'error_msg': error_msg})


def candidate_dashboard_view(request):
    candidate_id = request.session.get('candidate_id')
    if not candidate_id:
        messages.warning(request, "Please login first to view your dashboard.")
        return redirect('candidate_login')

    candidate_obj = get_object_or_404(Candidate, id=candidate_id)
    return render(request, 'portal/candidate_dashboard.html', {'candidate': candidate_obj})


def candidate_logout_view(request):
    request.session.flush()
    messages.info(request, "You have been logged out successfully.")
    return redirect('candidate_login')


# --- Grievance & Helpdesk ---
def helpdesk_view(request):
    success_ticket = None
    if request.method == 'POST':
        reg_no = request.POST.get('registration_no', '').strip()
        email = request.POST.get('email', '').strip()
        category = request.POST.get('category')
        subject = request.POST.get('subject', '').strip()
        description = request.POST.get('description', '').strip()

        candidate_obj = Candidate.objects.filter(registration_no__iexact=reg_no).first()
        ticket = Grievance.objects.create(
            candidate=candidate_obj,
            registration_no=reg_no,
            email=email,
            category=category,
            subject=subject,
            description=description,
        )
        success_ticket = ticket

    return render(request, 'portal/helpdesk.html', {'success_ticket': success_ticket})


def view_ticket_status_view(request):
    ticket = None
    searched = False
    ticket_id = (request.GET.get('ticket_id') or request.POST.get('ticket_id') or '').strip()

    if ticket_id:
        searched = True
        ticket = Grievance.objects.filter(ticket_id__iexact=ticket_id).first()

    return render(request, 'portal/ticket_status.html', {'ticket': ticket, 'searched': searched, 'ticket_id': ticket_id})


# --- Custom Admin Executive Dashboard ---
@staff_member_required
def executive_admin_dashboard_view(request):
    candidates = Candidate.objects.all().order_by('-created_at')
    total_count = candidates.count()
    paid_count = candidates.filter(is_paid=True).count()
    unpaid_count = total_count - paid_count
    total_tickets = Grievance.objects.count()

    context = {
        'candidates': candidates,
        'total_count': total_count,
        'paid_count': paid_count,
        'unpaid_count': unpaid_count,
        'total_tickets': total_tickets,
    }
    return render(request, 'portal/admin_dashboard.html', context)