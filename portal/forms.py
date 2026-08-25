import re
from django import forms
from django.core.exceptions import ValidationError
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
        raise ValidationError(f"File size too small ({file_size_kb:.1f} KB). Min size: {min_size_kb} KB.")
    if file_size_kb > max_size_kb:
        raise ValidationError(f"File size too large ({file_size_kb:.1f} KB). Max size: {max_size_kb} KB.")

def validate_aadhaar_file(file):
    valid_extensions = ['pdf', 'jpg', 'jpeg', 'png']
    ext = file.name.split('.')[-1].lower()
    if ext not in valid_extensions:
        raise ValidationError("Unsupported format. Allowed: PDF, JPG, JPEG, PNG.")
    
    max_size_kb = 300
    file_size_kb = file.size / 1024
    if file_size_kb > max_size_kb:
        raise ValidationError(f"File size too large ({file_size_kb:.1f} KB). Maximum allowed: {max_size_kb} KB.")


class CandidateForm(forms.ModelForm):
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

    class Meta:
        model = Candidate
        fields = [
            'full_name', 'father_name', 'mother_name', 'dob', 'gender', 'category', 'aadhaar_number',
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
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit Mobile Number'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Complete Address'}),
            'qualification_class': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 10th / 12th / Graduation'}),
            'passing_year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2024'}),
            'total_marks': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_total_marks', 'placeholder': 'e.g. 500'}),
            'obtained_marks': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_obtained_marks', 'placeholder': 'e.g. 430'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'id_photo', 'accept': 'image/*'}),
            'signature': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'id_signature', 'accept': 'image/*'}),
            'aadhaar_doc': forms.ClearableFileInput(attrs={'class': 'form-control', 'id': 'id_aadhaar_doc', 'accept': '.pdf,image/*'}),
        }

    def clean_aadhaar_number(self):
        aadhaar = self.cleaned_data.get('aadhaar_number')
        if aadhaar:
            aadhaar = aadhaar.strip()
            if not (len(aadhaar) == 12 and aadhaar.isdigit()):
                raise ValidationError("Aadhaar Number must be exactly 12 numeric digits.")
        return aadhaar

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and hasattr(photo, 'size'):
            validate_image_file(photo)
        return photo

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
        c1 = cleaned_data.get('center_choice_1')
        c2 = cleaned_data.get('center_choice_2')
        c3 = cleaned_data.get('center_choice_3')

        if c1 and c2 and c3:
            if len({c1.id, c2.id, c3.id}) < 3:
                raise forms.ValidationError("Please select 3 different test centers.")
        return cleaned_data