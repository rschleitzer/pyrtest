"""FHIR-specific assertion helpers for testing."""
import requests
from typing import Dict, Any, Optional, List


class FHIRAssertions:
    """Assertion helpers for FHIR responses."""

    @staticmethod
    def assert_status_code(response: requests.Response, expected: int, message: Optional[str] = None):
        """Assert response has expected status code."""
        msg = message or f"Expected status {expected}, got {response.status_code}"
        if response.status_code != expected:
            # Try to get OperationOutcome for better error messages
            try:
                body = response.json()
                if body.get('resourceType') == 'OperationOutcome':
                    issues = body.get('issue', [])
                    if issues:
                        msg += f"\nOperationOutcome: {issues[0].get('diagnostics', 'No details')}"
            except:
                pass
            msg += f"\nResponse: {response.text[:500]}"
        assert response.status_code == expected, msg

    @staticmethod
    def assert_created(response: requests.Response, resource_type: str):
        """Assert resource was created successfully (201)."""
        FHIRAssertions.assert_status_code(response, 201, f"{resource_type} creation failed")
        assert 'Location' in response.headers, "Location header missing from create response"
        return response.json()

    @staticmethod
    def assert_read_success(response: requests.Response, resource_type: str):
        """Assert resource was read successfully (200)."""
        FHIRAssertions.assert_status_code(response, 200, f"{resource_type} read failed")
        resource = response.json()
        assert resource['resourceType'] == resource_type, \
            f"Expected {resource_type}, got {resource.get('resourceType')}"
        return resource

    @staticmethod
    def assert_updated(response: requests.Response, resource_type: str):
        """Assert resource was updated successfully (200)."""
        FHIRAssertions.assert_status_code(response, 200, f"{resource_type} update failed")
        return response.json()

    @staticmethod
    def assert_deleted(response: requests.Response):
        """Assert resource was deleted successfully (204 or 200)."""
        assert response.status_code in [200, 204], \
            f"Expected 200 or 204 for delete, got {response.status_code}"

    @staticmethod
    def assert_not_found(response: requests.Response):
        """Assert resource was not found (404) or deleted (410)."""
        assert response.status_code in [404, 410], \
            f"Expected 404 Not Found or 410 Gone, got {response.status_code}"
        resource = response.json()
        assert resource['resourceType'] == 'OperationOutcome', \
            "Expected OperationOutcome for 404/410"

    @staticmethod
    def assert_bad_request(response: requests.Response):
        """Assert request was invalid (400)."""
        FHIRAssertions.assert_status_code(response, 400, "Expected 400 Bad Request")
        resource = response.json()
        assert resource['resourceType'] == 'OperationOutcome', \
            "Expected OperationOutcome for 400"

    @staticmethod
    def assert_conflict(response: requests.Response):
        """Assert there was a conflict (409 or 412)."""
        assert response.status_code in [409, 412], \
            f"Expected 409 or 412 for conflict, got {response.status_code}"

    @staticmethod
    def assert_bundle(response: requests.Response, resource_type: Optional[str] = None) -> Dict[str, Any]:
        """Assert response is a valid Bundle."""
        FHIRAssertions.assert_status_code(response, 200, "Bundle search failed")
        bundle = response.json()
        assert bundle['resourceType'] == 'Bundle', \
            f"Expected Bundle, got {bundle.get('resourceType')}"
        assert 'type' in bundle, "Bundle missing type field"
        assert 'entry' in bundle or bundle.get('total', 0) == 0, \
            "Bundle missing entry field"

        # Validate entries if resource type specified
        # Only check primary matches (mode='match'), not includes (mode='include')
        if resource_type and 'entry' in bundle:
            for entry in bundle['entry']:
                search_mode = entry.get('search', {}).get('mode', 'match')
                if search_mode == 'match':  # Only validate primary search results
                    resource = entry.get('resource', {})
                    assert resource.get('resourceType') == resource_type, \
                        f"Expected {resource_type} in bundle, got {resource.get('resourceType')}"

        return bundle

    @staticmethod
    def assert_bundle_count(bundle: Dict[str, Any], expected_count: int):
        """Assert Bundle has expected number of entries."""
        actual = len(bundle.get('entry', []))
        assert actual == expected_count, \
            f"Expected {expected_count} entries in Bundle, got {actual}"

    @staticmethod
    def assert_bundle_contains(bundle: Dict[str, Any], resource_id: str) -> bool:
        """Assert Bundle contains a resource with given ID."""
        entries = bundle.get('entry', [])
        for entry in entries:
            resource = entry.get('resource', {})
            if resource.get('id') == resource_id:
                return True
        raise AssertionError(f"Bundle does not contain resource with id={resource_id}")

    @staticmethod
    def assert_resource_has_field(resource: Dict[str, Any], field_path: str):
        """Assert resource has a field (supports dot notation).

        Example: assert_resource_has_field(patient, 'name.0.family')
        """
        parts = field_path.split('.')
        obj = resource
        for part in parts:
            if part.isdigit():
                # Array index
                idx = int(part)
                assert isinstance(obj, list) and len(obj) > idx, \
                    f"Field path {field_path} not found (array index {idx} out of bounds)"
                obj = obj[idx]
            else:
                assert isinstance(obj, dict) and part in obj, \
                    f"Field path {field_path} not found (missing '{part}')"
                obj = obj[part]

    @staticmethod
    def assert_resource_field_equals(resource: Dict[str, Any], field_path: str, expected_value: Any):
        """Assert resource field has expected value."""
        FHIRAssertions.assert_resource_has_field(resource, field_path)

        parts = field_path.split('.')
        obj = resource
        for part in parts:
            if part.isdigit():
                obj = obj[int(part)]
            else:
                obj = obj[part]

        assert obj == expected_value, \
            f"Expected {field_path}={expected_value}, got {obj}"

    @staticmethod
    def assert_operation_outcome(response: requests.Response, severity: Optional[str] = None):
        """Assert response contains an OperationOutcome.

        Args:
            response: HTTP response
            severity: Optional expected severity (error, warning, information)
        """
        resource = response.json()
        assert resource['resourceType'] == 'OperationOutcome', \
            f"Expected OperationOutcome, got {resource.get('resourceType')}"
        assert 'issue' in resource, "OperationOutcome missing issue array"
        assert len(resource['issue']) > 0, "OperationOutcome has no issues"

        if severity:
            issue_severities = [issue.get('severity') for issue in resource['issue']]
            assert severity in issue_severities, \
                f"Expected issue with severity '{severity}', got {issue_severities}"

        return resource
