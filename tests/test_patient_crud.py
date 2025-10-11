"""Test suite for Patient CRUD operations."""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.fhir_client import FHIRClient
from utils.assertions import FHIRAssertions
from fixtures.resource_generators import FHIRResourceGenerator


@pytest.fixture
def client():
    """Create FHIR client for tests."""
    return FHIRClient()


@pytest.fixture
def assertions():
    """Create assertions helper."""
    return FHIRAssertions()


class TestPatientCreate:
    """Test Patient creation (POST)."""

    def test_create_valid_patient(self, client, assertions):
        """Test creating a valid Patient returns 201 with Location header."""
        patient = FHIRResourceGenerator.generate_patient()

        response = client.create(patient)

        created = assertions.assert_created(response, "Patient")
        assert created['resourceType'] == 'Patient'
        assert 'id' in created, "Created patient should have an id"
        assert 'meta' in created, "Created patient should have meta"

        # Verify Location header format
        location = response.headers['Location']
        assert 'Patient/' in location
        assert created['id'] in location

    def test_create_patient_with_identifier(self, client, assertions):
        """Test creating Patient with specific identifier."""
        identifier_value = "TEST-12345"
        patient = FHIRResourceGenerator.generate_patient(
            identifier=[{"system": "http://hospital.org/mrn", "value": identifier_value}]
        )

        response = client.create(patient)
        created = assertions.assert_created(response, "Patient")

        assert created['identifier'][0]['value'] == identifier_value

    def test_create_patient_minimal(self, client, assertions):
        """Test creating Patient with minimal required fields."""
        patient = {
            "resourceType": "Patient"
        }

        response = client.create(patient)

        # Should succeed - Patient has no required fields in FHIR R5
        created = assertions.assert_created(response, "Patient")
        assert created['resourceType'] == 'Patient'

    def test_create_invalid_patient_missing_resource_type(self, client, assertions):
        """Test creating Patient without resourceType returns 400."""
        invalid_patient = {
            "name": [{"family": "Smith"}]
        }

        response = client.session.post(
            client._url("Patient"),
            json=invalid_patient
        )

        assertions.assert_bad_request(response)

    def test_create_invalid_patient_wrong_data_type(self, client, assertions):
        """Test creating Patient with wrong data type returns 400."""
        invalid_patient = FHIRResourceGenerator.generate_invalid_patient("invalid_type")

        response = client.create(invalid_patient)

        assertions.assert_bad_request(response)

    def test_conditional_create_no_match(self, client, assertions):
        """Test conditional create when no match exists creates new resource."""
        patient = FHIRResourceGenerator.generate_patient()
        search_params = {"identifier": "http://hospital.org/mrn|UNIQUE-99999"}

        response = client.conditional_create(patient, search_params)

        assertions.assert_created(response, "Patient")

    def test_conditional_create_with_match(self, client, assertions):
        """Test conditional create when match exists returns existing resource."""
        # First create a patient
        identifier_value = f"TEST-COND-{FHIRResourceGenerator.generate_id()}"
        patient1 = FHIRResourceGenerator.generate_patient(
            identifier=[{"system": "http://hospital.org/mrn", "value": identifier_value}]
        )
        response1 = client.create(patient1)
        created1 = assertions.assert_created(response1, "Patient")

        # Try conditional create with same identifier
        patient2 = FHIRResourceGenerator.generate_patient(
            identifier=[{"system": "http://hospital.org/mrn", "value": identifier_value}]
        )
        search_params = {"identifier": f"http://hospital.org/mrn|{identifier_value}"}

        response2 = client.conditional_create(patient2, search_params)

        # Should return 200 (found existing) not 201 (created new)
        assert response2.status_code == 200, \
            f"Conditional create with match should return 200, got {response2.status_code}"
        returned = response2.json()
        assert returned['id'] == created1['id'], "Should return existing patient"


class TestPatientRead:
    """Test Patient read operations (GET)."""

    def test_read_existing_patient(self, client, assertions):
        """Test reading an existing Patient returns 200."""
        # Create a patient first
        patient = FHIRResourceGenerator.generate_patient()
        create_response = client.create(patient)
        created = assertions.assert_created(create_response, "Patient")

        # Read it back
        read_response = client.read("Patient", created['id'])

        read_patient = assertions.assert_read_success(read_response, "Patient")
        assert read_patient['id'] == created['id']
        assert read_patient['resourceType'] == 'Patient'

    def test_read_nonexistent_patient(self, client, assertions):
        """Test reading non-existent Patient returns 404."""
        fake_id = FHIRResourceGenerator.generate_id()

        response = client.read("Patient", fake_id)

        assertions.assert_not_found(response)

    def test_read_returns_meta(self, client, assertions):
        """Test read response includes meta with versionId and lastUpdated."""
        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        create_response = client.create(patient)
        created = assertions.assert_created(create_response, "Patient")

        # Read it
        read_response = client.read("Patient", created['id'])
        read_patient = assertions.assert_read_success(read_response, "Patient")

        assertions.assert_resource_has_field(read_patient, 'meta.versionId')
        assertions.assert_resource_has_field(read_patient, 'meta.lastUpdated')


class TestPatientUpdate:
    """Test Patient update operations (PUT)."""

    def test_update_existing_patient(self, client, assertions):
        """Test updating an existing Patient returns 200."""
        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        create_response = client.create(patient)
        created = assertions.assert_created(create_response, "Patient")

        # Update it
        created['active'] = False
        created['name'][0]['family'] = 'UpdatedName'

        update_response = client.update(created)

        updated = assertions.assert_updated(update_response, "Patient")
        assert updated['id'] == created['id']
        assert updated['active'] == False
        assert updated['name'][0]['family'] == 'UpdatedName'

    def test_update_increments_version(self, client, assertions):
        """Test update increments the resource version."""
        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        create_response = client.create(patient)
        created = assertions.assert_created(create_response, "Patient")
        version1 = created['meta']['versionId']

        # Update it
        created['active'] = False
        update_response = client.update(created)
        updated = assertions.assert_updated(update_response, "Patient")
        version2 = updated['meta']['versionId']

        assert version2 != version1, "Version should change after update"

    def test_update_with_if_match(self, client, assertions):
        """Test conditional update with If-Match header."""
        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        create_response = client.create(patient)
        created = assertions.assert_created(create_response, "Patient")

        # Update with correct version
        created['active'] = False
        etag = f'W/"{created["meta"]["versionId"]}"'
        update_response = client.update(created, if_match=etag)

        assertions.assert_updated(update_response, "Patient")

    def test_update_with_wrong_if_match(self, client, assertions):
        """Test conditional update with wrong If-Match fails."""
        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        create_response = client.create(patient)
        created = assertions.assert_created(create_response, "Patient")

        # Update with wrong version
        created['active'] = False
        wrong_etag = 'W/"999"'
        update_response = client.update(created, if_match=wrong_etag)

        # Should fail with conflict
        assertions.assert_conflict(update_response)

    def test_update_nonexistent_patient(self, client, assertions):
        """Test updating non-existent Patient behavior."""
        fake_id = FHIRResourceGenerator.generate_id()
        patient = FHIRResourceGenerator.generate_patient(id=fake_id)

        response = client.update(patient)

        # Server may return 404 or create new (201) - both are valid FHIR behaviors
        assert response.status_code in [201, 404], \
            f"Update of non-existent should return 201 or 404, got {response.status_code}"


class TestPatientDelete:
    """Test Patient delete operations (DELETE)."""

    def test_delete_existing_patient(self, client, assertions):
        """Test deleting an existing Patient returns 200/204."""
        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        create_response = client.create(patient)
        created = assertions.assert_created(create_response, "Patient")

        # Delete it
        delete_response = client.delete("Patient", created['id'])
        assertions.assert_deleted(delete_response)

        # Verify it's gone
        read_response = client.read("Patient", created['id'])
        assertions.assert_not_found(read_response)

    def test_delete_nonexistent_patient(self, client, assertions):
        """Test deleting non-existent Patient returns 404."""
        fake_id = FHIRResourceGenerator.generate_id()

        response = client.delete("Patient", fake_id)

        assertions.assert_not_found(response)

    def test_delete_twice(self, client, assertions):
        """Test deleting same Patient twice returns 404 on second delete."""
        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        create_response = client.create(patient)
        created = assertions.assert_created(create_response, "Patient")

        # First delete
        delete_response1 = client.delete("Patient", created['id'])
        assertions.assert_deleted(delete_response1)

        # Second delete should fail
        delete_response2 = client.delete("Patient", created['id'])
        assertions.assert_not_found(delete_response2)


class TestPatientWorkflow:
    """End-to-end Patient workflow tests."""

    def test_complete_patient_lifecycle(self, client, assertions):
        """Test complete CRUD lifecycle for Patient."""
        # 1. Create
        patient = FHIRResourceGenerator.generate_patient()
        create_resp = client.create(patient)
        created = assertions.assert_created(create_resp, "Patient")
        patient_id = created['id']

        # 2. Read
        read_resp = client.read("Patient", patient_id)
        read_patient = assertions.assert_read_success(read_resp, "Patient")
        assert read_patient['id'] == patient_id

        # 3. Update
        read_patient['active'] = False
        update_resp = client.update(read_patient)
        updated = assertions.assert_updated(update_resp, "Patient")
        assert updated['active'] == False

        # 4. Read again to verify update
        read_resp2 = client.read("Patient", patient_id)
        read_patient2 = assertions.assert_read_success(read_resp2, "Patient")
        assert read_patient2['active'] == False

        # 5. Delete
        delete_resp = client.delete("Patient", patient_id)
        assertions.assert_deleted(delete_resp)

        # 6. Verify deletion
        read_resp3 = client.read("Patient", patient_id)
        assertions.assert_not_found(read_resp3)
