from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

def custom_exception_handler(exc, context):
    """
    Standardize error responses to:
    {
        "status": "error",
        "message": "Human readable summary",
        "errors": { "field": ["detail"], "non_field_errors": ["detail"] },
        "code": "error_code_if_available"
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        custom_data = {
            "status": "error",
            "message": "An error occurred",
            "errors": {}
        }

        # Handle specific status codes
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            custom_data["message"] = "Validation failed"
            if isinstance(response.data, list):
                custom_data["errors"] = {"non_field_errors": response.data}
            elif isinstance(response.data, dict):
                 custom_data["errors"] = response.data
            else:
                 custom_data["errors"] = {"detail": [str(response.data)]}

        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            custom_data["message"] = "Authentication failed"
            # Often 401 returns {"detail": "..."}
            if isinstance(response.data, dict):
                custom_data["errors"] = response.data
            else:
                custom_data["errors"] = {"detail": [str(response.data)]}

        elif response.status_code == status.HTTP_403_FORBIDDEN:
            custom_data["message"] = "Permission denied"
            if isinstance(response.data, dict):
                custom_data["errors"] = response.data
            else:
                custom_data["errors"] = {"detail": [str(response.data)]}
            
        elif response.status_code == status.HTTP_404_NOT_FOUND:
             custom_data["message"] = "Resource not found"
        
        else:
             # Fallback
             detail = response.data.get('detail', 'Unknown error') if isinstance(response.data, dict) else str(response.data)
             custom_data["message"] = detail
             custom_data["errors"] = response.data

        # If specific 'detail' exists in data, override message for better clarity
        if isinstance(response.data, dict) and 'detail' in response.data:
            custom_data["message"] = response.data['detail']
            # Remove detail from errors if it's the only thing, or keep it?
            # Let's keep it in errors for consistency if frontend looks there.
        
        # Ensure errors is always a dict
        if not isinstance(custom_data["errors"], dict):
             custom_data["errors"] = {"detail": [str(custom_data["errors"])]}

        response.data = custom_data

    return response
