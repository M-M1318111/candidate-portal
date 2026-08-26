import csv
import io
import os
import random
import requests
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin, GroupAdmin as BaseGroupAdmin
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import models, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

try:
    from unfold.admin import ModelAdmin
except ImportError:
    from django.contrib.admin import ModelAdmin

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

admin.site.site_header = "Executive Examination Authority Console"
admin.site.site_title = "Admin Portal 2026"
admin.site.index_title = "Candidate Management & Verification Center"


def attach_file_from_source(file_source, subfolder="imports"):
    if not file_source or not str(file_source).strip():
        return None
    file_source = str(file_source).strip()

    if file_source.startswith("http://") or file_source.startswith("https://"):
        try:
            resp = requests.get(file_source, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                parsed = urlparse(file_source)
                filename = os.path.basename(parsed.path) or f"file_{random.randint(1000, 9999)}.jpg"
                return ContentFile(resp.content, name=filename)
        except Exception:
            return None
    elif os.path.exists(file_source):
        try:
            with open(file_source, "rb") as f:
                filename = os.path.basename(file_source)
                return ContentFile(f.read(), name=filename)
        except Exception:
            return None
    return None


if admin.site.is_registered(User):
    admin.site.unregister(User)

if admin.site.is_registered(Group):
    admin.site.unregister(Group)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = (
        'username',
        'email',
        'full_name_display',
        'role_badge',
        'active_status_badge',
        'edit_action_btn',
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)

    def full_name_display(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name if name else "-"
    full_name_display.short_description = "Full Name"

    def role_badge(self, obj):
        if obj.is_superuser:
            return mark_safe('<span style="background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">👑 MASTER ADMIN</span>')
        elif obj.is_staff:
            return mark_safe('<span style="background: #dcfce7; color: #15803d; border: 1px solid #86efac; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">🛡️ CENTER STAFF</span>')
        return mark_safe('<span style="background: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1; padding: 2px 8px; border-radius: 6px; font-size: 11px;">Candidate</span>')
    role_badge.short_description = "Role"

    def active_status_badge(self, obj):
        if obj.is_active:
            return mark_safe('<span style="color: #16a34a; font-weight: bold;">Active</span>')
        return mark_safe('<span style="color: #dc2626; font-weight: bold;">Inactive</span>')
    active_status_badge.short_description = "Active"

    def edit_action_btn(self, obj):
        change_url = reverse('admin:auth_user_change', args=[obj.id])
        return format_html(
            '<a href="{}" style="background: #2563eb; color: #ffffff !important; padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: bold; text-decoration: none;">✏️ Edit</a>',
            change_url
        )
    edit_action_btn.short_description = "Action"


@admin.register(Group)
class CustomGroupAdmin(BaseGroupAdmin, ModelAdmin):
    list_display = ('name',)


@admin.register(PortalSetting)
class PortalSettingAdmin(ModelAdmin):
    list_display = ('portal_title_display', 'is_admit_card_active', 'is_result_published')

    def portal_title_display(self, obj):
        return getattr(obj, 'board_name', None) or getattr(obj, 'site_name', 'Examination Authority Portal')
    portal_title_display.short_description = "Portal Title"

    def has_add_permission(self, request):
        return not PortalSetting.objects.exists()


class PresentCandidateResult(Candidate):
    class Meta:
        proxy = True
        verbose_name = "🎯 Result Entry (Present Candidates Only)"
        verbose_name_plural = "🎯 Result Entry (Present Candidates Only)"


@admin.register(PresentCandidateResult)
class PresentCandidateResultAdmin(ModelAdmin):
    list_display = (
        'student_photo',
        'roll_number',
        'full_name',
        'allotted_center',
        'exam_marks_obtained',
        'exam_total_marks',
        'exam_percentage',
        'exam_qualification_status',
        'is_result_declared',
    )
    list_editable = ('exam_marks_obtained', 'exam_total_marks', 'exam_qualification_status', 'is_result_declared')
    search_fields = ('roll_number', 'registration_no', 'full_name')
    list_filter = ('exam_qualification_status', 'is_result_declared', 'allotted_center')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_present=True)

    def student_photo(self, obj):
        if getattr(obj, 'photo', None) and hasattr(obj.photo, 'url'):
            return format_html(
                '<img src="{}" style="width: 36px; height: 42px; object-fit: cover; border-radius: 4px; border: 1px solid #2563eb;" />',
                obj.photo.url
            )
        return mark_safe('<span style="color: #94a3b8; font-size: 11px;">No Pic</span>')
    student_photo.short_description = "Photo"

    def save_model(self, request, obj, form, change):
        if obj.exam_marks_obtained is not None and obj.exam_total_marks:
            try:
                obt = float(obj.exam_marks_obtained)
                tot = float(obj.exam_total_marks)
                obj.exam_percentage = round((obt / tot) * 100, 2)
                obj.exam_qualification_status = 'QUALIFIED' if obj.exam_percentage >= 40.0 else 'NOT_QUALIFIED'
            except (ValueError, ZeroDivisionError):
                pass
        super().save_model(request, obj, form, change)

    actions = ['declare_result_and_notify_action']

    @admin.action(description="📢 Declare Result & Send Scorecard Alerts")
    def declare_result_and_notify_action(self, request, queryset):
        settings_obj = PortalSetting.objects.first()
        if settings_obj:
            settings_obj.is_result_published = True
            if hasattr(settings_obj, 'result_published_date'):
                settings_obj.result_published_date = timezone.now()
            settings_obj.save()

        count = 0
        current_host = request.get_host()
        protocol = 'https' if request.is_secure() else 'http'
        login_url = f"{protocol}://{current_host}/candidate/login/"

        for cand in queryset:
            cand.is_result_declared = True
            cand.save()
            count += 1

            AuditLog.objects.create(
                user=request.user,
                action='RESULT_DECLARED',
                candidate=cand,
                details=f"Result declared. Score: {cand.exam_marks_obtained}/{cand.exam_total_marks} ({cand.exam_percentage}%)"
            )

            if cand.email:
                subject = f"📢 Examination Result Declared - Roll No: {cand.roll_number}"
                body = f"""Dear {cand.full_name},

Your official result for Central Examination Authority 2026 has been published!

• Roll Number : {cand.roll_number}
• Marks Scored: {cand.exam_marks_obtained} / {cand.exam_total_marks} ({cand.exam_percentage}%)
• Status      : {cand.exam_qualification_status}

Login to access your scorecard:
{login_url}
"""
                try:
                    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [cand.email], fail_silently=True)
                    NotificationLog.objects.create(
                        recipient=cand.email,
                        channel='EMAIL',
                        subject=subject,
                        message_body=body,
                        status='SENT'
                    )
                except Exception:
                    NotificationLog.objects.create(
                        recipient=cand.email,
                        channel='EMAIL',
                        subject=subject,
                        message_body=body,
                        status='FAILED'
                    )

        self.message_user(request, f"✅ Result declared for {count} candidate(s)!", level='success')


if admin.site.is_registered(Candidate):
    admin.site.unregister(Candidate)


@admin.register(Candidate)
class CandidateAdmin(ModelAdmin):
    change_list_template = "admin/candidate_changelist.html"

    list_display = (
        'student_photo',
        'registration_no',
        'student_profile',
        'contact_details',
        'category_badge',
        'allotted_center',
        'exam_date',
        'exam_shift',
        'payment_badge',
        'admit_release_badge',
        'attendance_badge',
        'quick_downloads',
    )
    
    list_editable = ('allotted_center', 'exam_date', 'exam_shift')
    list_display_links = ('registration_no', 'student_profile')

    search_fields = (
        'registration_no',
        'roll_number',
        'full_name',
        'father_name',
        'email',
        'phone',
        'razorpay_payment_id',
    )
    list_filter = (
        'is_present',
        'is_paid',
        'is_admit_card_released',
        'is_result_declared',
        'allotted_center',
        'exam_date',
        'exam_shift',
        'category',
        'created_at',
    )
    ordering = ('-created_at',)
    list_per_page = 20

    readonly_fields = (
        'registration_no',
        'percentage_view',
        'entry_verified_at',
        'large_photo',
        'large_signature',
        'id_proof_link',
        'created_at',
    )

    fieldsets = (
        ('Application & Attendance Status', {
            'fields': (
                ('registration_no', 'roll_number'),
                ('is_paid', 'fee_amount'),
                ('is_present', 'entry_verified_at'),
                ('razorpay_order_id', 'razorpay_payment_id'),
                'created_at',
            ),
        }),
        ('Admin Allotment & Scheduling Engine', {
            'fields': (
                ('center_choice_1', 'center_choice_2', 'center_choice_3'),
                ('allotted_center', 'is_admit_card_released'),
                ('exam_date', 'exam_shift'),
            ),
        }),
        ('Exam Evaluation & Result', {
            'fields': (
                ('exam_marks_obtained', 'exam_total_marks', 'exam_percentage'),
                ('exam_qualification_status', 'is_result_declared'),
            ),
        }),
        ('Personal Details', {
            'fields': (
                ('full_name', 'dob'),
                ('father_name', 'mother_name'),
                ('gender', 'category', 'nationality'),
                ('aadhaar_number',),
            ),
        }),
        ('Contact Information', {
            'fields': (
                ('email', 'phone'),
                'address',
            ),
        }),
        ('Academic Details', {
            'fields': (
                ('qualification_class', 'passing_year'),
                ('total_marks', 'obtained_marks', 'percentage_view'),
            ),
        }),
        ('Uploaded Proofs & Documents', {
            'fields': (
                ('photo', 'large_photo'),
                ('signature', 'large_signature'),
                ('aadhaar_doc', 'id_proof_link'),
            ),
        }),
    )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        total_reg = Candidate.objects.count()
        paid_reg = Candidate.objects.filter(is_paid=True).count()
        allotted_count = Candidate.objects.filter(allotted_center__isnull=False).count()
        released_count = Candidate.objects.filter(is_admit_card_released=True).count()

        extra_context['summary_metrics'] = {
            'total_reg': total_reg,
            'paid_reg': paid_reg,
            'allotted_count': allotted_count,
            'released_count': released_count,
        }

        extra_context['top_rankers'] = Candidate.objects.filter(
            is_result_declared=True,
            exam_percentage__isnull=False
        ).order_by('-exam_percentage', '-exam_marks_obtained')[:5]

        schedule_data = (
            Candidate.objects.filter(allotted_center__isnull=False)
            .values('allotted_center__center_name', 'allotted_center__city', 'exam_date', 'exam_shift')
            .annotate(
                total_candidates=Count('id'),
                released_admit_cards=Count('id', filter=Q(is_admit_card_released=True))
            )
            .order_by('allotted_center__center_name', 'exam_date', 'exam_shift')
        )
        extra_context['schedule_summary'] = schedule_data

        return super().changelist_view(request, extra_context=extra_context)

    # --- CSV Hub URL Routing (All 7 Modules) ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-sheet/', self.admin_site.admin_view(self.import_master_sheet_view), name='candidate_import_sheet'),
            path('download-sample-csv/', self.admin_site.admin_view(self.download_candidates_sample_view), name='candidate_sample_csv'),
            path('download-centers-sample/', self.admin_site.admin_view(self.download_centers_sample_view), name='centers_sample_csv'),
            path('download-keys-sample/', self.admin_site.admin_view(self.download_keys_sample_view), name='keys_sample_csv'),
            path('download-objections-sample/', self.admin_site.admin_view(self.download_objections_sample_view), name='objections_sample_csv'),
            path('download-grievances-sample/', self.admin_site.admin_view(self.download_grievances_sample_view), name='grievances_sample_csv'),
            path('download-marks-sample/', self.admin_site.admin_view(self.download_marks_sample_view), name='marks_sample_csv'),
            path('download-settings-sample/', self.admin_site.admin_view(self.download_settings_sample_view), name='settings_sample_csv'),
        ]
        return custom_urls + urls

    def download_candidates_sample_view(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="1_candidates_master_template.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'full_name', 'father_name', 'mother_name', 'dob', 'gender', 'category',
            'email', 'phone', 'address', 'qualification_class', 'passing_year',
            'total_marks', 'obtained_marks', 'is_paid', 'aadhaar_number',
            'photo_url', 'signature_url'
        ])
        writer.writerow([
            'Rahul Kumar', 'Suresh Kumar', 'Sunita Devi', '2000-05-15', 'M', 'UR',
            'rahul.sample@example.com', '9876543210', '123 Civil Lines, New Delhi', '12th Standard', '2024',
            '500', '425', '1', '[Aadhaar Redacted]',
            'https://picsum.photos/200/250',
            'https://dummyimage.com/200x80/000/fff.png&text=Signature'
        ])
        return response

    def download_centers_sample_view(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="2_exam_centers_template.csv"'
        writer = csv.writer(response)
        writer.writerow(['center_code', 'center_name', 'city', 'full_address', 'capacity_per_shift'])
        writer.writerow(['DEL-01', 'Delhi Public Assessment Hub', 'New Delhi', 'Plot 4, Sector 5, Dwarka, New Delhi', '250'])
        writer.writerow(['MUM-02', 'Mumbai CBT Examination Centre', 'Mumbai', 'Andheri East, Near Metro Station, Mumbai', '200'])
        return response

    def download_keys_sample_view(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="3_answer_keys_template.csv"'
        writer = csv.writer(response)
        writer.writerow(['question_number', 'exam_shift', 'question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option'])
        writer.writerow(['1', 'Shift 1', 'What is the capital of India?', 'Mumbai', 'New Delhi', 'Kolkata', 'Chennai', 'B'])
        writer.writerow(['2', 'Shift 1', 'Which protocol powers the web?', 'FTP', 'SMTP', 'HTTP', 'SSH', 'C'])
        return response

    def download_objections_sample_view(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="4_objections_challenges_template.csv"'
        writer = csv.writer(response)
        writer.writerow(['candidate_registration_no', 'question_number', 'exam_shift', 'claimed_option', 'justification'])
        writer.writerow(['CAND-12345678', '1', 'Shift 1', 'A', 'According to NCERT Chapter 4, option A is also accepted.'])
        return response

    def download_grievances_sample_view(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="5_grievance_tickets_template.csv"'
        writer = csv.writer(response)
        writer.writerow(['registration_no', 'email', 'category', 'subject', 'description'])
        writer.writerow(['CAND-12345678', 'candidate@gmail.com', 'PAYMENT', 'Fee Debited but not updated', 'Bank deducted money but receipt pending.'])
        return response

    def download_marks_sample_view(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="6_result_marks_template.csv"'
        writer = csv.writer(response)
        writer.writerow(['roll_number_or_registration_no', 'marks_obtained', 'total_marks'])
        writer.writerow(['CBT-2026-100234', '85.5', '100'])
        writer.writerow(['CBT-2026-100235', '42.0', '100'])
        return response

    def download_settings_sample_view(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="7_portal_settings_template.csv"'
        writer = csv.writer(response)
        writer.writerow(['board_name', 'exam_title', 'helpline_email', 'helpline_phone', 'announcement_ticker', 'is_result_published'])
        writer.writerow(['Central Examination Authority 2026', 'Combined Entrance Examination (CEE-2026)', 'support@examauthority.gov.in', '+91-1800-2026-99', 'Admit Cards live on candidate dashboard.', '1'])
        return response

    # Universal 7-in-1 Master CSV Importer Engine
    def import_master_sheet_view(self, request):
        if request.method == "POST" and request.FILES.get('candidate_file'):
            uploaded_file = request.FILES['candidate_file']
            import_type = request.POST.get('import_type', 'candidates')
            file_name = uploaded_file.name.lower()

            if not (file_name.endswith('.csv') or file_name.endswith('.txt')):
                messages.error(request, "❌ Kripya valid .csv format file upload karein.")
                return render(request, "admin/import_candidates.html")

            try:
                decoded_file = uploaded_file.read().decode('utf-8-sig').splitlines()
                reader = csv.DictReader(decoded_file)
                success_count = 0

                # 1. Candidates Master Import
                if import_type == 'candidates':
                    for idx, row in enumerate(reader, start=2):
                        full_name = row.get('full_name', '').strip()
                        email = row.get('email', '').strip()
                        phone = row.get('phone', '').strip()
                        dob_str = row.get('dob', '').strip()

                        if not full_name or not email or not phone or not dob_str:
                            continue

                        tot = float(row.get('total_marks') or 500)
                        obt = float(row.get('obtained_marks') or 0)
                        is_paid_val = str(row.get('is_paid', '1')).strip().lower() in ['1', 'true', 'yes', 'paid']
                        clean_phone = ''.join(filter(str.isdigit, phone))[-10:]

                        candidate = Candidate(
                            full_name=full_name,
                            father_name=row.get('father_name', '—').strip(),
                            mother_name=row.get('mother_name', '—').strip(),
                            dob=dob_str,
                            gender=row.get('gender', 'M').strip()[:1].upper(),
                            category=row.get('category', 'UR').strip(),
                            email=email,
                            phone=clean_phone,
                            address=row.get('address', 'Not Provided').strip(),
                            qualification_class=row.get('qualification_class', '12th').strip(),
                            passing_year=int(row.get('passing_year') or 2024),
                            total_marks=tot,
                            obtained_marks=obt,
                            is_paid=is_paid_val,
                            aadhaar_number=row.get('aadhaar_number', '').strip() or None
                        )

                        photo_f = attach_file_from_source(row.get('photo_url') or row.get('photo'))
                        if photo_f:
                            candidate.photo = photo_f

                        sig_f = attach_file_from_source(row.get('signature_url') or row.get('signature'))
                        if sig_f:
                            candidate.signature = sig_f

                        candidate.save()
                        success_count += 1
                    messages.success(request, f"✅ Successfully added {success_count} Candidates!")

                # 2. Exam Centers Import
                elif import_type == 'centers':
                    for row in reader:
                        code = row.get('center_code', '').strip()
                        name = row.get('center_name', '').strip()
                        city = row.get('city', '').strip()
                        addr = row.get('full_address', '').strip() or city
                        cap = int(row.get('capacity_per_shift') or 100)

                        if code and name:
                            ExamCenter.objects.update_or_create(
                                center_code=code,
                                defaults={
                                    'center_name': name,
                                    'city': city,
                                    'full_address': addr,
                                    'capacity_per_shift': cap,
                                    'is_active': True,
                                }
                            )
                            success_count += 1
                    messages.success(request, f"✅ Successfully imported/updated {success_count} Exam Centers!")

                # 3. Answer Keys Import
                elif import_type == 'keys':
                    for row in reader:
                        q_num = row.get('question_number', '').strip()
                        shift = row.get('exam_shift', 'Shift 1').strip()
                        if q_num and q_num.isdigit():
                            AnswerKey.objects.update_or_create(
                                question_number=int(q_num),
                                exam_shift=shift,
                                defaults={
                                    'question_text': row.get('question_text', f"Question #{q_num}"),
                                    'option_a': row.get('option_a', 'Option A'),
                                    'option_b': row.get('option_b', 'Option B'),
                                    'option_c': row.get('option_c', 'Option C'),
                                    'option_d': row.get('option_d', 'Option D'),
                                    'correct_option': row.get('correct_option', 'A').strip().upper()[:1],
                                    'is_active': True,
                                }
                            )
                            success_count += 1
                    messages.success(request, f"✅ Successfully imported {success_count} Answer Key Questions!")

                # 4. Candidate Objections Import
                elif import_type == 'objections':
                    for row in reader:
                        reg_no = row.get('candidate_registration_no', '').strip()
                        q_num = row.get('question_number', '').strip()
                        shift = row.get('exam_shift', 'Shift 1').strip()
                        claimed = row.get('claimed_option', 'A').strip().upper()[:1]
                        justification = row.get('justification', 'Imported via CSV').strip()

                        cand = Candidate.objects.filter(registration_no__iexact=reg_no).first()
                        if cand and q_num.isdigit():
                            q_obj = AnswerKey.objects.filter(question_number=int(q_num), exam_shift=shift).first()
                            if q_obj:
                                QuestionObjection.objects.create(
                                    candidate=cand,
                                    question=q_obj,
                                    claimed_option=claimed,
                                    justification=justification,
                                    status='PENDING'
                                )
                                success_count += 1
                    messages.success(request, f"✅ Successfully logged {success_count} Candidate Objections!")

                # 5. Grievances Import
                elif import_type == 'grievances':
                    for row in reader:
                        reg_no = row.get('registration_no', '').strip()
                        email = row.get('email', '').strip()
                        cat = row.get('category', 'OTHER').strip()
                        sub = row.get('subject', 'Helpdesk Query').strip()
                        desc = row.get('description', 'Query raised').strip()

                        if reg_no and email:
                            cand = Candidate.objects.filter(registration_no__iexact=reg_no).first()
                            Grievance.objects.create(
                                candidate=cand,
                                registration_no=reg_no,
                                email=email,
                                category=cat,
                                subject=sub,
                                description=desc,
                                status='OPEN'
                            )
                            success_count += 1
                    messages.success(request, f"✅ Successfully logged {success_count} Grievance Tickets!")

                # 6. CBT Marks & Result Import
                elif import_type == 'marks':
                    for row in reader:
                        identifier = (row.get('roll_number_or_registration_no') or row.get('roll_number') or row.get('registration_no') or '').strip()
                        m_str = (row.get('marks_obtained') or row.get('marks') or '').strip()
                        tot_str = (row.get('total_marks') or '100').strip()

                        if identifier and m_str:
                            cand = Candidate.objects.filter(roll_number__iexact=identifier).first() or Candidate.objects.filter(registration_no__iexact=identifier).first()
                            if cand:
                                cand.exam_marks_obtained = float(m_str)
                                cand.exam_total_marks = float(tot_str) if tot_str else 100.0
                                cand.exam_percentage = round((cand.exam_marks_obtained / cand.exam_total_marks) * 100, 2)
                                cand.exam_qualification_status = 'QUALIFIED' if cand.exam_percentage >= 40.0 else 'NOT_QUALIFIED'
                                cand.is_result_declared = True
                                cand.save()
                                success_count += 1
                    messages.success(request, f"✅ Successfully evaluated and updated {success_count} Candidate Scores!")

                # 7. Global Settings Import
                elif import_type == 'settings':
                    for row in reader:
                        setting = PortalSetting.objects.first() or PortalSetting()
                        setting.board_name = row.get('board_name', setting.board_name)
                        setting.exam_title = row.get('exam_title', setting.exam_title)
                        setting.helpline_email = row.get('helpline_email', setting.helpline_email)
                        setting.helpline_phone = row.get('helpline_phone', setting.helpline_phone)
                        setting.announcement_ticker = row.get('announcement_ticker', setting.announcement_ticker)
                        pub = str(row.get('is_result_published', '0')).strip().lower() in ['1', 'true', 'yes']
                        setting.is_result_published = pub
                        setting.save()
                        success_count += 1
                        break
                    messages.success(request, f"✅ Global Portal Settings updated successfully!")

                return redirect('/admin/portal/candidate/')

            except Exception as e:
                messages.error(request, f"❌ CSV Processing Error: {str(e)}")

        return render(request, "admin/import_candidates.html")

    def student_photo(self, obj):
        if getattr(obj, 'photo', None) and hasattr(obj.photo, 'url'):
            return format_html(
                '<img src="{}" style="width: 44px; height: 50px; object-fit: cover; border-radius: 6px; border: 1.5px solid #2563eb;" />',
                obj.photo.url
            )
        return mark_safe('<span style="color: #94a3b8; font-size: 11px;">No Pic</span>')
    student_photo.short_description = "Photo"

    def student_profile(self, obj):
        roll = obj.roll_number or "Pending"
        father = getattr(obj, 'father_name', '-')
        return format_html(
            '<div style="line-height: 1.35;">'
            '<strong style="color: #0f172a; font-size: 13px;">{}</strong><br>'
            '<span style="color: #64748b; font-size: 11px;">Roll: <b style="color: #2563eb;">{}</b></span><br>'
            '<span style="color: #64748b; font-size: 11px;">Father: {}</span>'
            '</div>',
            obj.full_name,
            roll,
            father
        )
    student_profile.short_description = "Candidate Profile"

    def contact_details(self, obj):
        return format_html(
            '<div style="line-height: 1.35;">'
            '<span style="font-size: 12px; color: #1e293b;">{}</span><br>'
            '<span style="color: #0284c7; font-size: 11px; font-weight: 600;">+91-{}</span>'
            '</div>',
            obj.email,
            obj.phone
        )
    contact_details.short_description = "Contact Info"

    def category_badge(self, obj):
        colors = {
            'General': '#475569',
            'UR': '#475569',
            'OBC': '#0284c7',
            'EWS': '#0d9488',
            'SC': '#d97706',
            'ST': '#7c3aed',
        }
        bg = colors.get(obj.category, '#2563eb')
        return format_html(
            '<span style="background: {}; color: #fff; padding: 3px 9px; border-radius: 999px; font-size: 11px; font-weight: bold;">{}</span>',
            bg,
            obj.category
        )
    category_badge.short_description = "Category"

    def payment_badge(self, obj):
        if obj.is_paid:
            amt = getattr(obj, 'fee_amount', 500)
            return format_html(
                '<span style="background: #dcfce7; color: #15803d; border: 1px solid #86efac; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">✓ PAID (₹{})</span>',
                amt
            )
        return mark_safe(
            '<span style="background: #fef9c3; color: #a16207; border: 1px solid #fde047; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">⏳ PENDING</span>'
        )
    payment_badge.short_description = "Payment"

    def admit_release_badge(self, obj):
        if obj.is_admit_card_released:
            return mark_safe(
                '<span style="background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">📢 RELEASED</span>'
            )
        return mark_safe(
            '<span style="background: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: 500;">🔒 Locked</span>'
        )
    admit_release_badge.short_description = "Admit Status"

    def attendance_badge(self, obj):
        if obj.is_present:
            time_str = obj.entry_verified_at.strftime('%I:%M %p') if getattr(obj, 'entry_verified_at', None) else "Verified"
            return format_html(
                '<span style="background: #dcfce7; color: #166534; border: 1px solid #86efac; padding: 2px 7px; border-radius: 6px; font-size: 11px; font-weight: bold;">🟢 PRESENT<br><small style="color: #15803d;">{}</small></span>',
                time_str
            )
        return mark_safe('<span style="background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; padding: 2px 7px; border-radius: 6px; font-size: 11px; font-weight: bold;">🔴 ABSENT</span>')
    attendance_badge.short_description = "Attendance"

    def quick_downloads(self, obj):
        try:
            slip_url = reverse('download_slip', args=[obj.registration_no])
        except Exception:
            slip_url = reverse('download_pdf', args=[obj.registration_no])

        admit_url = reverse('download_admit_card', args=[obj.registration_no])

        admit_html = (
            format_html('<a href="{}" target="_blank" style="padding: 3px 8px; background: #059669; color: #fff; text-decoration: none; border-radius: 4px; font-size: 11px; font-weight: bold;">🎟️ Admit</a>', admit_url)
            if (obj.is_paid and obj.is_admit_card_released) else
            mark_safe('<span style="color: #94a3b8; font-size: 11px;">Locked</span>')
        )

        score_html = ""
        if obj.is_result_declared:
            score_url = reverse('download_scorecard', args=[obj.registration_no])
            score_html = format_html('<a href="{}" target="_blank" style="padding: 3px 8px; background: #4338ca; color: #fff; text-decoration: none; border-radius: 4px; font-size: 11px; font-weight: bold;">📊 Score</a>', score_url)

        return format_html(
            '<div style="display: flex; gap: 5px; align-items: center;">'
            '<a href="{}" target="_blank" style="padding: 3px 8px; background: #4f46e5; color: #fff; text-decoration: none; border-radius: 4px; font-size: 11px; font-weight: bold;">📄 Slip</a>'
            '{} {}'
            '</div>',
            slip_url,
            admit_html,
            score_html
        )
    quick_downloads.short_description = "Downloads"

    def large_photo(self, obj):
        if getattr(obj, 'photo', None) and hasattr(obj.photo, 'url'):
            return format_html('<img src="{}" style="max-height: 150px; max-width: 130px; border-radius: 8px; border: 1px solid #cbd5e1;" />', obj.photo.url)
        return "No Photo"
    large_photo.short_description = "Photo Preview"

    def large_signature(self, obj):
        if getattr(obj, 'signature', None) and hasattr(obj.signature, 'url'):
            return format_html('<img src="{}" style="max-height: 70px; max-width: 200px; border-radius: 6px; border: 1px solid #cbd5e1;" />', obj.signature.url)
        return "No Signature"
    large_signature.short_description = "Signature Preview"

    def id_proof_link(self, obj):
        doc = getattr(obj, 'aadhaar_doc', None) or getattr(obj, 'id_proof', None)
        if doc and hasattr(doc, 'url'):
            return format_html('<a href="{}" target="_blank" style="background: #2563eb; color: #fff; padding: 4px 10px; border-radius: 5px; text-decoration: none; font-size: 12px; font-weight: bold;">📄 Open ID Document &rarr;</a>', doc.url)
        return "No ID Document Uploaded"
    id_proof_link.short_description = "Identity Document"

    def percentage_view(self, obj):
        return f"{obj.percentage}%" if getattr(obj, 'percentage', None) else "-"
    percentage_view.short_description = "Percentage"

    actions = [
        'mark_as_paid_action',
        'open_csv_importer_hub_action',
        'batch_auto_allocate_engine',
        'mark_as_present_action',
        'mark_as_absent_action',
        'release_admit_card_and_notify_action',
        'export_as_csv',
        'export_final_merit_rankers_csv',
    ]

    @admin.action(description="📥 1-Click Open CSV / Excel Bulk Importer Hub")
    def open_csv_importer_hub_action(self, request, queryset):
        return HttpResponseRedirect(reverse('admin:candidate_import_sheet'))

    @admin.action(description="✓ Mark selected as PAID")
    def mark_as_paid_action(self, request, queryset):
        updated = queryset.update(is_paid=True)
        self.message_user(request, f"Successfully updated {updated} candidate(s) to Paid.")

    @admin.action(description="🟢 Mark selected as PRESENT (Manual Check-in)")
    def mark_as_present_action(self, request, queryset):
        updated = queryset.update(is_present=True, entry_verified_at=timezone.now())
        for c in queryset:
            AuditLog.objects.create(user=request.user, action='ATTENDANCE_CHECKIN', candidate=c, details="Manual present mark from admin")
        self.message_user(request, f"Successfully marked {updated} candidate(s) as Present.")

    @admin.action(description="🔴 Mark selected as ABSENT")
    def mark_as_absent_action(self, request, queryset):
        updated = queryset.update(is_present=False, entry_verified_at=None)
        self.message_user(request, f"Successfully marked {updated} candidate(s) as Absent.")

    @admin.action(description="⚡ 1-Click Smart Auto-Allot (Centers, Dates, Shifts & Roll Nos)")
    def batch_auto_allocate_engine(self, request, queryset):
        unallotted_candidates = queryset.filter(is_paid=True).order_by('created_at')
        if not unallotted_candidates.exists():
            self.message_user(request, "Selected list me koi aisa PAID candidate nahi mila jise allot karna ho.", level='warning')
            return

        active_centers = list(ExamCenter.objects.filter(is_active=True))
        if not active_centers:
            self.message_user(request, "Koi active Exam Center nahi mila. Pehle Exam Centers add karein.", level='error')
            return

        dates = [d[0] for d in EXAM_DATE_CHOICES]
        shifts = [s[0] for s in SHIFT_CHOICES]

        occupancy_query = (
            Candidate.objects.filter(allotted_center__isnull=False)
            .values('allotted_center_id', 'exam_date', 'exam_shift')
            .annotate(total=Count('id'))
        )
        occupancy = {}
        for row in occupancy_query:
            occupancy[(row['allotted_center_id'], row['exam_date'], row['exam_shift'])] = row['total']

        allocated_count = 0
        roll_prefix = "CBT-2026"

        with transaction.atomic():
            for cand in unallotted_candidates:
                allocated = False
                pref_centers = [
                    getattr(cand, 'center_choice_1', None),
                    getattr(cand, 'center_choice_2', None),
                    getattr(cand, 'center_choice_3', None)
                ]
                target_centers = [c for c in pref_centers if c and getattr(c, 'is_active', True)]

                for c in active_centers:
                    if c not in target_centers:
                        target_centers.append(c)

                for center in target_centers:
                    cap = getattr(center, 'capacity_per_shift', getattr(center, 'seating_capacity', 100))
                    for dt in dates:
                        for sh in shifts:
                            current_filled = occupancy.get((center.id, dt, sh), 0)
                            if current_filled < cap:
                                cand.allotted_center = center
                                cand.exam_date = dt
                                cand.exam_shift = sh
                                if not cand.roll_number:
                                    cand.roll_number = f"{roll_prefix}-{random.randint(100000, 999999)}"
                                cand.save()
                                occupancy[(center.id, dt, sh)] = current_filled + 1
                                allocated_count += 1
                                allocated = True
                                break
                        if allocated:
                            break
                    if allocated:
                        break

        self.message_user(request, f"✅ Batch Allocation Complete! Allotted to {allocated_count} candidate(s).", level='success')

    @admin.action(description="📢 Release Admit Card & Send Alerts (For Selected)")
    def release_admit_card_and_notify_action(self, request, queryset):
        paid_candidates = queryset.filter(is_paid=True)
        if not paid_candidates.exists():
            self.message_user(request, "Selected candidates me koi paid candidate nahi mila.", level='warning')
            return

        current_host = request.get_host()
        protocol = 'https' if request.is_secure() else 'http'
        login_url = f"{protocol}://{current_host}/candidate/login/"

        for cand in paid_candidates:
            if not cand.allotted_center:
                cand.allotted_center = getattr(cand, 'center_choice_1', None) or ExamCenter.objects.first()
            if not cand.roll_number:
                cand.roll_number = f"CBT-{random.randint(100000, 999999)}"
            cand.is_admit_card_released = True
            cand.save()

            AuditLog.objects.create(
                user=request.user,
                action='ADMIT_CARD_RELEASED',
                candidate=cand,
                details=f"Admit card released. Center: {cand.allotted_center.center_name}"
            )

            if cand.email:
                subject = f"🎟️ Admit Card Released - Roll No: {cand.roll_number}"
                center_title = cand.allotted_center.center_name if cand.allotted_center else getattr(cand, 'exam_center', 'Exam Center')
                body = f"""Dear {cand.full_name},

Your Admit Card for Central Examination Authority 2026 is officially released!

• Roll Number : {cand.roll_number}
• Allotted Center : {center_title}
• Exam Date : {cand.exam_date}
• Shift : {cand.exam_shift}

Login here to download:
{login_url}
"""
                try:
                    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [cand.email], fail_silently=True)
                    NotificationLog.objects.create(
                        recipient=cand.email,
                        channel='EMAIL',
                        subject=subject,
                        message_body=body,
                        status='SENT'
                    )
                except Exception:
                    NotificationLog.objects.create(
                        recipient=cand.email,
                        channel='EMAIL',
                        subject=subject,
                        message_body=body,
                        status='FAILED'
                    )

        self.message_user(request, f"Processed {paid_candidates.count()} candidate(s). Issued admit cards & dispatched alerts.", level='success')

    @admin.action(description="📥 Export Selected Candidates to Master CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="candidates_master.csv"'
        writer = csv.writer(response)
        writer.writerow(['Reg No', 'Roll No', 'Full Name', 'Father Name', 'DOB', 'Category', 'Email', 'Phone', 'Allotted Center', 'Exam Date', 'Shift', 'Paid', 'Present', 'Marks', 'Result Status'])

        for c in queryset:
            center_title = c.allotted_center.center_name if c.allotted_center else getattr(c, 'exam_center', '-')
            writer.writerow([
                c.registration_no,
                c.roll_number or "Pending",
                c.full_name,
                getattr(c, 'father_name', '-'),
                c.dob,
                c.category,
                c.email,
                c.phone,
                center_title,
                c.exam_date,
                c.exam_shift,
                "PAID" if c.is_paid else "PENDING",
                "PRESENT" if c.is_present else "ABSENT",
                getattr(c, 'exam_marks_obtained', None) or "-",
                getattr(c, 'exam_qualification_status', '-'),
            ])
        return response

    @admin.action(description="🏆 1-Click Export Final Merit & Rankers Sheet (CSV)")
    def export_final_merit_rankers_csv(self, request, queryset):
        evaluated = queryset.filter(is_result_declared=True, exam_marks_obtained__isnull=False).order_by('-exam_percentage', '-exam_marks_obtained')
        if not evaluated.exists():
            self.message_user(request, "Selected candidates me se kisi ka result declare nahi hua hai.", level='warning')
            return

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="official_cbt_merit_rankers_2026.csv"'
        writer = csv.writer(response)
        writer.writerow([
            'AIR Rank', 'Roll Number', 'Registration No', 'Candidate Name', 'Father Name',
            'Category', 'Category Rank', 'Shift', 'Marks Scored', 'Total Marks', 'Percentage', 'Status'
        ])

        for idx, c in enumerate(evaluated, start=1):
            c_marks = c.exam_marks_obtained or 0
            cat_rank = Candidate.objects.filter(
                category=c.category,
                is_result_declared=True,
                exam_marks_obtained__gt=c_marks
            ).count() + 1

            writer.writerow([
                f"#{idx}",
                c.roll_number or "—",
                c.registration_no,
                c.full_name,
                c.father_name,
                c.category,
                f"#{cat_rank}",
                c.exam_shift,
                c.exam_marks_obtained,
                c.exam_total_marks,
                f"{c.exam_percentage}%",
                c.exam_qualification_status
            ])
        return response


@admin.register(ExamCenter)
class ExamCenterAdmin(ModelAdmin):
    list_display = ('center_code', 'center_name', 'city', 'display_capacity', 'assigned_incharge', 'is_active')
    list_editable = ('is_active', 'assigned_incharge')
    list_filter = ('is_active', 'city')
    search_fields = ('center_code', 'center_name', 'city')
    ordering = ('center_code',)

    def display_capacity(self, obj):
        return getattr(obj, 'capacity_per_shift', getattr(obj, 'seating_capacity', 100))
    display_capacity.short_description = "Capacity / Shift"


@admin.register(Grievance)
class GrievanceAdmin(ModelAdmin):
    list_display = ('ticket_id', 'registration_no', 'email', 'category', 'status_badge', 'replied_by', 'created_at')
    list_filter = ('category', 'status', 'created_at')
    search_fields = ('ticket_id', 'registration_no', 'email', 'subject', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('ticket_id', 'candidate', 'registration_no', 'email', 'category', 'subject', 'description', 'created_at', 'replied_by', 'replied_at')

    def status_badge(self, obj):
        if obj.status == 'RESOLVED':
            return mark_safe('<span style="background: #dcfce7; color: #15803d; border: 1px solid #86efac; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">✓ RESOLVED</span>')
        elif obj.status == 'CLOSED':
            return mark_safe('<span style="background: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1; padding: 2px 8px; border-radius: 6px; font-size: 11px;">CLOSED</span>')
        return mark_safe('<span style="background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">⏳ OPEN</span>')
    status_badge.short_description = "Status"


@admin.register(AnswerKey)
class AnswerKeyAdmin(ModelAdmin):
    list_display = ('question_number', 'exam_shift', 'correct_option', 'is_revised', 'is_active', 'created_at')
    list_editable = ('correct_option', 'is_revised', 'is_active')
    list_filter = ('exam_shift', 'is_revised', 'is_active')
    search_fields = ('question_number', 'question_text')
    ordering = ('question_number',)


@admin.register(QuestionObjection)
class QuestionObjectionAdmin(ModelAdmin):
    list_display = ('candidate', 'question', 'claimed_option', 'status_badge', 'created_at')
    list_filter = ('status', 'question__exam_shift')
    search_fields = ('candidate__registration_no', 'candidate__full_name', 'justification')
    ordering = ('-created_at',)

    def status_badge(self, obj):
        if obj.status == 'ACCEPTED':
            return mark_safe('<span style="background: #dcfce7; color: #15803d; border: 1px solid #86efac; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">✓ REVISED / ACCEPTED</span>')
        elif obj.status == 'REJECTED':
            return mark_safe('<span style="background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">✕ REJECTED</span>')
        return mark_safe('<span style="background: #fef9c3; color: #a16207; border: 1px solid #fde047; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">⏳ UNDER REVIEW</span>')
    status_badge.short_description = "Status"


# --- Notification Log Admin Panel (Option 2 Integration) ---
@admin.register(NotificationLog)
class NotificationLogAdmin(ModelAdmin):
    list_display = ('sent_at', 'channel', 'recipient', 'subject', 'status_badge')
    list_filter = ('channel', 'status', 'sent_at')
    search_fields = ('recipient', 'subject', 'message_body')
    readonly_fields = ('recipient', 'channel', 'subject', 'message_body', 'status', 'sent_at')

    def status_badge(self, obj):
        if obj.status == 'SENT':
            return mark_safe('<span style="background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 6px; font-weight: bold;">✓ SENT</span>')
        return mark_safe('<span style="background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 6px; font-weight: bold;">✕ FAILED</span>')
    status_badge.short_description = "Status"

    def has_add_permission(self, request):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = ('timestamp', 'action_badge', 'user', 'candidate', 'ip_address')
    list_filter = ('action', 'timestamp', 'user')
    search_fields = ('candidate__registration_no', 'candidate__full_name', 'details', 'ip_address')
    readonly_fields = ('user', 'action', 'candidate', 'details', 'ip_address', 'timestamp')

    def action_badge(self, obj):
        colors = {
            'ATTENDANCE_CHECKIN': '#15803d',
            'MARKS_ENTERED': '#0284c7',
            'RESULT_DECLARED': '#9333ea',
            'ADMIT_CARD_RELEASED': '#d97706',
            'KEY_REVISED': '#dc2626',
            'HELPDESK_RESOLVED': '#0d9488',
        }
        col = colors.get(obj.action, '#475569')
        return format_html(
            '<span style="background: {}; color: #fff; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">{}</span>',
            col,
            obj.get_action_display()
        )
    action_badge.short_description = "Action Type"

    def has_add_permission(self, request):
        return False