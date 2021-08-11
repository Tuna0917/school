from django.forms.models import ModelForm
import django.forms as forms
from .models import *

class BanForm(ModelForm):
    class Meta:
        model = Seat
        fields = ['ban_list']

    ban_list = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        widget=forms.CheckboxSelectMultiple
    )