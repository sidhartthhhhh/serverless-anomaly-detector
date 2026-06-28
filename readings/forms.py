from django import forms


class CsvUploadForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if not uploaded.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a CSV file.")
        if uploaded.size > 2 * 1024 * 1024:
            raise forms.ValidationError("CSV must be smaller than 2 MB.")
        return uploaded
