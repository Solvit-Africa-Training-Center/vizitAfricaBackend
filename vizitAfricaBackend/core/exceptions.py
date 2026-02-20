import logging
from django.core.exceptions import ValidationError as DjangoValidationError, PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from django.db.utils import IntegrityError
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status, exceptions

logger = logging.getLogger(__name__)

class BaseAPIException(exceptions.APIException):
    """Base class for all custom API exceptions."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An unexpected error occurred."
    default_code = "error"

    def __init__(self, detail=None, code=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail, code)

def custom_exception_handler(exc, context):
    """
    Standardize error responses.
    Handles DRF exceptions, Django core exceptions, and DB errors.
    """
    
    # 1. Map Django exceptions to DRF exceptions
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, 'message_dict'):
            exc = exceptions.ValidationError(detail=exc.message_dict)
        elif hasattr(exc, 'messages'):
             exc = exceptions.ValidationError(detail=exc.messages)
        else:
             exc = exceptions.ValidationError(detail=str(exc))
             
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
        
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()
        
    elif isinstance(exc, IntegrityError):
        # Often occurs on unique constraint failures
        # Note: Be careful not to expose too much DB info in production
        logger.error(f"Database IntegrityError: {exc}")
        exc = exceptions.ValidationError(detail="A database conflict occurred. This record might already exist.")

    # 2. Call DRF's default exception handler
    response = exception_handler(exc, context)

    # 3. If DRF handled it, format the response
    if response is not None:
        custom_data = {
            "status": "error",
            "message": "An error occurred",
            "errors": {},
            "code": getattr(exc, 'default_code', 'error')
        }

        # Determine a human-readable message based on status code or detail
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            custom_data["message"] = "Validation failed"
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            custom_data["message"] = "Authentication failed"
        elif response.status_code == status.HTTP_403_FORBIDDEN:
            custom_data["message"] = "Permission denied"
        elif response.status_code == status.HTTP_404_NOT_FOUND:
            custom_data["message"] = "Resource not found"
        elif response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            custom_data["message"] = "Too many requests"
        
        # Extract errors
        if isinstance(response.data, dict):
            # If 'detail' is present, use it as the message
            if 'detail' in response.data:
                custom_data["message"] = response.data.pop('detail')
            
            # Map remaining fields to 'errors'
            custom_data["errors"] = response.data
        elif isinstance(response.data, list):
             custom_data["errors"] = {"non_field_errors": response.data}
        else:
             custom_data["errors"] = {"detail": [str(response.data)]}

        # If errors is empty after popping detail, ensure it's not None
        if not custom_data["errors"]:
            # If message was detail, but errors is now empty, maybe populate it?
            # Let's leave it empty for now or put the message back if needed.
            pass

        response.data = custom_data
        
    else:
        # 4. Handle unhandled exceptions (Server Errors)
        # In production, we don't want to expose stack traces
        logger.exception("Unhandled server error")
        
        # You might want to return a 500 response here manually if response is None
        # but DRF's exception_handler returns None for non-API exceptions.
        # This is where a Middleware or a final catch-all is useful.
        
        return Response({
            "status": "error",
            "message": "Internal server error. Please contact support.",
            "errors": {},
            "code": "server_error"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
