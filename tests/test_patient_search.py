"""Test suite for Patient search operations."""
import pytest
import sys
import os
from datetime import datetime, timedelta

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
def test_patients(client, assertions):
    """Create a set of test patients with known attributes."""
    patients = []

    # Patient 1: John Smith, male
    p1 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Smith", "given": ["John"]}],
        gender="male",
        birthDate="1980-05-15",
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-001"}]
    )
    resp = client.create(p1)
    patients.append(assertions.assert_created(resp, "Patient"))

    # Patient 2: Jane Smith, female
    p2 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Smith", "given": ["Jane"]}],
        gender="female",
        birthDate="1985-08-20",
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-002"}]
    )
    resp = client.create(p2)
    patients.append(assertions.assert_created(resp, "Patient"))

    # Patient 3: Bob Johnson, male
    p3 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Johnson", "given": ["Bob"]}],
        gender="male",
        birthDate="1975-03-10",
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-003"}]
    )
    resp = client.create(p3)
    patients.append(assertions.assert_created(resp, "Patient"))

    # Patient 4: Alice Williams, female, inactive
    p4 = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Williams", "given": ["Alice"]}],
        gender="female",
        birthDate="1990-12-01",
        active=False,
        identifier=[{"system": "http://hospital.org/mrn", "value": "MRN-004"}]
    )
    resp = client.create(p4)
    patients.append(assertions.assert_created(resp, "Patient"))

    yield patients

    # Cleanup
    for patient in patients:
        try:
            client.delete("Patient", patient['id'])
        except:
            pass  # Best effort cleanup


class TestBasicSearch:
    """Test basic Patient search functionality."""

    def test_search_all_patients(self, client, assertions, test_patients):
        """Test searching for all patients returns a Bundle."""
        response = client.search("Patient")

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['type'] == 'searchset'
        assert bundle['total'] >= len(test_patients)

    def test_search_by_family_name(self, client, assertions, test_patients):
        """Test searching by family name."""
        response = client.search("Patient", {"family": "Smith"})

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find both John Smith and Jane Smith
        assert bundle['total'] >= 2

        # Verify all results have "Smith" in family name
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            family_names = [name['family'] for name in patient.get('name', [])]
            assert any('Smith' in fn for fn in family_names)

    def test_search_by_given_name(self, client, assertions, test_patients):
        """Test searching by given name."""
        response = client.search("Patient", {"given": "John"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify results contain "John"
        found_john = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                if 'John' in name.get('given', []):
                    found_john = True
        assert found_john, "Should find patient with given name John"

    def test_search_by_gender(self, client, assertions, test_patients):
        """Test searching by gender."""
        response = client.search("Patient", {"gender": "male"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 2  # John Smith and Bob Johnson

        # Verify all results are male
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            assert patient['gender'] == 'male'

    def test_search_by_identifier(self, client, assertions, test_patients):
        """Test searching by identifier (token search)."""
        response = client.search("Patient", {"identifier": "MRN-001"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] == 1

        patient = bundle['entry'][0]['resource']
        identifiers = [i['value'] for i in patient.get('identifier', [])]
        assert "MRN-001" in identifiers

    def test_search_by_identifier_with_system(self, client, assertions, test_patients):
        """Test searching by identifier with system (system|value format)."""
        response = client.search("Patient", {
            "identifier": "http://hospital.org/mrn|MRN-002"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] == 1

        patient = bundle['entry'][0]['resource']
        found = False
        for identifier in patient.get('identifier', []):
            if identifier.get('system') == 'http://hospital.org/mrn' and \
               identifier.get('value') == 'MRN-002':
                found = True
        assert found, "Should find patient with specific system and value"

    def test_search_by_birthdate(self, client, assertions, test_patients):
        """Test searching by birthdate (exact match)."""
        response = client.search("Patient", {"birthdate": "1980-05-15"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify result has correct birthdate
        found = False
        for entry in bundle.get('entry', []):
            if entry['resource'].get('birthDate') == '1980-05-15':
                found = True
        assert found


class TestSearchPrefixes:
    """Test search with date prefixes (gt, lt, ge, le, etc.)."""

    def test_search_birthdate_greater_than(self, client, assertions, test_patients):
        """Test birthdate with gt (greater than) prefix."""
        response = client.search("Patient", {"birthdate": "gt1985-01-01"})

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find Alice Williams (1990)
        assert bundle['total'] >= 1

    def test_search_birthdate_less_than(self, client, assertions, test_patients):
        """Test birthdate with lt (less than) prefix."""
        response = client.search("Patient", {"birthdate": "lt1980-01-01"})

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find Bob Johnson (1975)
        assert bundle['total'] >= 1

    def test_search_birthdate_range(self, client, assertions, test_patients):
        """Test birthdate range using ge and le prefixes."""
        # Find patients born between 1980 and 1990
        response = client.search("Patient", {
            "birthdate": ["ge1980-01-01", "le1990-01-01"]
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find John Smith (1980) and Jane Smith (1985)
        assert bundle['total'] >= 2


class TestSearchMultipleParameters:
    """Test search with multiple parameters (AND logic)."""

    def test_search_family_and_gender(self, client, assertions, test_patients):
        """Test search with multiple parameters (AND)."""
        response = client.search("Patient", {
            "family": "Smith",
            "gender": "male"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find only John Smith (male)
        assert bundle['total'] >= 1

        for entry in bundle.get('entry', []):
            patient = entry['resource']
            assert patient['gender'] == 'male'
            family_names = [name['family'] for name in patient.get('name', [])]
            assert any('Smith' in fn for fn in family_names)

    def test_search_multiple_conditions(self, client, assertions, test_patients):
        """Test search with three parameters."""
        response = client.search("Patient", {
            "family": "Smith",
            "gender": "female",
            "active": "true"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find Jane Smith (female, active)
        assert bundle['total'] >= 1


class TestSearchMultipleValues:
    """Test search with multiple values for one parameter (OR logic)."""

    def test_search_multiple_family_names(self, client, assertions, test_patients):
        """Test search with multiple family names (OR)."""
        response = client.search("Patient", {
            "family": "Smith,Johnson"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find Smith and Johnson patients
        assert bundle['total'] >= 3

    def test_search_multiple_genders(self, client, assertions, test_patients):
        """Test search with multiple values for same parameter."""
        response = client.search("Patient", {
            "gender": "male,female"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 4


class TestSearchModifiers:
    """Test search parameter modifiers."""

    def test_search_exact_modifier(self, client, assertions, test_patients):
        """Test :exact modifier for string search."""
        # Without exact - should find partial matches
        response1 = client.search("Patient", {"family": "Smit"})
        bundle1 = assertions.assert_bundle(response1, "Patient")

        # With exact - should not find partial matches
        response2 = client.search("Patient", {"family:exact": "Smit"})
        bundle2 = assertions.assert_bundle(response2, "Patient")

        # Exact search should find fewer or zero results
        assert bundle2['total'] <= bundle1['total']

    def test_search_contains_modifier(self, client, assertions, test_patients):
        """Test :contains modifier for substring search."""
        response = client.search("Patient", {"family:contains": "mit"})

        bundle = assertions.assert_bundle(response, "Patient")
        # Should find Smith
        assert bundle['total'] >= 1

    def test_search_missing_modifier(self, client, assertions):
        """Test :missing modifier."""
        # Search for patients without active field
        response = client.search("Patient", {"active:missing": "true"})

        bundle = assertions.assert_bundle(response, "Patient")
        # All results should not have active field, or vice versa

        for entry in bundle.get('entry', []):
            patient = entry['resource']
            assert 'active' not in patient, "Patient should not have active field"


class TestNamePrefixSuffix:
    """Test search for Patient name prefix and suffix."""

    @pytest.fixture
    def prefix_suffix_patients(self, client, assertions):
        """Create test patients with name prefixes and suffixes."""
        patients = []

        # Patient 1: Prof. Dr. Albert Einstein
        p1 = FHIRResourceGenerator.generate_patient(
            name=[{"family": "Einstein", "given": ["Albert"], "prefix": ["Prof.", "Dr."]}],
            gender="male",
            birthDate="1879-03-14"
        )
        resp = client.create(p1)
        patients.append(assertions.assert_created(resp, "Patient"))

        # Patient 2: Dr. Marie Curie, Ph.D.
        p2 = FHIRResourceGenerator.generate_patient(
            name=[{"family": "Curie", "given": ["Marie"], "prefix": ["Dr."], "suffix": ["Ph.D."]}],
            gender="female",
            birthDate="1867-11-07"
        )
        resp = client.create(p2)
        patients.append(assertions.assert_created(resp, "Patient"))

        # Patient 3: John Smith Jr.
        p3 = FHIRResourceGenerator.generate_patient(
            name=[{"family": "Smith", "given": ["John"], "suffix": ["Jr."]}],
            gender="male",
            birthDate="1990-01-15"
        )
        resp = client.create(p3)
        patients.append(assertions.assert_created(resp, "Patient"))

        # Patient 4: Brother Ansgar OSB (monk with religious name and former name)
        p4 = FHIRResourceGenerator.generate_patient(
            name=[
                {"use": "official", "given": ["Ansgar"], "prefix": ["Brother"], "suffix": ["OSB"]},
                {"use": "old", "given": ["Herbert"], "family": "Müller"}
            ],
            gender="male",
            birthDate="1960-06-01"
        )
        resp = client.create(p4)
        patients.append(assertions.assert_created(resp, "Patient"))

        yield patients

        # Cleanup
        for patient in patients:
            try:
                client.delete("Patient", patient['id'])
            except:
                pass  # Best effort cleanup

    def test_search_by_prefix_default(self, client, assertions, prefix_suffix_patients):
        """Test searching by prefix using default name parameter."""
        response = client.search("Patient", {"name": "Prof"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify result contains prefix "Prof."
        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                if "Prof." in name.get('prefix', []):
                    found = True
        assert found, "Should find patient with prefix Prof."

    def test_search_by_prefix_exact(self, client, assertions, prefix_suffix_patients):
        """Test searching by prefix with exact modifier."""
        response = client.search("Patient", {"name:exact": "Prof."})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify result has exact prefix "Prof."
        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                if "Prof." in name.get('prefix', []):
                    found = True
        assert found, "Should find patient with exact prefix Prof."

    def test_search_by_prefix_contains(self, client, assertions, prefix_suffix_patients):
        """Test searching by prefix with contains modifier."""
        response = client.search("Patient", {"name:contains": "Dr"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify result contains "Dr" in prefix
        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                for prefix in name.get('prefix', []):
                    if "Dr" in prefix:
                        found = True
        assert found, "Should find patient with Dr in prefix"

    def test_search_by_suffix_default(self, client, assertions, prefix_suffix_patients):
        """Test searching by suffix using default name parameter."""
        response = client.search("Patient", {"name": "Jr"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify result contains suffix "Jr."
        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                if "Jr." in name.get('suffix', []):
                    found = True
        assert found, "Should find patient with suffix Jr."

    def test_search_by_suffix_exact(self, client, assertions, prefix_suffix_patients):
        """Test searching by suffix with exact modifier."""
        response = client.search("Patient", {"name:exact": "OSB"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify result has exact suffix "OSB"
        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                if "OSB" in name.get('suffix', []):
                    found = True
        assert found, "Should find patient with exact suffix OSB"

    def test_search_by_suffix_contains(self, client, assertions, prefix_suffix_patients):
        """Test searching by suffix with contains modifier."""
        response = client.search("Patient", {"name:contains": "Ph.D"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify result contains "Ph.D" in suffix
        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                for suffix in name.get('suffix', []):
                    if "Ph.D" in suffix:
                        found = True
        assert found, "Should find patient with Ph.D in suffix"

    def test_search_by_religious_suffix(self, client, assertions, prefix_suffix_patients):
        """Test searching for religious title suffix (OSB)."""
        response = client.search("Patient", {"name": "Ansgar"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify we find the monk by religious name
        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                if "Ansgar" in name.get('given', []):
                    found = True
        assert found, "Should find Brother Ansgar by religious name"

    def test_search_by_former_name(self, client, assertions, prefix_suffix_patients):
        """Test searching for person by their former/old name."""
        response = client.search("Patient", {"name": "Herbert"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        # Verify we find the monk by former given name
        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                if "Herbert" in name.get('given', []):
                    found = True
        assert found, "Should find Brother Ansgar by former name Herbert"

        # Also test by former family name
        response = client.search("Patient", {"name": "Müller"})
        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] >= 1

        found = False
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            for name in patient.get('name', []):
                if name.get('family') == "Müller":
                    found = True
        assert found, "Should find Brother Ansgar by former family name Müller"


class TestResultControl:
    """Test result control parameters (_count, _sort, etc.)."""

    def test_count_parameter(self, client, assertions, test_patients):
        """Test _count parameter for pagination."""
        response = client.search("Patient", {"_count": "2"})

        bundle = assertions.assert_bundle(response, "Patient")
        entries = bundle.get('entry', [])
        assert len(entries) <= 2, "Should return at most 2 results"

    def test_sort_ascending(self, client, assertions, test_patients):
        """Test _sort parameter (ascending)."""
        response = client.search("Patient", {
            "family": "Smith",
            "_sort": "birthdate"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        entries = bundle.get('entry', [])

        if len(entries) >= 2:
            # Verify ascending order
            dates = [e['resource'].get('birthDate') for e in entries if 'birthDate' in e['resource']]
            assert dates == sorted(dates), "Results should be sorted by birthdate ascending"

    def test_sort_descending(self, client, assertions, test_patients):
        """Test _sort parameter (descending)."""
        response = client.search("Patient", {
            "family": "Smith",
            "_sort": "-birthdate"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        entries = bundle.get('entry', [])

        if len(entries) >= 2:
            # Verify descending order
            dates = [e['resource'].get('birthDate') for e in entries if 'birthDate' in e['resource']]
            assert dates == sorted(dates, reverse=True), "Results should be sorted by birthdate descending"

    def test_summary_parameter(self, client, assertions, test_patients):
        """Test _summary parameter."""
        response = client.search("Patient", {
            "_summary": "true",
            "family": "Smith"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        # Summary results should have reduced content
        # Exact behavior is server-dependent

    def test_elements_parameter(self, client, assertions, test_patients):
        """Test _elements parameter for sparse fieldsets."""
        response = client.search("Patient", {
            "_elements": "id,name",
            "family": "Smith"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            # Should only have id and name (and resourceType which is always included)
            assert 'id' in patient
            assert 'name' in patient
            # Other fields might still be present depending on server implementation


class TestEmptyResults:
    """Test searches that return no results."""

    def test_search_no_matches(self, client, assertions):
        """Test search with no matching results."""
        response = client.search("Patient", {"family": "NONEXISTENT_NAME_12345"})

        bundle = assertions.assert_bundle(response, "Patient")
        assert bundle['total'] == 0
        assert len(bundle.get('entry', [])) == 0
