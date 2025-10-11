"""Pytest configuration and shared fixtures."""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from utils.fhir_client import FHIRClient
from utils.assertions import FHIRAssertions


# Purge key for cleanup operations
PURGE_KEY = "c522382c-8656-463e-8277-b913e4466f53"

# Global list to track resources created during test
_created_resources = []


@pytest.fixture(scope="function")
def client():
    """Create FHIR client for tests with resource tracking."""
    client = FHIRClient()

    # Wrap create method to track created resources
    original_create = client.create

    def tracked_create(resource):
        response = original_create(resource)
        if response.status_code in [200, 201]:
            # Track the created resource
            result = response.json()
            resource_type = result.get('resourceType')
            resource_id = result.get('id')
            if resource_type and resource_id:
                _created_resources.append((resource_type, resource_id))
        return response

    client.create = tracked_create
    return client


@pytest.fixture(scope="function")
def assertions():
    """Create assertions helper."""
    return FHIRAssertions()


@pytest.fixture(scope="function", autouse=True)
def cleanup_created_resources(request):
    """Automatically cleanup only resources created during the test.

    This fixture runs after every test and only deletes resources that were
    created during that specific test, avoiding accidental deletion of
    shared test database resources.
    """
    # Clear the tracking list before test
    _created_resources.clear()

    # Track test-specific identifiers to clean up resources created by bundles
    test_name = request.node.name
    test_markers = []

    # Common test identifiers that might be in family names or other fields
    if "transaction" in test_name.lower():
        test_markers.extend(["TransactionTest", "ConditionalTxn"])
    if "rollback" in test_name.lower():
        test_markers.append("TestRollback")

    yield  # Let the test run first

    # After test completes, delete tracked resources
    client = FHIRClient()

    # Track which resource types we deleted from
    deleted_resource_types = set()

    # Delete tracked resources from client.create()
    for resource_type, resource_id in _created_resources:
        try:
            client.delete(resource_type, resource_id)
            deleted_resource_types.add(resource_type)
        except Exception:
            pass

    # Also clean up test-specific resources (from transaction bundles, etc.) using conditional delete
    if test_markers:
        for marker in test_markers:
            try:
                # Use conditional delete with family name search parameter
                response = client.conditional_delete("Patient", {"family": marker})
                if response.status_code in [200, 204]:
                    deleted_resource_types.add("Patient")
            except Exception:
                pass

    # Purge schemas for resource types we deleted from
    for resource_type in deleted_resource_types:
        try:
            purge_url = f"{client.base_url}/purgeschema/{resource_type}/{PURGE_KEY}"
            client.session.get(purge_url)
        except Exception:
            pass  # Ignore purge errors

    # Clear the list for the next test
    _created_resources.clear()
