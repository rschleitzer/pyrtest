"""Tests for FHIR Observation resource CRUD operations."""
import pyrtest
import sys
import os

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


@pyrtest.fixture
def test_patient(client, assertions):
    """Create a test patient for observations."""
    patient = FHIRResourceGenerator.generate_patient()
    resp = client.create(patient)
    created = assertions.assert_created(resp, "Patient")

    yield created

    try:
        client.delete("Patient", created['id'])
    except:
        pass


class TestObservationCreate:
    """Test Observation resource creation."""

    def test_create_observation_with_quantity(self, client, assertions, test_patient):
        """Test creating observation with quantity value."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="8867-4",
            code_display="Heart rate",
            value_quantity={
                "value": 72,
                "unit": "beats/minute",
                "system": "http://unitsofmeasure.org",
                "code": "/min"
            }
        )

        response = client.create(observation)
        created = assertions.assert_created(response, "Observation")

        try:
            assert created['status'] in ['final', 'preliminary', 'registered'], \
                "Observation should have valid status"
            assert created['subject']['reference'] == f"Patient/{test_patient['id']}"
            assert created['code']['coding'][0]['code'] == "8867-4"
            assert created['valueQuantity']['value'] == 72
        finally:
            client.delete("Observation", created['id'])

    def test_create_observation_with_codeable_concept(self, client, assertions, test_patient):
        """Test creating observation with CodeableConcept value."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="32451-7",
            code_display="Physical findings",
            value_codeable_concept={
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "271594007",
                    "display": "Normal"
                }]
            }
        )

        response = client.create(observation)
        created = assertions.assert_created(response, "Observation")

        try:
            assert 'valueCodeableConcept' in created
            assert created['valueCodeableConcept']['coding'][0]['code'] == "271594007"
        finally:
            client.delete("Observation", created['id'])

    def test_create_observation_with_string_value(self, client, assertions, test_patient):
        """Test creating observation with string value."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="11543-6",
            code_display="Notes",
            value_string="Patient appears healthy"
        )

        response = client.create(observation)
        created = assertions.assert_created(response, "Observation")

        try:
            assert 'valueString' in created
            assert created['valueString'] == "Patient appears healthy"
        finally:
            client.delete("Observation", created['id'])

    def test_create_observation_with_components(self, client, assertions, test_patient):
        """Test creating observation with components (e.g., blood pressure)."""
        observation = {
            "resourceType": "Observation",
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "vital-signs",
                    "display": "Vital Signs"
                }]
            }],
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "85354-9",
                    "display": "Blood pressure panel"
                }]
            },
            "subject": FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            "component": [
                {
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "8480-6",
                            "display": "Systolic blood pressure"
                        }]
                    },
                    "valueQuantity": {
                        "value": 120,
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]"
                    }
                },
                {
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "8462-4",
                            "display": "Diastolic blood pressure"
                        }]
                    },
                    "valueQuantity": {
                        "value": 80,
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]"
                    }
                }
            ]
        }

        response = client.create(observation)
        created = assertions.assert_created(response, "Observation")

        try:
            assert 'component' in created
            assert len(created['component']) == 2

            # Verify systolic
            systolic = next(c for c in created['component']
                          if c['code']['coding'][0]['code'] == '8480-6')
            assert systolic['valueQuantity']['value'] == 120

            # Verify diastolic
            diastolic = next(c for c in created['component']
                           if c['code']['coding'][0]['code'] == '8462-4')
            assert diastolic['valueQuantity']['value'] == 80
        finally:
            client.delete("Observation", created['id'])

    def test_create_observation_with_category(self, client, assertions, test_patient):
        """Test creating observation with category."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="2339-0",
            code_display="Glucose",
            value_quantity={
                "value": 95,
                "unit": "mg/dL",
                "system": "http://unitsofmeasure.org",
                "code": "mg/dL"
            },
            category=[{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "laboratory",
                    "display": "Laboratory"
                }]
            }]
        )

        response = client.create(observation)
        created = assertions.assert_created(response, "Observation")

        try:
            assert 'category' in created
            assert created['category'][0]['coding'][0]['code'] == "laboratory"
        finally:
            client.delete("Observation", created['id'])


class TestObservationRead:
    """Test Observation resource reading."""

    def test_read_observation(self, client, assertions, test_patient):
        """Test reading an observation by ID."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="8867-4",
            code_display="Heart rate",
            value_quantity={"value": 75, "unit": "bpm"}
        )

        resp = client.create(observation)
        created = assertions.assert_created(resp, "Observation")

        try:
            response = client.read("Observation", created['id'])
            read_obs = assertions.assert_read_success(response, "Observation")

            assert read_obs['id'] == created['id']
            assert read_obs['valueQuantity']['value'] == 75
        finally:
            client.delete("Observation", created['id'])

    def test_read_nonexistent_observation(self, client, assertions):
        """Test reading a nonexistent observation returns 404."""
        response = client.read("Observation", "nonexistent-obs-id")
        assertions.assert_not_found(response)


class TestObservationUpdate:
    """Test Observation resource updates."""

    def test_update_observation_value(self, client, assertions, test_patient):
        """Test updating an observation's value."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="8867-4",
            code_display="Heart rate",
            value_quantity={"value": 72, "unit": "bpm"}
        )

        resp = client.create(observation)
        created = assertions.assert_created(resp, "Observation")

        try:
            # Update the value
            created['valueQuantity']['value'] = 78

            update_resp = client.update(created)
            updated = assertions.assert_updated(update_resp, "Observation")

            assert updated['valueQuantity']['value'] == 78
            assert int(updated['meta']['versionId']) > int(created['meta']['versionId'])
        finally:
            client.delete("Observation", created['id'])

    def test_update_observation_status(self, client, assertions, test_patient):
        """Test updating observation status."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="8867-4",
            code_display="Heart rate",
            value_quantity={"value": 72, "unit": "bpm"}
        )
        observation['status'] = 'preliminary'

        resp = client.create(observation)
        created = assertions.assert_created(resp, "Observation")

        try:
            created['status'] = 'final'

            update_resp = client.update(created)
            updated = assertions.assert_updated(update_resp, "Observation")

            assert updated['status'] == 'final'
        finally:
            client.delete("Observation", created['id'])

    def test_update_nonexistent_observation_creates(self, client, assertions, test_patient):
        """Test updating nonexistent observation creates it (update-as-create)."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="8867-4",
            code_display="Heart rate",
            value_quantity={"value": 72, "unit": "bpm"}
        )
        observation['id'] = 'update-as-create-obs-test'

        try:
            response = client.update(observation)
            created = assertions.assert_created(response, "Observation")

            assert created['id'] == 'update-as-create-obs-test'
            assert created['valueQuantity']['value'] == 72
        finally:
            client.delete("Observation", 'update-as-create-obs-test')


class TestObservationDelete:
    """Test Observation resource deletion."""

    def test_delete_observation(self, client, assertions, test_patient):
        """Test deleting an observation."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="8867-4",
            code_display="Heart rate",
            value_quantity={"value": 72, "unit": "bpm"}
        )

        resp = client.create(observation)
        created = assertions.assert_created(resp, "Observation")

        # Delete the observation
        delete_resp = client.delete("Observation", created['id'])
        assertions.assert_deleted(delete_resp)

        # Verify it's gone
        read_resp = client.read("Observation", created['id'])
        assertions.assert_not_found(read_resp)

    def test_delete_nonexistent_observation(self, client, assertions):
        """Test deleting nonexistent observation returns appropriate status."""
        response = client.delete("Observation", "nonexistent-obs-id")
        # Should return 404 or 204 depending on server implementation
        assert response.status_code in [204, 404]


class TestObservationSearch:
    """Test Observation resource searching."""

    @pyrtest.fixture
    def test_observations(self, client, assertions, test_patient):
        """Create multiple test observations."""
        observations = []

        # Heart rate observation
        obs1 = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="8867-4",
            code_display="Heart rate",
            value_quantity={"value": 72, "unit": "bpm"}
        )
        resp = client.create(obs1)
        observations.append(assertions.assert_created(resp, "Observation"))

        # Glucose observation
        obs2 = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="2339-0",
            code_display="Glucose",
            value_quantity={"value": 95, "unit": "mg/dL"}
        )
        resp = client.create(obs2)
        observations.append(assertions.assert_created(resp, "Observation"))

        yield observations

        # Cleanup
        for obs in observations:
            try:
                client.delete("Observation", obs['id'])
            except:
                pass

    def test_search_by_patient(self, client, assertions, test_patient, test_observations):
        """Test searching observations by patient."""
        response = client.search("Observation", {
            "patient": test_patient['id']
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle['total'] >= 2

        # All results should be for this patient
        for entry in bundle.get('entry', []):
            obs = entry['resource']
            assert test_patient['id'] in obs['subject']['reference']

    def test_search_by_code(self, client, assertions, test_observations):
        """Test searching observations by code."""
        response = client.search("Observation", {
            "code": "http://loinc.org|8867-4"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle['total'] >= 1

        # All results should have the heart rate code
        for entry in bundle.get('entry', []):
            obs = entry['resource']
            codes = [coding['code'] for coding in obs['code']['coding']]
            assert '8867-4' in codes

    def test_search_by_category(self, client, assertions, test_patient):
        """Test searching observations by category."""
        # Create observation with specific category
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="2339-0",
            code_display="Glucose",
            value_quantity={"value": 95, "unit": "mg/dL"},
            category=[{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "laboratory",
                    "display": "Laboratory"
                }]
            }]
        )

        resp = client.create(observation)
        created = assertions.assert_created(resp, "Observation")

        try:
            response = client.search("Observation", {
                "category": "laboratory"
            })

            bundle = assertions.assert_bundle(response, "Observation")

            # Should find at least our observation
            found = False
            for entry in bundle.get('entry', []):
                if entry['resource']['id'] == created['id']:
                    found = True
                    break
            assert found, "Should find the laboratory observation"
        finally:
            client.delete("Observation", created['id'])

    def test_search_by_status(self, client, assertions, test_patient):
        """Test searching observations by status."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="8867-4",
            code_display="Heart rate",
            value_quantity={"value": 72, "unit": "bpm"}
        )
        observation['status'] = 'final'

        resp = client.create(observation)
        created = assertions.assert_created(resp, "Observation")

        try:
            response = client.search("Observation", {
                "status": "final"
            })

            bundle = assertions.assert_bundle(response, "Observation")

            # All results should have final status
            for entry in bundle.get('entry', []):
                obs = entry['resource']
                assert obs['status'] == 'final'
        finally:
            client.delete("Observation", created['id'])


class TestObservationValidation:
    """Test Observation resource validation."""

    def test_create_observation_requires_status(self, client, assertions, test_patient):
        """Test that observation requires status field."""
        observation = {
            "resourceType": "Observation",
            # Missing status field
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "8867-4",
                    "display": "Heart rate"
                }]
            },
            "subject": FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            )
        }

        response = client.create(observation)
        # Should return 400 Bad Request for missing required field
        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for missing status, got {response.status_code}"

    def test_create_observation_requires_code(self, client, assertions, test_patient):
        """Test that observation requires code field."""
        observation = {
            "resourceType": "Observation",
            "status": "final",
            # Missing code field
            "subject": FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            )
        }

        response = client.create(observation)
        # Should return 400 Bad Request for missing required field
        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for missing code, got {response.status_code}"

    def test_create_observation_invalid_status(self, client, assertions, test_patient):
        """Test that observation rejects invalid status values."""
        observation = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", test_patient['id']
            ),
            code_system="http://loinc.org",
            code="8867-4",
            code_display="Heart rate",
            value_quantity={"value": 72, "unit": "bpm"}
        )
        observation['status'] = 'invalid-status'

        response = client.create(observation)
        # Should return 400 Bad Request for invalid enum value
        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for invalid status, got {response.status_code}"
