"""Test suite for conditional create operations (If-None-Exist)."""
import pyrtest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.fhir_client import FHIRClient
from utils.assertions import FHIRAssertions
from fixtures.resource_generators import FHIRResourceGenerator


@pyrtest.fixture
def client():
    """Create FHIR client for tests."""
    return FHIRClient()


@pyrtest.fixture
def assertions():
    """Create assertions helper."""
    return FHIRAssertions()


class TestConditionalCreate:
    """Test conditional create using If-None-Exist header."""

    def test_conditional_create_first_request_creates(self, client, assertions):
        """Test first conditional create creates new resource (201)."""
        identifier_value = f"COND-CREATE-{FHIRResourceGenerator.generate_id()}"
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "ConditionalTest"}],
            identifier=[{"value": identifier_value}]
        )

        created_id = None
        try:
            response = client.conditional_create(
                patient,
                {"identifier": identifier_value}
            )

            # Should create new resource
            assert response.status_code == 201, \
                f"First conditional create should return 201, got {response.status_code}"

            created = response.json()
            created_id = created['id']
            assert created['resourceType'] == 'Patient'
            assert 'Location' in response.headers

            # Verify identifier matches
            identifiers = created.get('identifier', [])
            matching = [i for i in identifiers if i.get('value') == identifier_value]
            assert len(matching) > 0, "Created patient should have the identifier"

        finally:
            if created_id:
                client.delete("Patient", created_id)

    def test_conditional_create_duplicate_returns_existing(self, client, assertions):
        """Test second conditional create returns existing resource (200)."""
        identifier_value = f"COND-DUP-{FHIRResourceGenerator.generate_id()}"
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "ConditionalDup"}],
            identifier=[{"value": identifier_value}]
        )

        created_id = None
        try:
            # First request - creates
            response1 = client.conditional_create(
                patient,
                {"identifier": identifier_value}
            )
            assert response1.status_code == 201
            created_id = response1.json()['id']

            # Second request - should return existing
            response2 = client.conditional_create(
                patient,
                {"identifier": identifier_value}
            )

            assert response2.status_code == 200, \
                f"Duplicate conditional create should return 200, got {response2.status_code}"

            existing = response2.json()
            assert existing['id'] == created_id, \
                "Should return the same resource ID"
            assert existing['resourceType'] == 'Patient'

        finally:
            if created_id:
                client.delete("Patient", created_id)

    def test_conditional_create_no_duplicate(self, client, assertions):
        """Test conditional create doesn't create duplicate resources."""
        identifier_value = f"COND-NODUP-{FHIRResourceGenerator.generate_id()}"
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "ConditionalNoDup"}],
            identifier=[{"value": identifier_value}]
        )

        created_id = None
        try:
            # First request
            response1 = client.conditional_create(
                patient,
                {"identifier": identifier_value}
            )
            assert response1.status_code == 201
            created_id = response1.json()['id']

            # Second request
            response2 = client.conditional_create(
                patient,
                {"identifier": identifier_value}
            )
            assert response2.status_code == 200

            # Search to verify only one exists
            search_resp = client.search("Patient", {"identifier": identifier_value})
            search_result = search_resp.json()

            assert search_result.get('total', 0) == 1, \
                "Should only have one patient with this identifier"

        finally:
            if created_id:
                client.delete("Patient", created_id)

    def test_conditional_create_with_system_and_value(self, client, assertions):
        """Test conditional create with system|value identifier format."""
        system = "http://hospital.org/conditional-test"
        value = f"VAL-{FHIRResourceGenerator.generate_id()}"
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "ConditionalSystem"}],
            identifier=[{"system": system, "value": value}]
        )

        created_id = None
        try:
            # Create with system|value search
            response1 = client.conditional_create(
                patient,
                {"identifier": f"{system}|{value}"}
            )
            assert response1.status_code == 201
            created_id = response1.json()['id']

            # Second request should find it
            response2 = client.conditional_create(
                patient,
                {"identifier": f"{system}|{value}"}
            )
            assert response2.status_code == 200
            assert response2.json()['id'] == created_id

        finally:
            if created_id:
                client.delete("Patient", created_id)

    def test_conditional_create_multiple_matches_precondition_failed(self, client, assertions):
        """Test conditional create with multiple matches returns 412."""
        family_name = f"ConditionalMulti-{FHIRResourceGenerator.generate_id()}"

        patient1 = FHIRResourceGenerator.generate_patient(
            name=[{"family": family_name}]
        )
        patient2 = FHIRResourceGenerator.generate_patient(
            name=[{"family": family_name}]
        )

        id1 = None
        id2 = None
        try:
            # Create two patients with same family name
            resp1 = client.create(patient1)
            id1 = resp1.json()['id']

            resp2 = client.create(patient2)
            id2 = resp2.json()['id']

            # Try conditional create with family name that matches both
            patient3 = FHIRResourceGenerator.generate_patient(
                name=[{"family": family_name}]
            )
            response = client.conditional_create(
                patient3,
                {"family": family_name}
            )

            # Should return 412 Precondition Failed for multiple matches
            assert response.status_code == 412, \
                f"Multiple matches should return 412, got {response.status_code}"

        finally:
            if id1:
                client.delete("Patient", id1)
            if id2:
                client.delete("Patient", id2)

    def test_conditional_create_with_multiple_search_parameters(self, client, assertions):
        """Test conditional create with multiple search criteria."""
        identifier_value = f"COND-MULTI-{FHIRResourceGenerator.generate_id()}"
        family_name = f"MultiParam-{FHIRResourceGenerator.generate_id()}"

        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": family_name}],
            identifier=[{"value": identifier_value}]
        )

        created_id = None
        try:
            # First request with multiple search params
            response1 = client.conditional_create(
                patient,
                {
                    "identifier": identifier_value,
                    "family": family_name
                }
            )
            assert response1.status_code == 201
            created_id = response1.json()['id']

            # Second request with same params should find it
            response2 = client.conditional_create(
                patient,
                {
                    "identifier": identifier_value,
                    "family": family_name
                }
            )
            assert response2.status_code == 200
            assert response2.json()['id'] == created_id

        finally:
            if created_id:
                client.delete("Patient", created_id)
