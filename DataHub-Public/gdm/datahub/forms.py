from django import forms

class ImportForm(forms.Form):
    username = forms.CharField(label='Username', max_length=100)
    password = forms.CharField(label='Password', max_length=100, widget=forms.PasswordInput)
    project_id = forms.CharField(label='Project ID', max_length=100)
