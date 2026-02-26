from rest_framework.views import exception_handler
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from .response import APIResponse


def custom_exception_handler(exc, context):
    # map django validation error to drf response
    if isinstance(exc, DjangoValidationError):
        return APIResponse.error(
            message=str(exc.message) if hasattr(exc, 'message') else str(exc),
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)

    if response is not None:
        status_code = response.status_code

        # validation errors
        if status_code == status.HTTP_400_BAD_REQUEST:
            if isinstance(response.data, dict):
                return APIResponse.validation_error(
                    details=response.data,
                    message="validation failed",
                    status_code=status_code,
                )
            else:
                return APIResponse.error(
                    message=str(response.data),
                    code="BAD_REQUEST",
                    status_code=status_code,
                )

        # auth errors
        if status_code == status.HTTP_401_UNAUTHORIZED:
            return APIResponse.error(
                message="authentication required",
                code="UNAUTHORIZED",
                status_code=status_code,
            )

        # permission errors
        if status_code == status.HTTP_403_FORBIDDEN:
            return APIResponse.error(
                message="permission denied",
                code="FORBIDDEN",
                status_code=status_code,
            )

        # not found
        if status_code == status.HTTP_404_NOT_FOUND:
            return APIResponse.error(
                message="resource not found",
                code="NOT_FOUND",
                status_code=status_code,
            )

        # method not allowed
        if status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            return APIResponse.error(
                message="method not allowed",
                code="METHOD_NOT_ALLOWED",
                status_code=status_code,
            )

        # server errors
        if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            return APIResponse.error(
                message="internal server error",
                code="SERVER_ERROR",
                status_code=status_code,
            )

        return APIResponse.error(
            message=str(response.data),
            code=f"ERROR_{status_code}",
            status_code=status_code,
        )

    return APIResponse.error(
        message="an unexpected error occurred",
        code="UNKNOWN_ERROR",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
