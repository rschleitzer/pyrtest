"""Test suite for Practitioner search operations."""
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


class TestPractitionerNamePrefixSuffix:
    """Test search for Practitioner name prefix and suffix."""

    @pytest.fixture
    def prefix_suffix_practitioners(self, client, assertions):
        """Create test practitioners with name prefixes and suffixes."""
        practitioners = []

        # Practitioner 1: Prof. Dr. Albert Einstein
        p1 = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "Einstein", "given": ["Albert"], "prefix": ["Prof.", "Dr."]}],
            gender="male",
            active=True
        )
        resp = client.create(p1)
        practitioners.append(assertions.assert_created(resp, "Practitioner"))

        # Practitioner 2: Dr. Marie Curie, Ph.D.
        p2 = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "Curie", "given": ["Marie"], "prefix": ["Dr."], "suffix": ["Ph.D."]}],
            gender="female",
            active=True
        )
        resp = client.create(p2)
        practitioners.append(assertions.assert_created(resp, "Practitioner"))

        # Practitioner 3: John Smith Jr.
        p3 = FHIRResourceGenerator.generate_practitioner(
            name=[{"family": "Smith", "given": ["John"], "suffix": ["Jr."]}],
            gender="male",
            active=True
        )
        resp = client.create(p3)
        practitioners.append(assertions.assert_created(resp, "Practitioner"))

        # Practitioner 4: Brother Ansgar OSB (monk with religious name and former name)
        p4 = FHIRResourceGenerator.generate_practitioner(
            name=[
                {"use": "official", "given": ["Ansgar"], "prefix": ["Brother"], "suffix": ["OSB"]},
                {"use": "old", "given": ["Herbert"], "family": "Müller"}
            ],
            gender="male",
            active=True
        )
        resp = client.create(p4)
        practitioners.append(assertions.assert_created(resp, "Practitioner"))

        yield practitioners

        # Cleanup
        for practitioner in practitioners:
            try:
                client.delete("Practitioner", practitioner['id'])
            except:
                pass  # Best effort cleanup

    def test_search_by_prefix_default(self, client, assertions, prefix_suffix_practitioners):
        """Test searching by prefix using default name parameter."""
        response = client.search("Practitioner", {"name": "Prof"})

        bundle = assertions.assert_bundle(response, "Practitioner")
        assert bundle['total'] >= 1

        # Verify result contains prefix "Prof."
        found = False
        for entry in bundle.get('entry', []):
            practitioner = entry['resource']
            for name in practitioner.get('name', []):
                if "Prof." in name.get('prefix', []):
                    found = True
        assert found, "Should find practitioner with prefix Prof."

    def test_search_by_prefix_exact(self, client, assertions, prefix_suffix_practitioners):
        """Test searching by prefix with exact modifier."""
        response = client.search("Practitioner", {"name:exact": "Prof."})

        bundle = assertions.assert_bundle(response, "Practitioner")
        assert bundle['total'] >= 1

        # Verify result has exact prefix "Prof."
        found = False
        for entry in bundle.get('entry', []):
            practitioner = entry['resource']
            for name in practitioner.get('name', []):
                if "Prof." in name.get('prefix', []):
                    found = True
        assert found, "Should find practitioner with exact prefix Prof."

    def test_search_by_prefix_contains(self, client, assertions, prefix_suffix_practitioners):
        """Test searching by prefix with contains modifier."""
        response = client.search("Practitioner", {"name:contains": "Dr"})

        bundle = assertions.assert_bundle(response, "Practitioner")
        assert bundle['total'] >= 1

        # Verify result contains "Dr" in prefix
        found = False
        for entry in bundle.get('entry', []):
            practitioner = entry['resource']
            for name in practitioner.get('name', []):
                for prefix in name.get('prefix', []):
                    if "Dr" in prefix:
                        found = True
        assert found, "Should find practitioner with Dr in prefix"

    def test_search_by_suffix_default(self, client, assertions, prefix_suffix_practitioners):
        """Test searching by suffix using default name parameter."""
        response = client.search("Practitioner", {"name": "Jr"})

        bundle = assertions.assert_bundle(response, "Practitioner")
        assert bundle['total'] >= 1

        # Verify result contains suffix "Jr."
        found = False
        for entry in bundle.get('entry', []):
            practitioner = entry['resource']
            for name in practitioner.get('name', []):
                if "Jr." in name.get('suffix', []):
                    found = True
        assert found, "Should find practitioner with suffix Jr."

    def test_search_by_suffix_exact(self, client, assertions, prefix_suffix_practitioners):
        """Test searching by suffix with exact modifier."""
        response = client.search("Practitioner", {"name:exact": "OSB"})

        bundle = assertions.assert_bundle(response, "Practitioner")
        assert bundle['total'] >= 1

        # Verify result has exact suffix "OSB"
        found = False
        for entry in bundle.get('entry', []):
            practitioner = entry['resource']
            for name in practitioner.get('name', []):
                if "OSB" in name.get('suffix', []):
                    found = True
        assert found, "Should find practitioner with exact suffix OSB"

    def test_search_by_suffix_contains(self, client, assertions, prefix_suffix_practitioners):
        """Test searching by suffix with contains modifier."""
        response = client.search("Practitioner", {"name:contains": "Ph.D"})

        bundle = assertions.assert_bundle(response, "Practitioner")
        assert bundle['total'] >= 1

        # Verify result contains "Ph.D" in suffix
        found = False
        for entry in bundle.get('entry', []):
            practitioner = entry['resource']
            for name in practitioner.get('name', []):
                for suffix in name.get('suffix', []):
                    if "Ph.D" in suffix:
                        found = True
        assert found, "Should find practitioner with Ph.D in suffix"

    def test_search_by_religious_suffix(self, client, assertions, prefix_suffix_practitioners):
        """Test searching for religious title suffix (OSB)."""
        response = client.search("Practitioner", {"name": "Ansgar"})

        bundle = assertions.assert_bundle(response, "Practitioner")
        assert bundle['total'] >= 1

        # Verify we find the monk by religious name
        found = False
        for entry in bundle.get('entry', []):
            practitioner = entry['resource']
            for name in practitioner.get('name', []):
                if "Ansgar" in name.get('given', []):
                    found = True
        assert found, "Should find Brother Ansgar by religious name"

    def test_search_by_former_name(self, client, assertions, prefix_suffix_practitioners):
        """Test searching for person by their former/old name."""
        response = client.search("Practitioner", {"name": "Herbert"})

        bundle = assertions.assert_bundle(response, "Practitioner")
        assert bundle['total'] >= 1

        # Verify we find the monk by former given name
        found = False
        for entry in bundle.get('entry', []):
            practitioner = entry['resource']
            for name in practitioner.get('name', []):
                if "Herbert" in name.get('given', []):
                    found = True
        assert found, "Should find Brother Ansgar by former name Herbert"

        # Also test by former family name
        response = client.search("Practitioner", {"name": "Müller"})
        bundle = assertions.assert_bundle(response, "Practitioner")
        assert bundle['total'] >= 1

        found = False
        for entry in bundle.get('entry', []):
            practitioner = entry['resource']
            for name in practitioner.get('name', []):
                if name.get('family') == "Müller":
                    found = True
        assert found, "Should find Brother Ansgar by former family name Müller"
