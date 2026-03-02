"""
Custom validators for better data validation.
"""

import re
from rest_framework import serializers


def validate_strong_password(password: str) -> str:
    """
    Validate password strength:
    - Min 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter  
    - At least 1 number
    - At least 1 special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
    """
    if len(password) < 8:
        raise serializers.ValidationError("La contraseña debe tener al menos 8 caracteres.")
    
    if not re.search(r'[A-Z]', password):
        raise serializers.ValidationError("La contraseña debe contener al menos una letra mayúscula.")
    
    if not re.search(r'[a-z]', password):
        raise serializers.ValidationError("La contraseña debe contener al menos una letra minúscula.")
    
    if not re.search(r'[0-9]', password):
        raise serializers.ValidationError("La contraseña debe contener al menos un número.")
    
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        raise serializers.ValidationError("La contraseña debe contener al menos un carácter especial (!@#$%^&*...).")
    
    return password


def validate_non_empty_name(name: str) -> str:
    """Validate that name is not empty or only whitespace."""
    cleaned_name = name.strip()
    if len(cleaned_name) < 2:
        raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres válidos.")
    
    if not re.match(r'^[a-zA-ZÀ-ÿ\s\.]+$', cleaned_name):
        raise serializers.ValidationError("El nombre solo puede contener letras, espacios y puntos.")
    
    return cleaned_name


def validate_phone_format(phone: str) -> str:
    """Validate phone number format (optional field)."""
    if not phone:  # Empty is allowed
        return phone
    
    # Remove spaces, dashes, parentheses
    cleaned_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Must be 8-15 digits, optionally starting with +
    if not re.match(r'^\+?\d{8,15}$', cleaned_phone):
        raise serializers.ValidationError("El teléfono debe tener entre 8 y 15 dígitos, opcionalmente con + al inicio.")
    
    return phone


def validate_company_name(company: str) -> str:
    """Validate company name format (optional field)."""
    if not company:  # Empty is allowed
        return company
    
    cleaned_company = company.strip()
    if len(cleaned_company) < 2:
        raise serializers.ValidationError("El nombre de empresa debe tener al menos 2 caracteres.")
    
    if len(cleaned_company) > 255:
        raise serializers.ValidationError("El nombre de empresa no puede exceder 255 caracteres.")
    
    return cleaned_company