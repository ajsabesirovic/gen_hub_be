import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CustomPasswordValidator:
    """
    Custom password validator that enforces:
    - At least one uppercase letter
    - At least one number
    - At least one special character
    - Minimum 6 characters
    """
    
    def validate(self, password, user=None):
        errors = []
        
        if len(password) < 6:
            errors.append(
                ValidationError(
                    _("This password must contain at least 6 characters."),
                    code='password_too_short',
                )
            )
        
        if not re.search(r'[A-Z]', password):
            errors.append(
                ValidationError(
                    _("This password must contain at least one uppercase letter."),
                    code='password_no_uppercase',
                )
            )
        
        if not re.search(r'[0-9]', password):
            errors.append(
                ValidationError(
                    _("This password must contain at least one number."),
                    code='password_no_number',
                )
            )
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', password):
            errors.append(
                ValidationError(
                    _("This password must contain at least one special character."),
                    code='password_no_special',
                )
            )
        
        if errors:
            raise ValidationError(errors)
    
    def get_help_text(self):
        return _(
            "Your password must contain at least 6 characters, "
            "including at least one uppercase letter, one number, and one special character."
        )

