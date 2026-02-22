"""
Custom exception handler for DRF
Uses unified APIResponse format for all errors
"""

from rest_framework.views import exception_handler
from rest_framework import status
from .response import APIResponse


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns unified response format
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Get status code
        status_code = response.status_code

        # Handle validation errors
        if status_code == status.HTTP_400_BAD_REQUEST:
            if isinstance(response.data, dict):
                # This is a validation error with field-level details
                return APIResponse.validation_error(
                    details=response.data,
                    message="Validation failed",
                    status_code=status_code,
                )
            else:
                # Generic bad request
                return APIResponse.error(
                    message=str(response.data),
                    code="BAD_REQUEST",
                    status_code=status_code,
                )

        # Handle authentication errors
        if status_code == status.HTTP_401_UNAUTHORIZED:
            return APIResponse.error(
                message="Authentication required",
                code="UNAUTHORIZED",
                status_code=status_code,
            )

        # Handle permission errors
        if status_code == status.HTTP_403_FORBIDDEN:
            return APIResponse.error(
                message="Permission denied",
                code="FORBIDDEN",
                status_code=status_code,
            )

        # Handle not found
        if status_code == status.HTTP_404_NOT_FOUND:
            return APIResponse.error(
                message="Resource not found",
                code="NOT_FOUND",
                status_code=status_code,
            )

        # Handle method not allowed
        if status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            return APIResponse.error(
                message="Method not allowed",
                code="METHOD_NOT_ALLOWED",
                status_code=status_code,
            )

        # Handle server errors
        if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            return APIResponse.error(
                message="Internal server error",
                code="SERVER_ERROR",
                status_code=status_code,
            )

        # For other status codes, return generic error
        return APIResponse.error(
            message=str(response.data),
            code=f"ERROR_{status_code}",
            status_code=status_code,
        )

    # If no response from DRF exception handler, handle it here
    return APIResponse.error(
        message="An unexpected error occurred",
        code="UNKNOWN_ERROR",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
