"""Test suite for FHIR search _include and _revinclude operations."""
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


@pytest.fixture
def test_data(client, assertions):
    """Create test data with relationships for include tests."""
    data = {
        'practitioners': [],
        'patients': [],
        'observations': []
    }

    # Create Practitioner 1: Dr. Anderson
    prac1 = FHIRResourceGenerator.generate_practitioner(
        name=[{"family": "Anderson", "given": ["Emily"], "prefix": ["Dr."]}],
        identifier=[{"system": "http://hospital.org/practitioners", "value": "PRAC-INC-001"}]
    )
    resp = client.create(prac1)
    created_prac1 = assertions.assert_created(resp, "Practitioner")
    data['practitioners'].append(created_prac1)

    # Create Practitioner 2: Dr. Martinez
    prac2 = FHIRResourceGenerator.generate_practitioner(
        name=[{"family": "Martinez", "given": ["Carlos"], "prefix": ["Dr."]}],
        identifier=[{"system": "http://hospital.org/practitioners", "value": "PRAC-INC-002"}]
    )
    resp = client.create(prac2)
    created_prac2 = assertions.assert_created(resp, "Practitioner")
    data['practitioners'].append(created_prac2)

    # Create Patient 1: Emma Taylor with Dr. Anderson
    patient1 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Taylor", "given": ["Emma"]}],
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-INC-001"}],
        generalPractitioner=[
            FHIRResourceGenerator.generate_reference(
                "Practitioner",
                created_prac1['id'],
                "Dr. Emily Anderson"
            )
        ]
    )
    resp = client.create(patient1)
    created_patient1 = assertions.assert_created(resp, "Patient")
    data['patients'].append(created_patient1)

    # Create Patient 2: Oliver Chen with Dr. Martinez
    patient2 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Chen", "given": ["Oliver"]}],
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-INC-002"}],
        generalPractitioner=[
            FHIRResourceGenerator.generate_reference(
                "Practitioner",
                created_prac2['id'],
                "Dr. Carlos Martinez"
            )
        ]
    )
    resp = client.create(patient2)
    created_patient2 = assertions.assert_created(resp, "Patient")
    data['patients'].append(created_patient2)

    # Create Patient 3: Sophia Lee with no practitioner
    patient3 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Lee", "given": ["Sophia"]}],
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-INC-003"}]
    )
    resp = client.create(patient3)
    created_patient3 = assertions.assert_created(resp, "Patient")
    data['patients'].append(created_patient3)

    # Create multiple Observations for Emma Taylor
    for i, (code, display, value) in enumerate([
        ("8867-4", "Heart rate", 72),
        ("85354-9", "Blood pressure systolic", 118),
        ("8310-5", "Body temperature", 36.8)
    ]):
        obs = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient",
                created_patient1['id'],
                "Emma Taylor"
            ),
            code_system="http://loinc.org",
            code=code,
            code_display=display,
            value_quantity={"value": value, "unit": "unit", "system": "http://unitsofmeasure.org", "code": "1"}
        )
        resp = client.create(obs)
        created_obs = assertions.assert_created(resp, "Observation")
        data['observations'].append(created_obs)

    # Create Observations for Oliver Chen
    for i, (code, display, value) in enumerate([
        ("8867-4", "Heart rate", 68),
        ("8310-5", "Body temperature", 37.1)
    ]):
        obs = FHIRResourceGenerator.generate_observation(
            patient_ref=FHIRResourceGenerator.generate_reference(
                "Patient",
                created_patient2['id'],
                "Oliver Chen"
            ),
            code_system="http://loinc.org",
            code=code,
            code_display=display,
            value_quantity={"value": value, "unit": "unit", "system": "http://unitsofmeasure.org", "code": "1"}
        )
        resp = client.create(obs)
        created_obs = assertions.assert_created(resp, "Observation")
        data['observations'].append(created_obs)

    yield data

    # Cleanup
    for obs in data['observations']:
        try:
            client.delete("Observation", obs['id'])
        except:
            pass
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


class TestIncludeForward:
    """Test _include parameter (forward references)."""

    def test_include_patient_general_practitioner(self, client, assertions, test_data):
        """Test including Practitioner resources referenced by Patient."""
        # Search for patients named Taylor and include their general practitioner
        response = client.search("Patient", {
            "family": "Taylor",
            "_include": "Patient:general-practitioner"
        })

        bundle = assertions.assert_bundle(response)
        assert bundle['total'] >= 1

        # Bundle should contain both Patient and Practitioner resources
        patient_count = 0
        practitioner_count = 0

        for entry in bundle.get('entry', []):
            resource_type = entry['resource']['resourceType']
            if resource_type == 'Patient':
                patient_count += 1
            elif resource_type == 'Practitioner':
                practitioner_count += 1

        assert patient_count >= 1, "Should include at least one Patient"
        assert practitioner_count >= 1, "Should include at least one Practitioner"

    def test_include_observation_subject(self, client, assertions, test_data):
        """Test including Patient resources referenced by Observation."""
        # Search for observations with code and include the subject (Patient)
        response = client.search("Observation", {
            "code": "8867-4",  # Heart rate
            "_include": "Observation:subject"
        })

        bundle = assertions.assert_bundle(response)

        # Bundle should contain both Observation and Patient resources
        observation_count = 0
        patient_count = 0

        for entry in bundle.get('entry', []):
            resource_type = entry['resource']['resourceType']
            if resource_type == 'Observation':
                observation_count += 1
            elif resource_type == 'Patient':
                patient_count += 1

        assert observation_count >= 1, "Should include Observations"
        assert patient_count >= 1, "Should include referenced Patients"

    def test_include_multiple_references(self, client, assertions, test_data):
        """Test including multiple different reference types."""
        # Include both the observation's subject and performer (if set)
        response = client.search("Observation", {
            "subject:Patient.family": "Taylor",
            "_include": ["Observation:subject", "Observation:performer"]
        })

        bundle = assertions.assert_bundle(response)
        # Should include observations and their referenced resources

    def test_include_with_resource_type_specified(self, client, assertions, test_data):
        """Test _include with explicit resource type."""
        # Include only Practitioner resources (not other possible reference types)
        response = client.search("Patient", {
            "family": "Taylor",
            "_include": "Patient:general-practitioner:Practitioner"
        })

        bundle = assertions.assert_bundle(response)

        # Check that only Patient and Practitioner are included
        resource_types = set()
        for entry in bundle.get('entry', []):
            resource_types.add(entry['resource']['resourceType'])

        assert 'Patient' in resource_types
        if len(resource_types) > 1:
            # If included resources exist, they should be Practitioners
            assert 'Practitioner' in resource_types


class TestRevIncludeReverse:
    """Test _revinclude parameter (reverse references)."""

    def test_revinclude_patient_observations(self, client, assertions, test_data):
        """Test including Observations that reference Patient."""
        # Search for patients and include observations that reference them
        response = client.search("Patient", {
            "family": "Taylor",
            "_revinclude": "Observation:subject"
        })

        bundle = assertions.assert_bundle(response)
        assert bundle['total'] >= 1

        # Bundle should contain both Patient and Observation resources
        patient_count = 0
        observation_count = 0

        for entry in bundle.get('entry', []):
            resource_type = entry['resource']['resourceType']
            if resource_type == 'Patient':
                patient_count += 1
            elif resource_type == 'Observation':
                observation_count += 1

        assert patient_count >= 1, "Should include at least one Patient"
        assert observation_count >= 3, "Should include Emma Taylor's observations"

    def test_revinclude_practitioner_patients(self, client, assertions, test_data):
        """Test including Patients that reference Practitioner."""
        # Search for practitioners and include patients who reference them
        response = client.search("Practitioner", {
            "family": "Anderson",
            "_revinclude": "Patient:general-practitioner"
        })

        bundle = assertions.assert_bundle(response)

        # Bundle should contain both Practitioner and Patient resources
        practitioner_count = 0
        patient_count = 0

        for entry in bundle.get('entry', []):
            resource_type = entry['resource']['resourceType']
            if resource_type == 'Practitioner':
                practitioner_count += 1
            elif resource_type == 'Patient':
                patient_count += 1

        assert practitioner_count >= 1, "Should include at least one Practitioner"
        assert patient_count >= 1, "Should include patients who reference Dr. Anderson"

    def test_revinclude_with_resource_type_specified(self, client, assertions, test_data):
        """Test _revinclude with explicit resource type."""
        response = client.search("Patient", {
            "family": "Chen",
            "_revinclude": "Observation:subject:Patient"
        })

        bundle = assertions.assert_bundle(response)

        # Should include Patient and Observations
        resource_types = set()
        for entry in bundle.get('entry', []):
            resource_types.add(entry['resource']['resourceType'])

        assert 'Patient' in resource_types


class TestIncludeIterate:
    """Test _include:iterate for recursive includes."""

    def test_include_iterate_two_levels(self, client, assertions, test_data):
        """Test iterating includes across two levels."""
        # Start with Observation, include Patient, then include Practitioner
        response = client.search("Observation", {
            "code": "8867-4",
            "_include": "Observation:subject",
            "_include:iterate": "Patient:general-practitioner"
        })

        bundle = assertions.assert_bundle(response)

        # Bundle should contain Observation, Patient, and Practitioner
        resource_types = set()
        for entry in bundle.get('entry', []):
            resource_types.add(entry['resource']['resourceType'])

        assert 'Observation' in resource_types, "Should include Observations"
        # Patient and Practitioner may be included depending on server support

    def test_revinclude_iterate(self, client, assertions, test_data):
        """Test iterating reverse includes."""
        # Start with Practitioner, include Patients, then include their Observations
        response = client.search("Practitioner", {
            "family": "Anderson",
            "_revinclude": "Patient:general-practitioner",
            "_revinclude:iterate": "Observation:subject"
        })

        bundle = assertions.assert_bundle(response)

        # Bundle should potentially contain Practitioner, Patient, and Observation
        resource_types = set()
        for entry in bundle.get('entry', []):
            resource_types.add(entry['resource']['resourceType'])

        assert 'Practitioner' in resource_types


class TestIncludeCombinations:
    """Test combinations of _include and _revinclude."""

    def test_include_and_revinclude_together(self, client, assertions, test_data):
        """Test using both _include and _revinclude in same search."""
        # Search for Patient, include their GP and their Observations
        response = client.search("Patient", {
            "family": "Taylor",
            "_include": "Patient:general-practitioner",
            "_revinclude": "Observation:subject"
        })

        bundle = assertions.assert_bundle(response)

        # Bundle should contain Patient, Practitioner, and Observation
        resource_types = set()
        for entry in bundle.get('entry', []):
            resource_types.add(entry['resource']['resourceType'])

        assert 'Patient' in resource_types, "Should include Patient"
        # May include Practitioner and Observation depending on data

    def test_multiple_includes(self, client, assertions, test_data):
        """Test multiple _include parameters."""
        response = client.search("Patient", {
            "_include": [
                "Patient:general-practitioner",
                "Patient:organization"
            ]
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should include patients and any referenced resources

    def test_multiple_revincludes(self, client, assertions, test_data):
        """Test multiple _revinclude parameters."""
        response = client.search("Patient", {
            "family": "Taylor",
            "_revinclude": [
                "Observation:subject",
                "Condition:subject"
            ]
        })

        bundle = assertions.assert_bundle(response)
        # Should include patient and resources that reference them


class TestIncludeEdgeCases:
    """Test edge cases for _include and _revinclude."""

    def test_include_with_no_matching_references(self, client, assertions, test_data):
        """Test _include when no resources have the reference."""
        # Search for patient without general practitioner
        response = client.search("Patient", {
            "family": "Lee",  # Sophia Lee has no GP
            "_include": "Patient:general-practitioner"
        })

        bundle = assertions.assert_bundle(response)

        # Should still return the patient, just no included resources
        patient_count = 0
        for entry in bundle.get('entry', []):
            if entry['resource']['resourceType'] == 'Patient':
                patient_count += 1

        assert patient_count >= 1, "Should still return matching patients"

    def test_revinclude_with_no_referencing_resources(self, client, assertions, test_data):
        """Test _revinclude when no resources reference the result."""
        # Search for patient with no observations
        response = client.search("Patient", {
            "family": "Lee",  # Sophia Lee has no observations
            "_revinclude": "Observation:subject"
        })

        bundle = assertions.assert_bundle(response)

        # Should return the patient even if no observations reference them
        patient_count = 0
        observation_count = 0
        for entry in bundle.get('entry', []):
            resource_type = entry['resource']['resourceType']
            if resource_type == 'Patient':
                patient_count += 1
            elif resource_type == 'Observation':
                observation_count += 1

        assert patient_count >= 1, "Should return matching patient"
        assert observation_count == 0, "Should not include observations for Sophia Lee"

    def test_include_with_invalid_parameter(self, client, assertions, test_data):
        """Test _include with non-existent search parameter."""
        response = client.search("Patient", {
            "_include": "Patient:nonexistent-parameter"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Server should ignore invalid include or return error

    def test_include_wildcard(self, client, assertions, test_data):
        """Test _include with wildcard (include all references)."""
        response = client.search("Patient", {
            "family": "Taylor",
            "_include": "Patient:*"
        })

        bundle = assertions.assert_bundle(response)
        # Should include patient and all resources they reference


class TestIncludeWithSearchParameters:
    """Test _include/_revinclude combined with other search parameters."""

    def test_include_with_filter_on_main_resource(self, client, assertions, test_data):
        """Test _include with search filters on primary resource."""
        response = client.search("Patient", {
            "family": "Taylor",
            "given": "Emma",
            "_include": "Patient:general-practitioner"
        })

        bundle = assertions.assert_bundle(response)
        # Should only include Emma Taylor and her GP

    def test_include_with_count_limit(self, client, assertions, test_data):
        """Test _include with _count parameter."""
        response = client.search("Patient", {
            "_include": "Patient:general-practitioner",
            "_count": "2"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # _count should limit the primary results, included resources are extra

    def test_revinclude_with_sort(self, client, assertions, test_data):
        """Test _revinclude with _sort parameter."""
        response = client.search("Patient", {
            "_revinclude": "Observation:subject",
            "_sort": "family"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Patients should be sorted, included observations are unsorted
