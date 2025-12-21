from django import forms
from django.contrib.auth.models import User
from .models import Organizer, Customer, Event, Booking
import datetime


# -------------------------------
# UserForm
# Allows editing of basic User info (first name, email).
# Used in profile editing or registration flows.
# -------------------------------
class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


# -------------------------------
# CustomerForm
# Handles extended customer info including profile image,
# contact details, DOB split into day/month/year for better UX,
# language, interests, and address.
# -------------------------------
class CustomerForm(forms.ModelForm):
    # Dropdowns for selecting date of birth
    dob_day = forms.ChoiceField(
        choices=[('', 'Day')] + [(str(i), i) for i in range(1, 32)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    dob_month = forms.ChoiceField(
        choices=[('', 'Month')] + [(str(i), datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )
    dob_year = forms.ChoiceField(
        choices=[('', 'Year')] + [(str(y), y) for y in range(datetime.date.today().year, 1900, -1)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'})
    )

    class Meta:
        model = Customer
        fields = ['image', 'phone', 'city', 'state', 'language', 'interests', 'dob', 'address']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'language': forms.TextInput(attrs={'class': 'form-control'}),
            'interests': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'dob': forms.HiddenInput(),  # actual dob stored here, but selected from dropdowns above
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize the form and prefill DOB dropdowns if value exists."""
        super().__init__(*args, **kwargs)
        dob = self.instance.dob
        if dob:
            self.fields['dob_day'].initial = str(dob.day)
            self.fields['dob_month'].initial = str(dob.month)
            self.fields['dob_year'].initial = str(dob.year)

    def clean(self):
        """Custom validation for DOB: must either be fully filled or left empty."""
        cleaned_data = super().clean()
        day = cleaned_data.get('dob_day')
        month = cleaned_data.get('dob_month')
        year = cleaned_data.get('dob_year')

        if day and month and year:
            try:
                cleaned_data['dob'] = datetime.date(int(year), int(month), int(day))
            except ValueError:
                self.add_error('dob_day', 'Invalid date')
        elif day or month or year:
            self.add_error('dob_day', 'Please complete all DOB fields')
        return cleaned_data


# -------------------------------
# OrganizerForm
# Used for creating or editing organizer profiles,
# including organization details and payout/payment info.
# -------------------------------
class OrganizerForm(forms.ModelForm):
    class Meta:
        model = Organizer
        fields = [
            'organization_name', 'logo', 'website', 'phone', 'city', 'state', 'description',
            'bank_account_number', 'bank_ifsc_code', 'bank_name', 'upi_id'
        ]
        widgets = {
            'organization_name': forms.TextInput(attrs={'class': 'form-control'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'bank_account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_ifsc_code': forms.TextInput(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'upi_id': forms.TextInput(attrs={'class': 'form-control'}),
        }


# -------------------------------
# EventForm
# Allows organizers to create/update events with full details
# (title, description, host, price, capacity, banner, etc.)
# -------------------------------
class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = [
            'title', 'description', 'host', 'special_attractions',
            'location', 'latitude', 'longitude',   # ✅ add here
            'capacity', 'price',
            'terms_and_conditions', 'registration_deadline',
            'banner', 'date', 'time', 'category',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control bg-dark text-light'}),
            'description': forms.Textarea(attrs={'class': 'form-control bg-dark text-light', 'rows': 4}),
            'host': forms.TextInput(attrs={'class': 'form-control bg-dark text-light'}),
            'special_attractions': forms.Textarea(attrs={'class': 'form-control bg-dark text-light', 'rows': 3}),
            'location': forms.TextInput(attrs={'class': 'form-control bg-dark text-light'}),
            'latitude': forms.HiddenInput(),   # ✅ hidden
            'longitude': forms.HiddenInput(),  # ✅ hidden
            'capacity': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light'}),
            'price': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light', 'step': '0.01'}),
            'terms_and_conditions': forms.Textarea(attrs={'class': 'form-control bg-dark text-light', 'rows': 4}),
            'registration_deadline': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-control bg-dark text-light'
            }),
            'banner': forms.ClearableFileInput(attrs={'class': 'form-control bg-dark text-light'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control bg-dark text-light'}),
            'time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control bg-dark text-light'}),
            'category': forms.Select(attrs={'class': 'form-control bg-dark text-light'}),
        }


# -------------------------------
# BookingForm
# Form used for customers to book tickets for events.
# Only includes user-entered fields.
# Event, user, total_price, and payment_status will be set in the view.
# -------------------------------
class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['booking_name', 'customer_email', 'customer_phone', 'tickets_booked']
        widgets = {
            'booking_name': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Enter name for booking'
            }),
            'customer_email': forms.EmailInput(attrs={
                'class': 'form-control', 'placeholder': 'Enter email'
            }),
            'customer_phone': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Enter phone number'
            }),
            'tickets_booked': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1'
            }),
        }
