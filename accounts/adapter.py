import logging
import os
import re

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class CustomAccountAdapter(DefaultAccountAdapter):
    def clean_password(self, password, user=None):
        """
        Validate password meets requirements:
        - At least 6 characters
        - At least one uppercase letter
        - At least one number
        - At least one special character
        """
        errors = []
        
        if len(password) < 6:
            errors.append(
                ValidationError(
                    "This password must contain at least 6 characters.",
                    code='password_too_short',
                )
            )
        
        if not re.search(r'[A-Z]', password):
            errors.append(
                ValidationError(
                    "This password must contain at least one uppercase letter.",
                    code='password_no_uppercase',
                )
            )
        
        if not re.search(r'[0-9]', password):
            errors.append(
                ValidationError(
                    "This password must contain at least one number.",
                    code='password_no_number',
                )
            )
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', password):
            errors.append(
                ValidationError(
                    "This password must contain at least one special character.",
                    code='password_no_special',
                )
            )
        
        if errors:
            raise ValidationError(errors)
        
        return super().clean_password(password, user)
    def send_mail(self, template_prefix, email, context):
        if 'password_reset' in template_prefix:
            user = context.get('user')
            if user and 'username' not in context:
                context['username'] = user.username if hasattr(user, 'username') else user.get_username()
        
        if 'password_reset_url' in context or 'password_reset' in template_prefix:
            frontend_url = (
                getattr(settings, 'FRONTEND_URL', None) or
                getattr(settings, 'REST_AUTH', {}).get('FRONTEND_RESET_PASSWORD_URL', '') or
                os.getenv('FRONTEND_URL', '')
            )
            
            if frontend_url and 'password_reset_url' in context:
                uid = context.get('uid', '')
                token = context.get('token', '')
                
                if not uid or not token:
                    original_url = context.get('password_reset_url', '')
                    patterns = [
                        r'/([^/]+)/([^/]+)/?$',
                        r'/([^/]+)/([^/]+)/([^/]+)/?$',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, original_url)
                        if match:
                            groups = match.groups()
                            if len(groups) >= 2:
                                uid = uid or groups[-2]
                                token = token or groups[-1]
                                break
                
                if uid and token:
                    frontend_url = frontend_url.rstrip('/')
                    if 'reset-password' not in frontend_url.lower() and 'reset' not in frontend_url.lower():
                        context['password_reset_url'] = f"{frontend_url}/reset-password/{uid}/{token}/"
                    else:
                        context['password_reset_url'] = f"{frontend_url}/{uid}/{token}/"
        
        try:
            subject_template = f"{template_prefix}_subject.txt"
            message_template = f"{template_prefix}_message.txt"
            html_template = f"{template_prefix}_message.html"
            
            subject = render_to_string(subject_template, context).strip()
            txt_message = render_to_string(message_template, context)
            html_message = render_to_string(html_template, context)
        except TemplateDoesNotExist:
            if 'password_reset_key' in template_prefix:
                try:
                    base_prefix = template_prefix.replace('_key', '')
                    subject_template = f"{base_prefix}_subject.txt"
                    message_template = f"{base_prefix}_message.txt"
                    html_template = f"{base_prefix}_message.html"
                    
                    subject = render_to_string(subject_template, context).strip()
                    txt_message = render_to_string(message_template, context)
                    html_message = render_to_string(html_template, context)
                except TemplateDoesNotExist:
                    return super().send_mail(template_prefix, email, context)
            else:
                return super().send_mail(template_prefix, email, context)
        except Exception as e:
            logger.warning(f"Error rendering email templates: {str(e)}, falling back to default")
            return super().send_mail(template_prefix, email, context)

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
        
        msg = EmailMultiAlternatives(
            subject,
            txt_message,
            from_email,
            [email],
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send()
