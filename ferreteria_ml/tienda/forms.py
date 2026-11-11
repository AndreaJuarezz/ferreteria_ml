from django import forms
from django.contrib.auth.models import User
from .models import Producto


class RegistroForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']


class ProductoForm(forms.ModelForm):
    stock = forms.IntegerField(
        min_value=0,
        max_value=1000,
        error_messages={
            'max_value': 'No es posible guardar esa cantidad de stock. El máximo permitido es 1000.',
            'min_value': 'El stock no puede ser negativo.',
            'invalid': 'Ingresa un número entero válido.',
        },
        widget=forms.NumberInput(attrs={'min': 0, 'max': 1000}),
        help_text='Máximo permitido: 1000 unidades.',
    )

    class Meta:
        model = Producto
        fields = ['nombre', 'categoria', 'precio', 'descripcion', 'stock']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4}),
        }