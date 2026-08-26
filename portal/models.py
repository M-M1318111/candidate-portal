import uuid
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

CATEGORY_CHOICES = (
    ('UR', 'General / Unreserved'),
    ('OBC', 'Other Backward Class (OBC)'),
    ('SC', 'Scheduled Caste (SC)'),
    ('ST', 'Scheduled Tribe (ST)'),
    ('EWS', 'Economically Weaker Section (EWS)'),
)

GENDER_CHOICES = (
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
)

NATIONALITY_CHOICES = (
    ('Indian', 'Indian'),
    ('Other', 'Other'),
)

SHIFT_CHOICES = (
    ('Shift 1 (08:30 AM - 11:30 AM)', 'Shift 1: Morning (08:30 AM - 11:30 AM)'),
    ('Shift 2 (12:30 PM - 03:30 PM)', 'Shift 2: Afternoon (12:30 PM - 03:30 PM)'),
    ('Shift 3 (04:30 PM - 07:30 PM)', 'Shift 3: Evening (04:30 PM - 07:30 PM)'),
)

EXAM_DATE_CHOICES = (
    ('15 October 2026', '15 October 2026 (Day 1)'),
    ('16 October 2026', '16 October 2026 (Day 2)'),
    ('17 October 2026', '17 October 2026 (Day 3)'),
    ('18 October 2026', '18 October 2026 (Day 4)'),
    ('19 October 2026', '19 October 2026 (Day 5)'),
)


# --- Master Site Customization Settings ---
class PortalSetting(models.Model):
    board_name = models.CharField(max_length=255, default="Central Examination Authority 2026")
    exam_title = models.CharField(max_length=255, default="Combined Entrance Examination (CEE-2026)")
    helpline_email = models.EmailField(default="support@examauthority.gov.in")
    helpline_phone = models.CharField(max_length=20, default="+91-1800-2026-99")
    announcement_ticker = models.TextField(
        default="Official Notice: Exam center allotment active. Admit cards available on candidate login.",
        help_text="Top scrolling news ticker on portal"
    )
    is_result_published = models.BooleanField(default=False, verbose_name="Publish Result Publicly on Portal")
    result_published_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Global Portal Setting"
        verbose_name_plural = "Global Portal Settings"

    @property
    def site_name(self):
        return self.board_name

    @property
    def is_admit_card_active(self):
        return True

    def __str__(self):
        return self.board_name


class ExamCenter(models.Model):
    center_code = models.CharField(max_length=20, unique=True)
    center_name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    full_address = models.TextField()
    capacity_per_shift = models.PositiveIntegerField(default=100, help_text="Max candidates per shift")
    assigned_incharge = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_center',
        help_text="Staff user assigned as Center Incharge"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Exam Center"
        verbose_name_plural = "Exam Centers"

    def __str__(self):
        return f"{self.center_name} ({self.center_code}, {self.city})"


class Candidate(models.Model):
    registration_no = models.CharField(max_length=30, unique=True, blank=True, null=True)
    roll_number = models.CharField(max_length=30, unique=True, blank=True, null=True)
    
    # 1. Personal Details
    full_name = models.CharField(max_length=100)
    father_name = models.CharField(max_length=100)
    mother_name = models.CharField(max_length=100)
    dob = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    aadhaar_number = models.CharField(max_length=12, blank=True, null=True)
    nationality = models.CharField(max_length=20, choices=NATIONALITY_CHOICES, default='Indian')
   
    # 2. Contact Details
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    address = models.TextField()

    # 3. Educational Details
    qualification_class = models.CharField(max_length=50)
    passing_year = models.IntegerField()
    total_marks = models.DecimalField(max_digits=6, decimal_places=2)
    obtained_marks = models.DecimalField(max_digits=6, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    # 4. Exam Center Choices
    center_choice_1 = models.ForeignKey(ExamCenter, on_delete=models.SET_NULL, null=True, blank=True, related_name='pref_1')
    center_choice_2 = models.ForeignKey(ExamCenter, on_delete=models.SET_NULL, null=True, blank=True, related_name='pref_2')
    center_choice_3 = models.ForeignKey(ExamCenter, on_delete=models.SET_NULL, null=True, blank=True, related_name='pref_3')

    # 5. Documents Upload
    photo = models.ImageField(upload_to='photos/')
    signature = models.ImageField(upload_to='signatures/')
    aadhaar_doc = models.FileField(upload_to='aadhaar_docs/', blank=True, null=True)

    # 6. Payment & Fee Info
    fee_amount = models.DecimalField(max_digits=7, decimal_places=2, default=500.00)
    is_paid = models.BooleanField(default=False)
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    
    # 7. Admin Allotment & Scheduling Engine
    allotted_center = models.ForeignKey(
        ExamCenter, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='allotted_candidates',
        verbose_name="Allotted Center"
    )
    exam_date = models.CharField(
        max_length=50, 
        choices=EXAM_DATE_CHOICES, 
        default='15 October 2026',
        verbose_name="Exam Date"
    )
    exam_shift = models.CharField(
        max_length=60, 
        choices=SHIFT_CHOICES, 
        default='Shift 1 (08:30 AM - 11:30 AM)',
        verbose_name="Exam Shift"
    )
    is_admit_card_released = models.BooleanField(default=False, verbose_name="Admit Card Released")
    exam_center = models.CharField(max_length=255, blank=True, null=True, default='Center to be allotted')
    
    # 8. Live Attendance & Verification
    is_present = models.BooleanField(default=False, verbose_name="Attended / Present")
    entry_verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Entry Timestamp")
    
    # 9. Result & Scorecard Engine
    exam_marks_obtained = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Exam Marks (CBT)")
    exam_total_marks = models.DecimalField(max_digits=6, decimal_places=2, default=300.00, verbose_name="Total Marks (CBT)")
    exam_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Score %")
    exam_rank = models.PositiveIntegerField(null=True, blank=True, verbose_name="All India Rank")
    exam_qualification_status = models.CharField(
        max_length=20,
        choices=(('QUALIFIED', 'Qualified'), ('NOT_QUALIFIED', 'Not Qualified'), ('PENDING', 'Pending Evaluation')),
        default='PENDING',
        verbose_name="Result Status"
    )
    is_result_declared = models.BooleanField(default=False, verbose_name="Individual Result Declared")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Candidate Application"
        verbose_name_plural = "Candidate Applications"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.registration_no:
            self.registration_no = f"CAND-{uuid.uuid4().hex[:8].upper()}"
        
        if self.total_marks and self.obtained_marks and float(self.total_marks) > 0:
            self.percentage = round((float(self.obtained_marks) / float(self.total_marks)) * 100, 2)
            
        if self.exam_marks_obtained is not None and self.exam_total_marks and float(self.exam_total_marks) > 0:
            self.exam_percentage = round((float(self.exam_marks_obtained) / float(self.exam_total_marks)) * 100, 2)
            if self.exam_qualification_status == 'PENDING':
                self.exam_qualification_status = 'QUALIFIED' if self.exam_percentage >= 40.0 else 'NOT_QUALIFIED'
            
        if self.allotted_center:
            self.exam_center = f"{self.allotted_center.center_name}, {self.allotted_center.city}"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.registration_no})"


GRIEVANCE_CATEGORY_CHOICES = (
    ('PAYMENT', 'Payment / Fee Related'),
    ('DOCUMENT', 'Photo / Signature Correction'),
    ('ADMIT_CARD', 'Admit Card Issue'),
    ('CENTER', 'Exam Center Query'),
    ('RESULT', 'Result / Scorecard Query'),
    ('OTHER', 'Other Technical Issue'),
)

GRIEVANCE_STATUS_CHOICES = (
    ('OPEN', 'Open / Under Review'),
    ('RESOLVED', 'Resolved'),
    ('CLOSED', 'Closed'),
)


class Grievance(models.Model):
    ticket_id = models.CharField(max_length=20, unique=True, blank=True)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='grievances', null=True, blank=True)
    registration_no = models.CharField(max_length=30)
    email = models.EmailField()
    category = models.CharField(max_length=20, choices=GRIEVANCE_CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    admin_reply = models.TextField(blank=True, null=True, help_text="Direct official resolution sent to student")
    replied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_tickets')
    replied_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=GRIEVANCE_STATUS_CHOICES, default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Grievance Ticket"
        verbose_name_plural = "Grievance Tickets"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_id} - {self.subject} ({self.status})"


# ==============================================================================
# 🎯 ANSWER KEY & OBJECTION CHALLENGE DESK
# ==============================================================================
class AnswerKey(models.Model):
    SHIFT_TYPE_CHOICES = (
        ('Shift 1', 'Shift 1 (Morning)'),
        ('Shift 2', 'Shift 2 (Evening)'),
    )
    question_number = models.PositiveIntegerField(db_index=True)
    question_text = models.TextField(help_text="Question statement / problem description")
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_option = models.CharField(max_length=2, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])
    exam_shift = models.CharField(max_length=50, choices=SHIFT_TYPE_CHOICES, default='Shift 1')
    is_revised = models.BooleanField(default=False, help_text="True if modified after objection review")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['question_number']
        unique_together = ('question_number', 'exam_shift')
        verbose_name = "Provisional & Revised Answer Key"
        verbose_name_plural = "Provisional & Revised Answer Keys"

    def __str__(self):
        rev = " [REVISED]" if self.is_revised else ""
        return f"Q{self.question_number} [{self.exam_shift}] - Correct: {self.correct_option}{rev}"


class QuestionObjection(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Under Review'),
        ('ACCEPTED', 'Accepted & Revised'),
        ('REJECTED', 'Rejected / Invalid'),
    )
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='objections')
    question = models.ForeignKey(AnswerKey, on_delete=models.CASCADE, related_name='raised_objections')
    claimed_option = models.CharField(max_length=2, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])
    justification = models.TextField(help_text="Detailed justification / book reference")
    supporting_doc = models.FileField(upload_to='objections_docs/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    admin_remark = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Candidate Objection / Challenge"
        verbose_name_plural = "Candidate Objections / Challenges"

    def __str__(self):
        return f"Objection by {self.candidate.registration_no} on Q{self.question.question_number} [{self.status}]"


# ==============================================================================
# 📨 NOTIFICATION LOG TRACKER MODEL
# ==============================================================================
class NotificationLog(models.Model):
    CHANNEL_CHOICES = (
        ('EMAIL', 'Email Dispatch'),
        ('SMS', 'SMS Gateway'),
    )
    STATUS_CHOICES = (
        ('SENT', 'Successfully Sent'),
        ('FAILED', 'Dispatch Failed'),
    )
    recipient = models.CharField(max_length=150)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='EMAIL')
    subject = models.CharField(max_length=255, blank=True, null=True)
    message_body = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SENT')
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = "Notification Log (Email/SMS)"
        verbose_name_plural = "Notification Logs (Email/SMS)"

    def __str__(self):
        return f"[{self.sent_at.strftime('%d-%b %H:%M')}] {self.channel} to {self.recipient} - {self.status}"


# ==============================================================================
# 🛡️ AUDIT LOG & SECURITY ACTIVITY TRACKER
# ==============================================================================
class AuditLog(models.Model):
    ACTION_CHOICES = (
        ('ATTENDANCE_CHECKIN', 'Gate Attendance Check-in'),
        ('MARKS_ENTERED', 'CBT Marks Entry/Update'),
        ('RESULT_DECLARED', 'Result Published'),
        ('ADMIT_CARD_RELEASED', 'Admit Card Released'),
        ('KEY_REVISED', 'Answer Key Revised via Objection'),
        ('HELPDESK_RESOLVED', 'Helpdesk Query Resolved'),
    )
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    candidate = models.ForeignKey(Candidate, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Security & Audit Log"
        verbose_name_plural = "Security & Audit Logs"

    def __str__(self):
        return f"[{self.timestamp.strftime('%d-%b %H:%M')}] {self.action} by {self.user.username if self.user else 'System'}"