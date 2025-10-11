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
        # Should find exactly 1 patient: Alice Brown (whose GP is Dr. Smith)
        assert bundle['total'] == 1, f"Expected 1 patient with GP family name 'Smith', got {bundle['total']}"

        # Verify Alice Brown is in results and others are NOT
        found_patients = []
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            patient_id = patient['id']
            names = patient.get('name', [])
            for name in names:
                family = name.get('family', '')
                given = name.get('given', [])
                found_patients.append((patient_id, family, given))

        # Alice Brown should be found
        alice_found = any(p[1] == 'Brown' and 'Alice' in p[2] for p in found_patients)
        assert alice_found, "Should find Alice Brown whose GP is Dr. Smith"

        # Bob Williams should NOT be found (his GP is Dr. Johnson)
        bob_found = any(p[1] == 'Williams' and 'Bob' in p[2] for p in found_patients)
        assert not bob_found, "Should NOT find Bob Williams whose GP is Dr. Johnson"

        # Charlie Davis should NOT be found (has no GP)
        charlie_found = any(p[1] == 'Davis' and 'Charlie' in p[2] for p in found_patients)
        assert not charlie_found, "Should NOT find Charlie Davis who has no GP"

    def test_chain_patient_to_practitioner_by_identifier(self, client, assertions, test_data):
        """Test chaining using practitioner identifier."""
        response = client.search("Patient", {
            "general-practitioner.identifier": "PRAC-002"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find exactly 1 patient: Bob Williams (whose GP is PRAC-002)
        assert bundle['total'] == 1, f"Expected 1 patient with GP identifier 'PRAC-002', got {bundle['total']}"

        # Verify Bob Williams is in results and others are NOT
        found_patients = []
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            patient_id = patient['id']
            names = patient.get('name', [])
            for name in names:
                family = name.get('family', '')
                given = name.get('given', [])
                found_patients.append((patient_id, family, given))

        # Bob Williams should be found
        bob_found = any(p[1] == 'Williams' and 'Bob' in p[2] for p in found_patients)
        assert bob_found, "Should find Bob Williams whose GP is PRAC-002"

        # Alice Brown should NOT be found (her GP is PRAC-001)
        alice_found = any(p[1] == 'Brown' and 'Alice' in p[2] for p in found_patients)
        assert not alice_found, "Should NOT find Alice Brown whose GP is PRAC-001"

        # Charlie Davis should NOT be found (has no GP)
        charlie_found = any(p[1] == 'Davis' and 'Charlie' in p[2] for p in found_patients)
        assert not charlie_found, "Should NOT find Charlie Davis who has no GP"

    def test_chain_observation_to_patient_by_name(self, client, assertions, test_data):
        """Test chaining from Observation to Patient by name."""
        # Find observations where the patient's family name is "Brown"
        response = client.search("Observation", {
            "subject:Patient.family": "Brown"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find exactly 2 observations for Alice Brown (heart rate and temperature)
        assert bundle['total'] == 2, f"Expected 2 observations for patient 'Brown', got {bundle['total']}"

        # Verify all observations are for Alice Brown's patient ID
        alice_patient_id = test_data['patients'][0]['id']  # Alice Brown
        bob_patient_id = test_data['patients'][1]['id']    # Bob Williams

        found_patient_ids = []
        for entry in bundle.get('entry', []):
            obs = entry['resource']
            subject_ref = obs.get('subject', {}).get('reference', '')
            assert 'Patient/' in subject_ref, "Subject reference should be a Patient"
            # Extract patient ID from reference
            patient_id = subject_ref.split('Patient/')[1] if 'Patient/' in subject_ref else None
            found_patient_ids.append(patient_id)

        # All observations should be for Alice Brown
        assert all(pid == alice_patient_id for pid in found_patient_ids), \
            "All observations should be for Alice Brown only"

        # Bob Williams' observation should NOT be found
        assert bob_patient_id not in found_patient_ids, \
            "Should NOT find Bob Williams' observations (patient name is Williams, not Brown)"

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
        # Find patients that have observations with code 8867-4 (heart rate)
        response = client.search("Patient", {
            "_has:Observation:subject:code": "8867-4"  # Heart rate code
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find exactly 1 patient: Alice Brown who has a heart rate observation
        assert bundle['total'] == 1, f"Expected 1 patient with heart rate observation, got {bundle['total']}"

        alice_patient_id = test_data['patients'][0]['id']  # Alice Brown
        bob_patient_id = test_data['patients'][1]['id']    # Bob Williams
        charlie_patient_id = test_data['patients'][2]['id']  # Charlie Davis

        found_patient_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]

        # Alice Brown should be found (has heart rate observation)
        assert alice_patient_id in found_patient_ids, \
            "Should find Alice Brown who has a heart rate observation"

        # Bob Williams should NOT be found (has blood pressure, not heart rate)
        assert bob_patient_id not in found_patient_ids, \
            "Should NOT find Bob Williams who has blood pressure observation, not heart rate"

        # Charlie Davis should NOT be found (has no observations)
        assert charlie_patient_id not in found_patient_ids, \
            "Should NOT find Charlie Davis who has no observations"

    def test_reverse_chain_practitioner_has_patient(self, client, assertions, test_data):
        """Test finding practitioners who have patients."""
        # Find practitioners who are general practitioners for patients named "Brown"
        response = client.search("Practitioner", {
            "_has:Patient:general-practitioner:family": "Brown"
        })

        bundle = assertions.assert_bundle(response, "Practitioner")
        # Should find exactly 1 practitioner: Dr. Smith who is GP for Alice Brown
        assert bundle['total'] == 1, f"Expected 1 practitioner with patient named Brown, got {bundle['total']}"

        smith_prac_id = test_data['practitioners'][0]['id']  # Dr. Smith
        johnson_prac_id = test_data['practitioners'][1]['id']  # Dr. Johnson

        found_prac_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]

        # Dr. Smith should be found (is GP for Alice Brown)
        assert smith_prac_id in found_prac_ids, \
            "Should find Dr. Smith who is GP for Alice Brown"

        # Dr. Johnson should NOT be found (is GP for Bob Williams, not Brown)
        assert johnson_prac_id not in found_prac_ids, \
            "Should NOT find Dr. Johnson who is GP for Bob Williams, not Brown"


class TestMultipleLevelChaining:
    """Test chaining across multiple references."""

    def test_two_level_chain(self, client, assertions, test_data):
        """Test chaining through two levels of references."""
        # Find observations for patients whose GP has family name "Smith"
        # This would be: Observation -> Patient -> Practitioner
        response = client.search("Observation", {
            "subject:Patient.general-practitioner.family": "Smith"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should find exactly 2 observations for Alice Brown (whose GP is Dr. Smith)
        assert bundle['total'] == 2, f"Expected 2 observations for patients with GP 'Smith', got {bundle['total']}"

        alice_patient_id = test_data['patients'][0]['id']  # Alice Brown (GP is Dr. Smith)
        bob_patient_id = test_data['patients'][1]['id']    # Bob Williams (GP is Dr. Johnson)

        # Verify all observations are for Alice Brown only
        found_patient_ids = []
        for entry in bundle.get('entry', []):
            obs = entry['resource']
            subject_ref = obs.get('subject', {}).get('reference', '')
            patient_id = subject_ref.split('Patient/')[1] if 'Patient/' in subject_ref else None
            found_patient_ids.append(patient_id)

        # All observations should be for Alice Brown (whose GP is Dr. Smith)
        assert all(pid == alice_patient_id for pid in found_patient_ids), \
            "All observations should be for Alice Brown whose GP is Dr. Smith"

        # Bob Williams' observation should NOT be found (his GP is Dr. Johnson, not Smith)
        assert bob_patient_id not in found_patient_ids, \
            "Should NOT find Bob Williams' observations (his GP is Dr. Johnson, not Smith)"


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
        # Should find exactly 1 observation: heart rate for Alice Brown
        assert bundle['total'] == 1, f"Expected 1 heart rate observation for patients with GP 'Smith', got {bundle['total']}"

        # Verify it's the heart rate observation
        obs = bundle['entry'][0]['resource']
        code = obs.get('code', {}).get('coding', [{}])[0].get('code', '')
        assert code == '8867-4', "Should be the heart rate observation"

        # Verify it's for Alice Brown
        alice_patient_id = test_data['patients'][0]['id']
        subject_ref = obs.get('subject', {}).get('reference', '')
        patient_id = subject_ref.split('Patient/')[1] if 'Patient/' in subject_ref else None
        assert patient_id == alice_patient_id, "Should be Alice Brown's observation"

        # The temperature observation for Alice should NOT be found (different code)
        # Bob's blood pressure observation should NOT be found (different GP)

    def test_chain_with_multiple_values(self, client, assertions, test_data):
        """Test chaining with OR logic on chained parameter."""
        # Find patients whose GP is either Smith or Johnson
        response = client.search("Patient", {
            "general-practitioner.family": "Smith,Johnson"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find exactly 2 patients: Alice (GP Smith) and Bob (GP Johnson)
        assert bundle['total'] == 2, f"Expected 2 patients with GP 'Smith' or 'Johnson', got {bundle['total']}"

        alice_patient_id = test_data['patients'][0]['id']  # Alice Brown
        bob_patient_id = test_data['patients'][1]['id']    # Bob Williams
        charlie_patient_id = test_data['patients'][2]['id']  # Charlie Davis

        found_patient_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]

        # Alice Brown should be found (GP is Dr. Smith)
        assert alice_patient_id in found_patient_ids, \
            "Should find Alice Brown whose GP is Dr. Smith"

        # Bob Williams should be found (GP is Dr. Johnson)
        assert bob_patient_id in found_patient_ids, \
            "Should find Bob Williams whose GP is Dr. Johnson"

        # Charlie Davis should NOT be found (has no GP)
        assert charlie_patient_id not in found_patient_ids, \
            "Should NOT find Charlie Davis who has no GP"


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
        # Should return exactly 0 results (no GP with that name exists)
        assert bundle['total'] == 0, f"Expected 0 patients with non-existent GP name, got {bundle['total']}"
        assert len(bundle.get('entry', [])) == 0, "Entry list should be empty"

        # Verify none of our test patients are in the results
        alice_patient_id = test_data['patients'][0]['id']
        bob_patient_id = test_data['patients'][1]['id']
        charlie_patient_id = test_data['patients'][2]['id']

        found_patient_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]

        assert alice_patient_id not in found_patient_ids, "Should NOT find Alice Brown"
        assert bob_patient_id not in found_patient_ids, "Should NOT find Bob Williams"
        assert charlie_patient_id not in found_patient_ids, "Should NOT find Charlie Davis"

    def test_chain_with_invalid_resource_type(self, client, assertions, test_data):
        """Test chaining with explicit resource type that doesn't match."""
        # Try to chain to Organization when reference is actually Practitioner
        response = client.search("Patient", {
            "general-practitioner:Organization.name": "SomeName"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should return exactly 0 results as the reference type doesn't match
        assert bundle['total'] == 0, f"Expected 0 patients (wrong resource type), got {bundle['total']}"
        assert len(bundle.get('entry', [])) == 0, "Entry list should be empty"

        # Verify none of our test patients are in the results
        alice_patient_id = test_data['patients'][0]['id']
        bob_patient_id = test_data['patients'][1]['id']

        found_patient_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]

        # Even though Alice and Bob have GPs, they shouldn't be found because
        # we're looking for Organization type references, not Practitioner
        assert alice_patient_id not in found_patient_ids, \
            "Should NOT find Alice Brown (GP is Practitioner, not Organization)"
        assert bob_patient_id not in found_patient_ids, \
            "Should NOT find Bob Williams (GP is Practitioner, not Organization)"

    def test_chain_excludes_patients_without_reference(self, client, assertions, test_data):
        """Test that chaining properly excludes patients without the reference field."""
        # Search for any patient with a GP - Charlie Davis has no GP and should be excluded
        response = client.search("Patient", {
            "general-practitioner.family": "Smith,Johnson"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find exactly 2 patients (Alice and Bob) but NOT Charlie
        assert bundle['total'] == 2, f"Expected 2 patients with GPs, got {bundle['total']}"

        alice_patient_id = test_data['patients'][0]['id']  # Alice Brown (has GP)
        bob_patient_id = test_data['patients'][1]['id']    # Bob Williams (has GP)
        charlie_patient_id = test_data['patients'][2]['id']  # Charlie Davis (NO GP)

        found_patient_ids = [entry['resource']['id'] for entry in bundle.get('entry', [])]

        # Alice and Bob should be found
        assert alice_patient_id in found_patient_ids, "Should find Alice Brown who has a GP"
        assert bob_patient_id in found_patient_ids, "Should find Bob Williams who has a GP"

        # Charlie should NOT be found (has no generalPractitioner field)
        assert charlie_patient_id not in found_patient_ids, \
            "Should NOT find Charlie Davis who has no GP (missing generalPractitioner field)"
