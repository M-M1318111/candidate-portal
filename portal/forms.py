import base64
import re
import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from .models import Candidate, ExamCenter


def validate_image_file(file):
    valid_extensions = ['jpg', 'jpeg', 'png']
    ext = file.name.split('.')[-1].lower()
    if ext not in valid_extensions:
        raise ValidationError("Unsupported format. Only JPG, JPEG, and PNG are allowed.")

    min_size_kb = 20
    max_size_kb = 100
    file_size_kb = file.size / 1024

    if file_size_kb < min_size_kb:
        raise ValidationError(f"File size too small ({file_size_kb:.1f} KB). Minimum size required: {min_size_kb} KB.")
    if file_size_kb > max_size_kb:
        raise ValidationError(f"File size too large ({file_size_kb:.1f} KB). Maximum allowed: {max_size_kb} KB.")


def validate_aadhaar_file(file):
    valid_extensions = ['pdf', 'jpg', 'jpeg', 'png']
    ext = file.name.split('.')[-1].lower()
    if ext not in valid_extensions:
        raise ValidationError("Unsupported format. Allowed formats: PDF, JPG, JPEG, PNG.")
    
    max_size_kb = 300
    file_size_kb = file.size / 1024
    if file_size_kb > max_size_kb:
        raise ValidationError(f"File size too large ({file_size_kb:.1f} KB). Maximum allowed: {max_size_kb} KB.")


class CandidateForm(forms.ModelForm):
    # Mandatory Hidden field for Live Webcam Capture Base64
    live_captured_photo = forms.CharField(
        required=False, 
        widget=forms.HiddenInput(attrs={'id': 'id_live_captured_photo'})
    )

    center_choice_1 = forms.ModelChoiceField(
        queryset=ExamCenter.objects.filter(is_active=True),
        empty_label="-- Select Preferred Center 1 --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    center_choice_2 = forms.ModelChoiceField(
        queryset=ExamCenter.objects.filter(is_active=True),
        empty_label="-- Select Preferred Center 2 --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    center_choice_3 = forms.ModelChoiceField(
        queryset=ExamCenter.objects.filter(is_active=True),
        empty_label="-- Select Preferred Center 3 --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_centers = ExamCenter.objects.filter(is_active=True)
        self.fields['center_choice_1'].queryset = active_centers
        self.fields['center_choice_2'].queryset = active_centers
        self.fields['center_choice_3'].queryset = active_centers
        
        # If candidate already exists with a photo in edit mode, photo is optional
        if self.instance and self.instance.pk and self.instance.photo:
            self.fields['photo'].required = False

    class Meta:
        model = Candidate
        fields = [
            'full_name', 'father_name', 'mother_name', 'dob', 'gender', 'category', 'nationality', 'aadhaar_number',
            'email', 'phone', 'address',
            'qualification_class', 'passing_year', 'total_marks', 'obtained_marks',
            'center_choice_1', 'center_choice_2', 'center_choice_3',
            'photo', 'signature', 'aadhaar_doc'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Full Name'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Enter Father's Name"}),
            'mother_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Enter Mother's Name"}),
            'dob': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'nationality': forms.Select(attrs={'class': 'form-select'}),
            'aadhaar_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12-digit Aadhaar Number', 'maxlength': '12'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'id': 'id_email', 'placeholder': 'name@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_phone', 'placeholder': '10-digit Mobile Number', 'maxlength': '10'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Complete Address'}),
            'qualification_class': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10th / 12th / Graduation'}),
            'passing_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2024'}),
            'total_marks': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_total_marks', 'placeholder': 'e.g. 500'}),
            'obtained_marks': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_obtained_marks', 'placeholder': 'e.g. 430'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'id_photo', 'accept': 'image/*'}),
            'signature': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'id_signature', 'accept': 'image/*'}),
            'aadhaar_doc': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'id_aadhaar_doc', 'accept': '.pdf,image/*'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        clean_num = ''.join(filter(str.isdigit, phone))
        if len(clean_num) != 10:
            raise forms.ValidationError("Please enter a valid 10-digit mobile number.")
        return clean_num

    def clean_aadhaar_number(self):
        aadhaar = self.cleaned_data.get('aadhaar_number')
        if aadhaar:
            aadhaar = aadhaar.strip()
            if not (len(aadhaar) == 12 and aadhaar.isdigit()):
                raise ValidationError("Aadhaar Number must be exactly 12 numeric digits.")
        return aadhaar

    def clean_signature(self):
        sig = self.cleaned_data.get('signature')
        if sig and hasattr(sig, 'size'):
            validate_image_file(sig)
        return sig

    def clean_aadhaar_doc(self):
        doc = self.cleaned_data.get('aadhaar_doc')
        if doc and hasattr(doc, 'size'):
            validate_aadhaar_file(doc)
        return doc

    def clean(self):
        cleaned_data = super().clean()
        
        is_edit = bool(self.instance and self.instance.pk and self.instance.photo)
        live_photo = cleaned_data.get('live_captured_photo')
        uploaded_photo = cleaned_data.get('photo')

        # Mandatory Live Webcam Validation
        if not is_edit and not live_photo:
            self.add_error(None, "Mandatory Requirement: You must capture a Live Biometric Webcam Photo before submitting the application.")

        # Convert Live Webcam Base64 into Photo file if provided
        if live_photo:
            try:
                format_prefix, imgstr = live_photo.split(';base64,')
                ext = format_prefix.split('/')[-1].lower()
                if ext not in ['jpg', 'jpeg', 'png']:
                    ext = 'jpg'
                file_name = f"biometric_live_{uuid.uuid4().hex[:8]}.{ext}"
                cleaned_data['photo'] = ContentFile(base64.b64decode(imgstr), name=file_name)
            except Exception:
                self.add_error(None, "Failed to decode live captured photo. Please capture again.")
        elif uploaded_photo and hasattr(uploaded_photo, 'size'):
            validate_image_file(uploaded_photo)

        # 3 Unique Exam Centers Validation
        c1 = cleaned_data.get('center_choice_1')
        c2 = cleaned_data.get('center_choice_2')
        c3 = cleaned_data.get('center_choice_3')

        if c1 and c2 and c3:
            if len({c1.id, c2.id, c3.id}) < 3:
                raise forms.ValidationError("Please select 3 different test centers.")

        total = cleaned_data.get('total_marks')
        obtained = cleaned_data.get('obtained_marks')
        if total is not None and obtained is not None:
            if float(obtained) > float(total):
                self.add_error('obtained_marks', "Obtained marks cannot be greater than total marks.")

        return cleaned_data