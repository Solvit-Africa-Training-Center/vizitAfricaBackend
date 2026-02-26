"""
Unified API Response Handler
Ensures all API responses follow a consistent structure
"""

from rest_framework.response import Response
from rest_framework.exceptions import APIException
from typing import Any, Dict, Optional, List


class APIResponse:
    """
    Standardized API Response Format:
    {
        "success": bool,
        "data": any,
        "error": {
            "code": str,
            "message": str,
            "details": {} or []
        },
        "message": str
    }
    """

    @staticmethod
    def success(
        data: Any = None,
        message: str = "Request successful",
        status_code: int = 200,
    ) -> Response:
        """Return a successful response"""
        return Response(
            {
                "success": True,
                "data": data,
                "error": None,
                "message": message,
            },
            status=status_code,
        )

    @staticmethod
    def error(
        message: str,
        code: str = "ERROR",
        details: Optional[Dict | List] = None,
        status_code: int = 400,
    ) -> Response:
        """Return an error response"""
        return Response(
            {
                "success": False,
                "data": None,
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                },
                "message": message,
            },
            status=status_code,
        )

    @staticmethod
    def validation_error(
        details: Dict[str, List[str]],
        message: str = "Validation failed",
        status_code: int = 400,
    ) -> Response:
        """Return a validation error response"""
        return Response(
            {
                "success": False,
                "data": None,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": message,
                    "details": details,
                },
                "message": message,
            },
            status=status_code,
        )

    @staticmethod
    def paginated(
        data: List,
        count: int,
        next_url: Optional[str] = None,
        previous_url: Optional[str] = None,
        message: str = "Request successful",
        status_code: int = 200,
    ) -> Response:
        """Return a paginated response"""
        return Response(
            {
                "success": True,
                "data": {
                    "results": data,
                    "count": count,
                    "next": next_url,
                    "previous": previous_url,
                },
                "error": None,
                "message": message,
            },
            status=status_code,
        )
