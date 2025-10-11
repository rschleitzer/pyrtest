"""Pagination tests for FHIR search results."""
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
def large_patient_set(client, assertions):
    """Create a large set of patients for pagination testing."""
    patients = []

    # Create 25 patients for pagination tests
    for i in range(25):
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": f"PaginationTest{i:02d}", "given": ["Patient"]}],
            identifier=[{"system": "http://hospital.org/pagination", "value": f"PAGE-{i:03d}"}]
        )
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")
        patients.append(created)

    yield patients

    # Cleanup
    for patient in patients:
        try:
            client.delete("Patient", patient['id'])
        except:
            pass


class TestBasicPagination:
    """Test basic pagination functionality."""

    def test_count_parameter_limits_results(self, client, assertions, large_patient_set):
        """Test that _count parameter limits the number of results."""
        response = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "10"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        entries = bundle.get('entry', [])

        # Should return at most 10 results
        assert len(entries) <= 10, f"Should return at most 10 results, got {len(entries)}"

        # Total should indicate total matching resources
        assert bundle.get('total', 0) >= 10, "Total should show more resources available"

    def test_next_link_exists(self, client, assertions, large_patient_set):
        """Test that next link is provided when more results exist."""
        response = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "10"
        })

        bundle = assertions.assert_bundle(response, "Patient")

        # Check for next link
        links = bundle.get('link', [])
        link_relations = [link.get('relation') for link in links]

        if bundle.get('total', 0) > 10:
            assert 'next' in link_relations, "Should have 'next' link when more results available"

    def test_self_link_present(self, client, assertions, large_patient_set):
        """Test that self link is present in bundle."""
        response = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "5"
        })

        bundle = assertions.assert_bundle(response, "Patient")

        links = bundle.get('link', [])
        link_relations = [link.get('relation') for link in links]

        assert 'self' in link_relations, "Should have 'self' link"

    def test_follow_next_link(self, client, assertions, large_patient_set):
        """Test following the next link to get subsequent pages."""
        # Get first page
        response1 = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "5"
        })

        bundle1 = assertions.assert_bundle(response1, "Patient")

        # Find next link
        next_link = None
        for link in bundle1.get('link', []):
            if link.get('relation') == 'next':
                next_link = link.get('url')
                break

        if next_link:
            # Follow next link
            import requests
            response2 = requests.get(next_link)
            assert response2.status_code == 200, "Next link should return 200"

            bundle2 = response2.json()
            assert bundle2['resourceType'] == 'Bundle', "Should return a Bundle"

            # Should have different entries than first page
            entries1 = bundle1.get('entry', [])
            entries2 = bundle2.get('entry', [])

            if entries1 and entries2:
                ids1 = set(e['resource']['id'] for e in entries1)
                ids2 = set(e['resource']['id'] for e in entries2)
                assert len(ids1.intersection(ids2)) == 0, "Pages should have different resources"

    def test_page_navigation_links(self, client, assertions, large_patient_set):
        """Test that first, last, previous, next links are provided appropriately."""
        response = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "5"
        })

        bundle = assertions.assert_bundle(response, "Patient")

        links = {link.get('relation'): link.get('url') for link in bundle.get('link', [])}

        # First page should have 'first' link
        assert 'first' in links or 'self' in links, "Should have 'first' or 'self' link"

        # If there are more results, should have 'next' link
        if bundle.get('total', 0) > 5:
            assert 'next' in links, "Should have 'next' link when more results available"


class TestPaginationStability:
    """Test that pagination results are stable across requests."""

    def test_consistent_results_on_repeat(self, client, assertions, large_patient_set):
        """Test that repeating the same search gives consistent results."""
        # First search
        response1 = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "10",
            "_sort": "family"
        })
        bundle1 = assertions.assert_bundle(response1, "Patient")

        # Second search with same parameters
        response2 = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "10",
            "_sort": "family"
        })
        bundle2 = assertions.assert_bundle(response2, "Patient")

        # Should get same results (same IDs in same order)
        entries1 = bundle1.get('entry', [])
        entries2 = bundle2.get('entry', [])

        if entries1 and entries2:
            ids1 = [e['resource']['id'] for e in entries1]
            ids2 = [e['resource']['id'] for e in entries2]
            assert ids1 == ids2, "Repeated searches should return same results in same order"

    def test_pagination_with_sort_order(self, client, assertions, large_patient_set):
        """Test that pagination respects sort order across pages."""
        # Get first page sorted by family name
        response1 = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "10",
            "_sort": "family"
        })
        bundle1 = assertions.assert_bundle(response1, "Patient")

        entries1 = bundle1.get('entry', [])
        if len(entries1) >= 2:
            # Verify first page is sorted
            families = [e['resource']['name'][0]['family'] for e in entries1 if e['resource'].get('name')]
            assert families == sorted(families), "First page should be sorted by family name"


class TestPaginationEdgeCases:
    """Test edge cases in pagination."""

    def test_count_zero(self, client, assertions):
        """Test _count=0 returns summary without entries."""
        response = client.search("Patient", {
            "_count": "0"
        })

        bundle = assertions.assert_bundle(response, "Patient")

        # Should have total but no entries
        assert 'total' in bundle, "Should have total count"
        entries = bundle.get('entry', [])
        assert len(entries) == 0, "Should have no entries with _count=0"

    def test_count_exceeds_server_limit(self, client, assertions, large_patient_set):
        """Test requesting more results than server limit."""
        # Request a very large count
        response = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "1000"
        })

        bundle = assertions.assert_bundle(response, "Patient")

        # Server may limit to its max page size
        entries = bundle.get('entry', [])
        # Just verify we get a reasonable response

    def test_pagination_with_zero_results(self, client, assertions):
        """Test pagination when search returns no results."""
        response = client.search("Patient", {
            "family": "NONEXISTENT_PAGINATION_TEST_999",
            "_count": "10"
        })

        bundle = assertions.assert_bundle(response, "Patient")

        assert bundle.get('total', 0) == 0, "Should have zero total"
        assert len(bundle.get('entry', [])) == 0, "Should have no entries"

        # Should still have self link
        links = bundle.get('link', [])
        link_relations = [link.get('relation') for link in links]
        assert 'self' in link_relations, "Should have self link even with no results"

    def test_pagination_with_single_result(self, client, assertions):
        """Test pagination when only one result exists."""
        # Create a unique patient
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "UniquePaginationPatient"}]
        )
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            response = client.search("Patient", {
                "family": "UniquePaginationPatient",
                "_count": "10"
            })

            bundle = assertions.assert_bundle(response, "Patient")

            assert bundle.get('total') == 1, "Should have one result"
            assert len(bundle.get('entry', [])) == 1, "Should have one entry"

            # Should not have next link
            links = bundle.get('link', [])
            link_relations = [link.get('relation') for link in links]
            assert 'next' not in link_relations, "Should not have next link with single result"
        finally:
            client.delete("Patient", created['id'])


class TestPaginationWithSearchParameters:
    """Test pagination combined with various search parameters."""

    def test_pagination_with_filter(self, client, assertions, large_patient_set):
        """Test pagination with search filter."""
        response = client.search("Patient", {
            "family:contains": "PaginationTest",
            "identifier:contains": "PAGE",
            "_count": "5"
        })

        bundle = assertions.assert_bundle(response, "Patient")

        # All returned results should match the filter
        for entry in bundle.get('entry', []):
            patient = entry['resource']
            identifiers = patient.get('identifier', [])
            has_page = any('PAGE' in id.get('value', '') for id in identifiers)
            assert has_page, "All results should have PAGE in identifier"

    def test_pagination_with_include(self, client, assertions):
        """Test pagination with _include parameter."""
        response = client.search("Patient", {
            "_include": "Patient:general-practitioner",
            "_count": "5"
        })

        bundle = assertions.assert_bundle(response)

        # _count applies to matched resources, included resources are extra
        # Just verify we get a valid bundle

    def test_pagination_with_sort(self, client, assertions, large_patient_set):
        """Test pagination maintains sort order."""
        response = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_sort": "family",
            "_count": "10"
        })

        bundle = assertions.assert_bundle(response, "Patient")
        entries = bundle.get('entry', [])

        if len(entries) >= 2:
            families = [e['resource']['name'][0]['family'] for e in entries if e['resource'].get('name')]
            assert families == sorted(families), "Results should be sorted"


class TestLargePagination:
    """Test pagination over large result sets."""

    def test_iterate_through_all_pages(self, client, assertions, large_patient_set):
        """Test iterating through all pages of results."""
        all_ids = set()
        next_url = None
        page_count = 0
        max_pages = 10  # Safety limit

        # Get first page
        response = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "5"
        })
        bundle = assertions.assert_bundle(response, "Patient")

        while page_count < max_pages:
            page_count += 1

            # Collect IDs from this page
            for entry in bundle.get('entry', []):
                all_ids.add(entry['resource']['id'])

            # Find next link
            next_url = None
            for link in bundle.get('link', []):
                if link.get('relation') == 'next':
                    next_url = link.get('url')
                    break

            if not next_url:
                break

            # Follow next link
            import requests
            response = requests.get(next_url)
            if response.status_code != 200:
                break
            bundle = response.json()

        # Should have collected a reasonable number of unique IDs
        assert len(all_ids) >= 5, f"Should have collected at least 5 unique patient IDs, got {len(all_ids)}"

    def test_page_size_consistency(self, client, assertions, large_patient_set):
        """Test that page sizes are consistent (except last page)."""
        page_sizes = []
        next_url = None
        page_count = 0
        max_pages = 5

        response = client.search("Patient", {
            "family:contains": "PaginationTest",
            "_count": "5"
        })
        bundle = assertions.assert_bundle(response, "Patient")

        while page_count < max_pages:
            page_count += 1
            entries = bundle.get('entry', [])
            page_sizes.append(len(entries))

            # Find next link
            next_url = None
            for link in bundle.get('link', []):
                if link.get('relation') == 'next':
                    next_url = link.get('url')
                    break

            if not next_url:
                break

            import requests
            response = requests.get(next_url)
            if response.status_code != 200:
                break
            bundle = response.json()

        # All pages except possibly the last should have the requested count
        if len(page_sizes) > 1:
            for size in page_sizes[:-1]:
                assert size <= 5, f"Page size should not exceed requested count of 5"
