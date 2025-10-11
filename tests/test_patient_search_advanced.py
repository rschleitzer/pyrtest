"""Advanced search parameter tests for FHIR Patient resource."""
import pytest
import sys
import os

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


class TestReferenceSearch:
    """Test reference parameter searches."""

    @pytest.fixture
    def test_data(self, client, assertions):
        """Create test data with references."""
        data = {'practitioners': [], 'patients': []}

        # Create practitioner
        prac = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "RefTest", "given": ["Doctor"]}]
        )
        resp = client.create(prac)
        created_prac = assertions.assert_created(resp, "Practitioner")
        data['practitioners'].append(created_prac)

        # Create patient with reference to practitioner
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "RefPatient", "given": ["Test"]}],
            generalPractitioner=[
                FHIRResourceGenerator.generate_reference(
                    "Practitioner",
                    created_prac['id'],
                    "Dr. RefTest"
                )
            ]
        )
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")
        data['patients'].append(created_patient)

        yield data

        # Cleanup
        for patient in data['patients']:
            try:
                client.delete("Patient", patient['id'])
            except:
                pass
        for prac in data['practitioners']:
            try:
                client.delete("Practitioner", prac['id'])
            except:
                pass

    def test_reference_by_id(self, client, assertions, test_data):
        """Test searching by reference ID."""
        prac_id = test_data['practitioners'][0]['id']
        response = client.search("Patient", {
            "general-practitioner": f"Practitioner/{prac_id}"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify the patient has the correct reference
        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            gps = patient.get('generalPractitioner', [])
            for gp in gps:
                if prac_id in gp.get('reference', ''):
                    found = True
        assert found, "Should find patient with the specific GP reference"

    def test_reference_by_resource_id_only(self, client, assertions, test_data):
        """Test searching by resource ID without type prefix."""
        prac_id = test_data['practitioners'][0]['id']
        response = client.search("Patient", {
            "general-practitioner": prac_id
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find the patient (server should be lenient)

    def test_reference_missing_modifier(self, client, assertions):
        """Test :missing modifier on reference."""
        # Find patients without a general practitioner
        response = client.search("Patient", {
            "general-practitioner:missing": "true"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # All results should not have generalPractitioner
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            assert 'generalPractitioner' not in patient or \
                   len(patient.get('generalPractitioner', [])) == 0


class TestAdvancedModifiers:
    """Test advanced search parameter modifiers."""

    @pytest.fixture
    def test_patients(self, client, assertions):
        """Create test patients."""
        patients = []

        # Patient with specific identifier
        p1 = FHIRResourceGenerator.generate_patient(
            name=[{"family": "ModTest1"}],
            identifier=[{"system": "http://hospital.org/mrn", "value": "MOD-001"}],
            active=True
        )
        resp = client.create(p1)
        patients.append(assertions.assert_created(resp, "Patient"))

        # Patient without identifier
        p2 = FHIRResourceGenerator.generate_patient(
            name=[{"family": "ModTest2"}],
            active=False
        )
        resp = client.create(p2)
        patients.append(assertions.assert_created(resp, "Patient"))

        yield patients

        # Cleanup
        for patient in patients:
            try:
                client.delete("Patient", patient['id'])
            except:
                pass

    def test_not_modifier_on_token(self, client, assertions, test_patients):
        """Test :not modifier to exclude values."""
        # Find patients where active is NOT true
        response = client.search("Patient", {
            "active:not": "true"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Results should not have active=true
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            if 'active' in patient:
                assert patient['active'] != True, "Should not return patients with active=true"

    def test_not_modifier_on_string(self, client, assertions, test_patients):
        """Test :not modifier on string parameters."""
        # Find patients whose family name is NOT "ModTest1"
        response = client.search("Patient", {
            "family:not": "ModTest1"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Verify ModTest1 is not in results
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            names = patient.get('name', [])
            for name in names:
                assert name.get('family') != 'ModTest1', "Should not return ModTest1"

    def test_missing_modifier_true(self, client, assertions, test_patients):
        """Test :missing=true to find resources without a field."""
        # Find patients without an identifier
        response = client.search("Patient", {
            "identifier:missing": "true"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Results should not have identifier
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            assert 'identifier' not in patient or len(patient.get('identifier', [])) == 0

    def test_missing_modifier_false(self, client, assertions, test_patients):
        """Test :missing=false to find resources with a field."""
        # Find patients with an identifier
        response = client.search("Patient", {
            "identifier:missing": "false"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Results should have identifier
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            assert 'identifier' in patient and len(patient.get('identifier', [])) > 0


class TestTextSearch:
    """Test text and content search parameters."""

    def test_text_search_parameter(self, client, assertions):
        """Test _text parameter for narrative text search."""
        # Search for patients with specific text in narrative
        response = client.search("Patient", {
            "_text": "patient"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Server may or may not support _text
        # Just verify we get a valid bundle response

    def test_content_search_parameter(self, client, assertions):
        """Test _content parameter for full resource content search."""
        # Search for patients with specific text anywhere in resource
        response = client.search("Patient", {
            "_content": "Smith"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Server may or may not support _content
        # Just verify we get a valid bundle response

    def test_filter_parameter(self, client, assertions):
        """Test _filter parameter for advanced filtering."""
        # Use FHIR's advanced filter syntax
        response = client.search("Patient", {
            "_filter": "family eq 'Smith'"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Server may or may not support _filter
        # Just verify we get a valid bundle response


class TestCompositeSearch:
    """Test composite search parameters."""

    @pytest.fixture
    def test_observations(self, client, assertions):
        """Create test observations with various values."""
        observations = []

        # Create a patient first
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")

        # Observation 1: High blood pressure
        obs1 = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", created_patient['id']
            ),
            code_system="http://loinc.org",
            code="8480-6",
            code_display="Systolic blood pressure",
            value_quantity={
                "value": 180,
                "unit": "mmHg",
                "system": "http://unitsofmeasure.org",
                "code": "mm[Hg]"
            }
        )
        resp = client.create(obs1)
        observations.append(assertions.assert_created(resp, "Observation"))

        # Observation 2: Normal blood pressure
        obs2 = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient", created_patient['id']
            ),
            code_system="http://loinc.org",
            code="8480-6",
            code_display="Systolic blood pressure",
            value_quantity={
                "value": 120,
                "unit": "mmHg",
                "system": "http://unitsofmeasure.org",
                "code": "mm[Hg]"
            }
        )
        resp = client.create(obs2)
        observations.append(assertions.assert_created(resp, "Observation"))

        yield {'observations': observations, 'patient': created_patient}

        # Cleanup
        for obs in observations:
            try:
                client.delete("Observation", obs['id'])
            except:
                pass
        try:
            client.delete("Patient", created_patient['id'])
        except:
            pass

    def test_composite_code_value_quantity(self, client, assertions, test_observations):
        """Test composite search on code and value-quantity."""
        # Find blood pressure observations with value > 150
        response = client.search("Observation", {
            "code-value-quantity": "http://loinc.org|8480-6$gt150"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find the high BP observation
        # Server may or may not support composite parameters


class TestQuantitySearch:
    """Test quantity parameter searches."""

    @pytest.fixture
    def test_observations(self, client, assertions):
        """Create observations with various quantity values."""
        observations = []
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")

        # Create observations with different values
        values = [
            (60, "Heart rate low"),
            (75, "Heart rate normal"),
            (120, "Heart rate high")
        ]

        for value, display in values:
            obs = FHIRResourceGenerator.generate_observation(
                patient_ref=FHIRResourceGenerator.generate_reference(
                    "Patient", created_patient['id']
                ),
                code_system="http://loinc.org",
                code="8867-4",
                code_display=display,
                value_quantity={
                    "value": value,
                    "unit": "beats/minute",
                    "system": "http://unitsofmeasure.org",
                    "code": "/min"
                }
            )
            resp = client.create(obs)
            observations.append(assertions.assert_created(resp, "Observation"))

        yield {'observations': observations, 'patient': created_patient}

        # Cleanup
        for obs in observations:
            try:
                client.delete("Observation", obs['id'])
            except:
                pass
        try:
            client.delete("Patient", created_patient['id'])
        except:
            pass

    def test_quantity_exact_match(self, client, assertions, test_observations):
        """Test exact quantity match."""
        response = client.search("Observation", {
            "value-quantity": "75"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observation with value 75

    def test_quantity_greater_than(self, client, assertions, test_observations):
        """Test quantity with gt (greater than) prefix."""
        response = client.search("Observation", {
            "value-quantity": "gt100"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observation with value 120

    def test_quantity_less_than(self, client, assertions, test_observations):
        """Test quantity with lt (less than) prefix."""
        response = client.search("Observation", {
            "value-quantity": "lt70"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observation with value 60

    def test_quantity_with_system_and_code(self, client, assertions, test_observations):
        """Test quantity with system and code specified."""
        response = client.search("Observation", {
            "value-quantity": "75|http://unitsofmeasure.org|/min"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observation with matching value, system, and code

    def test_quantity_approximate(self, client, assertions, test_observations):
        """Test quantity with ap (approximate) prefix."""
        response = client.search("Observation", {
            "value-quantity": "ap75"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observations with values approximately 75 (within 10%)

    def test_quantity_range(self, client, assertions, test_observations):
        """Test quantity range using multiple parameters."""
        response = client.search("Observation", {
            "value-quantity": ["ge70", "le80"]
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observation with value 75


class TestURISearch:
    """Test URI parameter searches."""

    def test_uri_exact_match(self, client, assertions):
        """Test URI parameter exact match."""
        # This would typically be used with ValueSet or StructureDefinition
        # Using identifier system as a URI-like parameter
        response = client.search("Patient", {
            "identifier": "http://hospital.org/mrn|TEST-URI"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should handle URI in system component

    def test_uri_below_modifier(self, client, assertions):
        """Test :below modifier for hierarchical URIs."""
        # Find all identifiers under a namespace
        response = client.search("Patient", {
            "identifier:below": "http://hospital.org/"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find identifiers with systems starting with http://hospital.org/

    def test_uri_above_modifier(self, client, assertions):
        """Test :above modifier for hierarchical URIs."""
        # Find identifiers that are ancestors of the specified URI
        response = client.search("Patient", {
            "identifier:above": "http://hospital.org/mrn/department"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find identifiers with parent URIs
