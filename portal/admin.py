import csv
import random
from django.contrib import admin
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

try:
    from unfold.admin import ModelAdmin
except ImportError:
    from django.contrib.admin import ModelAdmin

from .models import Candidate, Grievance


# Admin Portal Titles
admin.site.site_header = "Executive Examination Authority Console"
admin.site.site_title = "Admin Portal 2026"
admin.site.index_title = "Candidate Management & Verification Center"


if admin.site.is_registered(Candidate):
    admin.site.unregister(Candidate)


@admin.register(Candidate)
class CandidateAdmin(ModelAdmin):
    # 1. Main Table Columns
    list_display = (
        'student_photo',
        'registration_no',
        'student_profile',
        'contact_details',
        'category_badge',
        'academic_info',
        'center_pref',
        'payment_badge',
        'quick_downloads',
    )

    # 2. Search and Filters
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
        'is_paid',
        'category',
        'gender',
        'created_at',
    )
    ordering = ('-created_at',)
    list_per_page = 20

    # 3. Readonly Detail Fields
    readonly_fields = (
        'registration_no',
        'percentage_view',
        'large_photo',
        'large_signature',
        'id_proof_link',
        'created_at',
    )

    # 4. Detail View Sections
    fieldsets = (
        ('Application Status', {
            'fields': (
                ('registration_no', 'roll_number'),
                ('is_paid', 'fee_amount'),
                ('razorpay_order_id', 'razorpay_payment_id'),
                'created_at',
            ),
        }),
        ('Personal Details', {
            'fields': (
                ('full_name', 'dob'),
                ('father_name', 'mother_name'),
                ('gender', 'category'),
                'aadhaar_number',
            ),
        }),
        ('Contact Information', {
            'fields': (
                ('email', 'phone'),
                'address',
            ),
        }),
        ('Academic & Center Preferences', {
            'fields': (
                ('qualification_class', 'passing_year'),
                ('total_marks', 'obtained_marks', 'percentage_view'),
                ('center_choice_1', 'center_choice_2', 'center_choice_3'),
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

    # --- Safe Column Renders ---

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

    def academic_info(self, obj):
        qual = getattr(obj, 'qualification_class', getattr(obj, 'qualification', 'N/A'))
        tot = getattr(obj, 'total_marks', getattr(obj, 'total_mark', 0))
        obt = getattr(obj, 'obtained_marks', getattr(obj, 'obtain_mark', 0))
        perc = getattr(obj, 'percentage', '0.00')
        return format_html(
            '<div style="font-size: 12px; line-height: 1.3;">'
            '<strong>{}</strong> ({})<br>'
            '<span style="color: #16a34a; font-weight: bold;">{}%</span> '
            '<span style="color: #64748b; font-size: 11px;">({}/{})</span>'
            '</div>',
            qual,
            getattr(obj, 'passing_year', '-'),
            perc,
            obt,
            tot
        )
    academic_info.short_description = "Academic"

    def center_pref(self, obj):
        center = getattr(obj, 'center_choice_1', getattr(obj, 'exam_center', 'Center 1'))
        return format_html('<span style="font-size: 11px; font-weight: 600; color: #334155;">{}</span>', center)
    center_pref.short_description = "Center Pref 1"

    def payment_badge(self, obj):
        if obj.is_paid:
            return format_html(
                '<span style="background: #dcfce7; color: #15803d; border: 1px solid #86efac; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">'
                '✓ PAID (₹{})</span>',
                getattr(obj, 'fee_amount', 0)
            )
        return mark_safe(
            '<span style="background: #fef9c3; color: #a16207; border: 1px solid #fde047; padding: 3px 8px; border-radius: 6px; font-size: 11px; font-weight: bold;">'
            '⏳ PENDING</span>'
        )
    payment_badge.short_description = "Payment Status"

    def quick_downloads(self, obj):
        slip_url = reverse('download_pdf', args=[obj.registration_no])
        admit_url = reverse('download_admit_card', args=[obj.registration_no])

        admit_html = (
            f'<a href="{admit_url}" target="_blank" style="padding: 3px 8px; background: #059669; color: #fff; text-decoration: none; border-radius: 4px; font-size: 11px; font-weight: bold;">🎟️ Admit</a>'
            if obj.is_paid else
            '<span style="color: #94a3b8; font-size: 11px;">Locked</span>'
        )

        return format_html(
            '<div style="display: flex; gap: 5px; align-items: center;">'
            '<a href="{}" target="_blank" style="padding: 3px 8px; background: #4f46e5; color: #fff; text-decoration: none; border-radius: 4px; font-size: 11px; font-weight: bold;">📄 Slip</a>'
            '{}'
            '</div>',
            slip_url,
            mark_safe(admit_html)
        )
    quick_downloads.short_description = "Downloads"

    # Detail View Previews
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
        if getattr(obj, 'aadhaar_doc', None) and hasattr(obj.aadhaar_doc, 'url'):
            return format_html('<a href="{}" target="_blank" style="background: #2563eb; color: #fff; padding: 4px 10px; border-radius: 5px; text-decoration: none; font-size: 12px; font-weight: bold;">📄 Open ID Document &rarr;</a>', obj.aadhaar_doc.url)
        return "No ID Document Uploaded"
    id_proof_link.short_description = "Identity Document"

    def percentage_view(self, obj):
        return f"{obj.percentage}%" if getattr(obj, 'percentage', None) else "-"
    percentage_view.short_description = "Percentage"

    # --- Bulk Actions ---
    actions = ['mark_as_paid_action', 'export_as_csv']

    @admin.action(description="✓ Mark selected as PAID & Generate Roll Numbers")
    def mark_as_paid_action(self, request, queryset):
        count = 0
        for cand in queryset:
            cand.is_paid = True
            if not cand.roll_number:
                cand.roll_number = f"CBT-{random.randint(100000, 999999)}"
            cand.save()
            count += 1
        self.message_user(request, f"Updated {count} candidate(s) to Paid with generated Roll Numbers.")

    @admin.action(description="📥 Export Selected Candidates to CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="candidates_master.csv"'
        writer = csv.writer(response)

        writer.writerow([
            'Registration No', 'Roll Number', 'Full Name', "Father's Name", 'DOB',
            'Category', 'Gender', 'Email', 'Phone', 'Percentage', 'Status'
        ])

        for c in queryset:
            writer.writerow([
                c.registration_no,
                c.roll_number or "Pending",
                c.full_name,
                c.father_name,
                c.dob,
                c.category,
                c.gender,
                c.email,
                c.phone,
                getattr(c, 'percentage', '0.00'),
                "PAID" if c.is_paid else "PENDING",
            ])
        return response


@admin.register(Grievance)
class GrievanceAdmin(ModelAdmin):
    list_display = ('ticket_id', 'registration_no', 'email', 'category', 'status', 'created_at')
    list_filter = ('category', 'status', 'created_at')
    search_fields = ('ticket_id', 'registration_no', 'email', 'subject', 'description')
    ordering = ('-created_at',)
    list_per_page = 20