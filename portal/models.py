from django.db import models
import uuid

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
class ExamCenter(models.Model):
    center_code = models.CharField(max_length=20, unique=True)
    center_name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    full_address = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.center_name} - ({self.center_code}, {self.city})"


class Candidate(models.Model):
    registration_no = models.CharField(max_length=20, unique=True, blank=True, null=True)
    roll_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    
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
    center_choice_1 = models.ForeignKey(ExamCenter, on_delete=models.SET_NULL, null=True, related_name='pref_1')
    center_choice_2 = models.ForeignKey(ExamCenter, on_delete=models.SET_NULL, null=True, related_name='pref_2')
    center_choice_3 = models.ForeignKey(ExamCenter, on_delete=models.SET_NULL, null=True, related_name='pref_3')

    # 5. Documents Upload
    photo = models.ImageField(upload_to='photos/')
    signature = models.ImageField(upload_to='signatures/')
    aadhaar_doc = models.FileField(upload_to='aadhaar_docs/', blank=True, null=True)

    # 6. Payment & Final Allotted Info
    fee_amount = models.DecimalField(max_digits=6, decimal_places=2, default=500.00)
    is_paid = models.BooleanField(default=False)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    exam_center = models.CharField(max_length=255, default='Center to be allotted')
    exam_date = models.CharField(max_length=50, default='15 October 2026')
    created_at = models.DateTimeField(auto_now_add=True)
    

    def save(self, *args, **kwargs):
        if not self.registration_no:
            self.registration_no = f"CAND-{uuid.uuid4().hex[:8].upper()}"
        if not self.roll_number:
            self.roll_number = f"ROLL-{uuid.uuid4().hex[:6].upper()}"
        
        if self.total_marks and self.obtained_marks and self.total_marks > 0:
            self.percentage = round((self.obtained_marks / self.total_marks) * 100, 2)
            
        if self.center_choice_1:
            self.exam_center = f"{self.center_choice_1.center_name}, {self.center_choice_1.city}"
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.registration_no})"
GRIEVANCE_CATEGORY_CHOICES = (
    ('PAYMENT', 'Payment / Fee Related'),
    ('DOCUMENT', 'Photo / Signature Correction'),
    ('ADMIT_CARD', 'Admit Card Issue'),
    ('CENTER', 'Exam Center Query'),
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
    admin_reply = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=15, choices=GRIEVANCE_STATUS_CHOICES, default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticket_id} - {self.subject} ({self.status})"