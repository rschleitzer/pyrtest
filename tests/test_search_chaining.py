"""Test suite for FHIR search chaining operations."""
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
    """Create test data with relationships for chaining tests."""
    data = {
        'practitioners': [],
        'patients': [],
        'observations': []
    }

    # Create Practitioner 1: Dr. Smith
    prac1 = FHIRResourceGenerator.generate_practitioner(
        name=[{"family": "Smith", "given": ["John"], "prefix": ["Dr."]}],
        identifier=[{"system": "http://hospital.org/practitioners", "value": "PRAC-001"}]
    )
    resp = client.create(prac1)
    created_prac1 = assertions.assert_created(resp, "Practitioner")
    data['practitioners'].append(created_prac1)

    # Create Practitioner 2: Dr. Johnson
    prac2 = FHIRResourceGenerator.generate_practitioner(
        name=[{"family": "Johnson", "given": ["Sarah"], "prefix": ["Dr."]}],
        identifier=[{"system": "http://hospital.org/practitioners", "value": "PRAC-002"}]
    )
    resp = client.create(prac2)
    created_prac2 = assertions.assert_created(resp, "Practitioner")
    data['practitioners'].append(created_prac2)

    # Create Patient 1: Alice Brown with Dr. Smith as general practitioner
    patient1 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Brown", "given": ["Alice"]}],
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-CHAIN-001"}],
        generalPractitioner=[
            FHIRResourceGenerator.generate_reference(
                "Practitioner",
                created_prac1['id'],
                "Dr. John Smith"
            )
        ]
    )
    resp = client.create(patient1)
    created_patient1 = assertions.assert_created(resp, "Patient")
    data['patients'].append(created_patient1)

    # Create Patient 2: Bob Williams with Dr. Johnson as general practitioner
    patient2 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Williams", "given": ["Bob"]}],
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-CHAIN-002"}],
        generalPractitioner=[
            FHIRResourceGenerator.generate_reference(
                "Practitioner",
                created_prac2['id'],
                "Dr. Sarah Johnson"
            )
        ]
    )
    resp = client.create(patient2)
    created_patient2 = assertions.assert_created(resp, "Patient")
    data['patients'].append(created_patient2)

    # Create Patient 3: Charlie Davis with no practitioner
    patient3 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Davis", "given": ["Charlie"]}],
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-CHAIN-003"}]
    )
    resp = client.create(patient3)
    created_patient3 = assertions.assert_created(resp, "Patient")
    data['patients'].append(created_patient3)

    # Create Observation 1: Heart rate for Alice Brown
    obs1 = FHIRResourceGenerator.generate_observation(
        patient_ref=FHIRResourceGenerator.generate_reference(
            "Patient",
            created_patient1['id'],
            "Alice Brown"
        ),
        code_system="http://loinc.org",
        code="8867-4",
        code_display="Heart rate",
        value_quantity={"value": 75, "unit": "beats/minute", "system": "http://unitsofmeasure.org", "code": "/min"}
    )
    resp = client.create(obs1)
    created_obs1 = assertions.assert_created(resp, "Observation")
    data['observations'].append(created_obs1)

    # Create Observation 2: Blood pressure for Bob Williams
    obs2 = FHIRResourceGenerator.generate_observation(
        patient_ref=FHIRResourceGenerator.generate_reference(
            "Patient",
            created_patient2['id'],
            "Bob Williams"
        ),
        code_system="http://loinc.org",
        code="85354-9",
        code_display="Blood pressure",
        value_quantity={"value": 120, "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"}
    )
    resp = client.create(obs2)
    created_obs2 = assertions.assert_created(resp, "Observation")
    data['observations'].append(created_obs2)

    # Create Observation 3: Temperature for Alice Brown
    obs3 = FHIRResourceGenerator.generate_observation(
        patient_ref=FHIRResourceGenerator.generate_reference(
            "Patient",
            created_patient1['id'],
            "Alice Brown"
        ),
        code_system="http://loinc.org",
        code="8310-5",
        code_display="Body temperature",
        value_quantity={"value": 37.0, "unit": "Cel", "system": "http://unitsofmeasure.org", "code": "Cel"}
    )
    resp = client.create(obs3)
    created_obs3 = assertions.assert_created(resp, "Observation")
    data['observations'].append(created_obs3)

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


class TestForwardChaining:
    """Test forward chaining (following references)."""

    def test_chain_patient_to_practitioner_by_family(self, client, assertions, test_data):
        """Test chaining from Patient to Practitioner by family name."""
        # Find patients whose general practitioner has family name "Smith"
        response = client.search("Patient", {
            "general-practitioner.family": "Smith"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find Alice Brown (whose GP is Dr. Smith)
        assert bundle['total'] >= 1

        # Verify Alice Brown is in results
        found_alice = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            names = patient.get('name', [])
            for name in names:
                if name.get('family') == 'Brown' and 'Alice' in name.get('given', []):
                    found_alice = True
        assert found_alice, "Should find Alice Brown whose GP is Dr. Smith"

    def test_chain_patient_to_practitioner_by_identifier(self, client, assertions, test_data):
        """Test chaining using practitioner identifier."""
        response = client.search("Patient", {
            "general-practitioner.identifier": "PRAC-002"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find Bob Williams (whose GP is PRAC-002)
        assert bundle['total'] >= 1

        # Verify Bob Williams is in results
        found_bob = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            names = patient.get('name', [])
            for name in names:
                if name.get('family') == 'Williams' and 'Bob' in name.get('given', []):
                    found_bob = True
        assert found_bob, "Should find Bob Williams whose GP is PRAC-002"

    def test_chain_observation_to_patient_by_name(self, client, assertions, test_data):
        """Test chaining from Observation to Patient by name."""
        # Find observations where the patient's family name is "Brown"
        response = client.search("Observation", {
            "subject:Patient.family": "Brown"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observations for Alice Brown (2 observations)
        assert bundle['total'] >= 2

        # Verify all observations are for patients named Brown
        for entry in bundle.get('entry', []):
            obs = entry['resource']
            subject_ref = obs.get('subject', {}).get('reference', '')
            assert 'Patient/' in subject_ref

    def test_chain_observation_to_patient_by_gender(self, client, assertions, test_data):
        """Test chaining with gender parameter."""
        # Find observations for female patients
        response = client.search("Observation", {
            "subject:Patient.gender": "female"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observations based on patient gender
        # (depends on the gender of Alice and Bob in the test data)


class TestReverseChaining:
    """Test reverse chaining using _has parameter."""

    def test_reverse_chain_patient_has_observation(self, client, assertions, test_data):
        """Test finding patients who have observations."""
        # Find patients that have observations
        response = client.search("Patient", {
            "_has:Observation:subject:code": "8867-4"  # Heart rate code
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find Alice Brown who has a heart rate observation
        assert bundle['total'] >= 1

    def test_reverse_chain_practitioner_has_patient(self, client, assertions, test_data):
        """Test finding practitioners who have patients."""
        # Find practitioners who are general practitioners for patients
        response = client.search("Practitioner", {
            "_has:Patient:general-practitioner:family": "Brown"
        })

        bundle = assertions.assert_bundle(response, "Practitioner")
        # Should find Dr. Smith who is GP for Alice Brown
        assert bundle['total'] >= 1

        # Verify Dr. Smith is in results
        found_smith = False
        for entry in bundle.get('entry', []):
            prac = entry['resource']
            names = prac.get('name', [])
            for name in names:
                if name.get('family') == 'Smith':
                    found_smith = True
        assert found_smith, "Should find Dr. Smith who is GP for a patient named Brown"


class TestMultipleLevelChaining:
    """Test chaining across multiple references."""

    def test_two_level_chain(self, client, assertions, test_data):
        """Test chaining through two levels of references."""
        # Find observations for patients whose GP has a specific name
        # This would be: Observation -> Patient -> Practitioner
        response = client.search("Observation", {
            "subject:Patient.general-practitioner.family": "Smith"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observations for Alice Brown (whose GP is Dr. Smith)
        assert bundle['total'] >= 2


class TestChainingWithOtherParameters:
    """Test combining chaining with other search parameters."""

    def test_chain_with_date_filter(self, client, assertions, test_data):
        """Test chaining combined with date parameter."""
        # Find observations for patients named Brown, filtered by date
        response = client.search("Observation", {
            "subject:Patient.family": "Brown",
            "date": f"ge{test_data['observations'][0].get('effectiveDateTime', '2024-01-01')[:10]}"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find observations matching both criteria

    def test_chain_with_code_filter(self, client, assertions, test_data):
        """Test chaining combined with token parameter."""
        # Find heart rate observations for patients whose GP is Dr. Smith
        response = client.search("Observation", {
            "subject:Patient.general-practitioner.family": "Smith",
            "code": "8867-4"  # Heart rate
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find only the heart rate observation for Alice Brown
        assert bundle['total'] >= 1

    def test_chain_with_multiple_values(self, client, assertions, test_data):
        """Test chaining with OR logic on chained parameter."""
        # Find patients whose GP is either Smith or Johnson
        response = client.search("Patient", {
            "general-practitioner.family": "Smith,Johnson"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find both Alice (GP Smith) and Bob (GP Johnson)
        assert bundle['total'] >= 2


class TestMultipleChainedParameters:
    """Test multiple chained parameters on the same reference to validate JOIN aliasing."""

    def test_double_chain_same_reference(self, client, assertions):
        """Test two chained parameters on the same reference (validates unique JOIN aliases)."""
        # Create Practitioner with both family and given name
        prac = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "DoubleChainDoc", "given": ["Jane"]}]
        )
        resp = client.create(prac)
        created_prac = assertions.assert_created(resp, "Practitioner")

        # Create Patient linked to this Practitioner
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "DoubleChainPatient", "given": ["Test"]}],
            generalPractitioner=[
                FHIRResourceGenerator.generate_reference("Practitioner", created_prac['id'])
            ]
        )
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")

        # Search with TWO chained parameters on same reference
        # This validates that aliases are unique: patient_ref_general_practitioner_0, patient_ref_general_practitioner_1
        response = client.search("Patient", {
            "general-practitioner.family": "DoubleChainDoc",
            "general-practitioner.given": "Jane"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        found_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]
        assert created_patient['id'] in found_ids

        # Cleanup
        client.delete("Patient", created_patient['id'])
        client.delete("Practitioner", created_prac['id'])

    def test_triple_chain_same_reference(self, client, assertions):
        """Test three chained parameters on the same reference (validates aliasing with _0, _1, _2)."""
        # Create Practitioner with family, given, and email
        prac = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "TripleChainDoc", "given": ["Alice"], "prefix": ["Dr"]}],
            telecom=[{"system": "email", "value": "alice.triple@example.com"}]
        )
        resp = client.create(prac)
        created_prac = assertions.assert_created(resp, "Practitioner")

        # Create Patient linked to this Practitioner
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "TripleChainPatient", "given": ["Test"]}],
            generalPractitioner=[
                FHIRResourceGenerator.generate_reference("Practitioner", created_prac['id'])
            ]
        )
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")

        # Search with THREE chained parameters on same reference
        response = client.search("Patient", {
            "general-practitioner.family": "TripleChainDoc",
            "general-practitioner.given": "Alice",
            "general-practitioner.email": "alice.triple@example.com"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        found_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]
        assert created_patient['id'] in found_ids

        # Cleanup
        client.delete("Patient", created_patient['id'])
        client.delete("Practitioner", created_prac['id'])

    def test_multiple_chains_all_must_match(self, client, assertions):
        """Test that with multiple chains, ALL conditions must match (AND logic)."""
        # Create Practitioner
        prac = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "CorrectFamily", "given": ["CorrectGiven"]}]
        )
        resp = client.create(prac)
        created_prac = assertions.assert_created(resp, "Practitioner")

        # Create Patient linked to this Practitioner
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "AndLogicPatient", "given": ["Test"]}],
            generalPractitioner=[
                FHIRResourceGenerator.generate_reference("Practitioner", created_prac['id'])
            ]
        )
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")

        # Search with one correct, one wrong - should return 0
        response = client.search("Patient", {
            "general-practitioner.family": "CorrectFamily",
            "general-practitioner.given": "WrongGiven"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] == 0

        # Cleanup
        client.delete("Patient", created_patient['id'])
        client.delete("Practitioner", created_prac['id'])

    def test_multiple_chains_isolation(self, client, assertions):
        """Test that multiple chains don't cross-contaminate between different practitioners."""
        # Create two Practitioners
        prac1 = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "IsolationDoc1", "given": ["First"]}]
        )
        resp1 = client.create(prac1)
        created_prac1 = assertions.assert_created(resp1, "Practitioner")

        prac2 = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "IsolationDoc2", "given": ["Second"]}]
        )
        resp2 = client.create(prac2)
        created_prac2 = assertions.assert_created(resp2, "Practitioner")

        # Create two Patients
        patient1 = FHIRResourceGenerator.generate_patient(
            name=[{"family": "IsolationPatient1"}],
            generalPractitioner=[
                FHIRResourceGenerator.generate_reference("Practitioner", created_prac1['id'])
            ]
        )
        resp_p1 = client.create(patient1)
        created_patient1 = assertions.assert_created(resp_p1, "Patient")

        patient2 = FHIRResourceGenerator.generate_patient(
            name=[{"family": "IsolationPatient2"}],
            generalPractitioner=[
                FHIRResourceGenerator.generate_reference("Practitioner", created_prac2['id'])
            ]
        )
        resp_p2 = client.create(patient2)
        created_patient2 = assertions.assert_created(resp_p2, "Patient")

        # Search for IsolationDoc2 + Second - should only find patient2
        response = client.search("Patient", {
            "general-practitioner.family": "IsolationDoc2",
            "general-practitioner.given": "Second"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        found_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]
        assert created_patient2['id'] in found_ids
        assert created_patient1['id'] not in found_ids

        # Cleanup
        client.delete("Patient", created_patient1['id'])
        client.delete("Patient", created_patient2['id'])
        client.delete("Practitioner", created_prac1['id'])
        client.delete("Practitioner", created_prac2['id'])

    def test_chain_with_regular_parameters(self, client, assertions):
        """Test combining multiple chained parameters with regular search parameters."""
        # Create Practitioner
        prac = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "MixedDoc", "given": ["Mixed"]}]
        )
        resp = client.create(prac)
        created_prac = assertions.assert_created(resp, "Practitioner")

        # Create Patient with specific family name
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "MixedPatient", "given": ["TestGiven"]}],
            generalPractitioner=[
                FHIRResourceGenerator.generate_reference("Practitioner", created_prac['id'])
            ]
        )
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")

        # Search with both regular and multiple chained parameters
        response = client.search("Patient", {
            "family": "MixedPatient",
            "general-practitioner.family": "MixedDoc",
            "general-practitioner.given": "Mixed"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        found_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]
        assert created_patient['id'] in found_ids

        # Cleanup
        client.delete("Patient", created_patient['id'])
        client.delete("Practitioner", created_prac['id'])


class TestChainingEdgeCases:
    """Test edge cases in chaining."""

    def test_chain_with_missing_reference(self, client, assertions, test_data):
        """Test chaining when some resources lack the reference."""
        # Search for patients with GP named "NonExistent"
        response = client.search("Patient", {
            "general-practitioner.family": "NonExistent"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should return empty results
        assert bundle['total'] == 0

    def test_chain_with_invalid_resource_type(self, client, assertions, test_data):
        """Test chaining with explicit resource type that doesn't match."""
        # Try to chain to Organization when reference is actually Practitioner
        response = client.search("Patient", {
            "general-practitioner:Organization.name": "SomeName"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should return no results as the reference type doesn't match
        assert bundle['total'] == 0
