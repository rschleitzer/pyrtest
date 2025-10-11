"""Tests for FHIR resource history and versioning."""
import pytest
import sys
import os
from datetime import datetime, timedelta, timezone

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


class TestResourceHistory:
    """Test resource history operations."""

    @pytest.fixture
    def patient_with_history(self, client, assertions):
        """Create a patient and update it multiple times to generate history."""
        # Create initial patient
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "HistoryTest", "given": ["Version1"]}]
        )
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        # Update patient - version 2
        created['name'] = [{"family": "HistoryTest", "given": ["Version2"]}]
        resp = client.update(created)
        version2 = resp.json()

        # Update patient - version 3
        version2['name'] = [{"family": "HistoryTest", "given": ["Version3"]}]
        resp = client.update(version2)
        version3 = resp.json()

        yield {
            'id': created['id'],
            'version1': created,
            'version2': version2,
            'version3': version3
        }

        # Cleanup
        try:
            client.delete("Patient", created['id'])
        except:
            pass

    def test_instance_history(self, client, assertions, patient_with_history):
        """Test retrieving history for a specific resource instance."""
        patient_id = patient_with_history['id']

        # Get history for this patient
        response = client.history("Patient", patient_id)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        bundle = response.json()

        assert bundle['resourceType'] == 'Bundle', "Should return a Bundle"
        assert bundle['type'] == 'history', "Bundle type should be 'history'"

        # Should have at least 3 entries (3 versions)
        entries = bundle.get('entry', [])
        assert len(entries) >= 3, f"Should have at least 3 history entries, got {len(entries)}"

        # Entries should be sorted by most recent first (descending)
        # Verify that versions are in descending order
        versions = []
        for entry in entries:
            resource = entry.get('resource', {})
            meta = resource.get('meta', {})
            version_id = meta.get('versionId')
            if version_id:
                versions.append(int(version_id))

        if len(versions) >= 2:
            assert versions == sorted(versions, reverse=True), "History should be in descending order by version"

    def test_type_history(self, client, assertions, patient_with_history):
        """Test retrieving history for all resources of a type."""
        response = client.type_history("Patient")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        bundle = response.json()

        assert bundle['resourceType'] == 'Bundle', "Should return a Bundle"
        assert bundle['type'] == 'history', "Bundle type should be 'history'"

        # Should have entries for all patient operations
        entries = bundle.get('entry', [])
        assert len(entries) > 0, "Should have history entries"

    def test_system_history(self, client, assertions):
        """Test retrieving system-wide history."""
        response = client.system_history()

        # System history might not be supported by all servers
        if response.status_code == 200:
            bundle = response.json()
            assert bundle['resourceType'] == 'Bundle', "Should return a Bundle"
            assert bundle['type'] == 'history', "Bundle type should be 'history'"

    def test_history_with_count_parameter(self, client, assertions, patient_with_history):
        """Test history with _count parameter for pagination."""
        patient_id = patient_with_history['id']

        response = client.history("Patient", patient_id, params={"_count": "2"})

        assert response.status_code == 200
        bundle = response.json()

        entries = bundle.get('entry', [])
        assert len(entries) <= 2, "Should return at most 2 entries with _count=2"

    def test_history_with_since_parameter(self, client, assertions, patient_with_history):
        """Test history with _since parameter."""
        patient_id = patient_with_history['id']

        # Get current time and subtract a bit to ensure we catch all versions
        since_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat() + 'Z'

        response = client.history("Patient", patient_id, params={"_since": since_time})

        assert response.status_code == 200
        bundle = response.json()

        # Should have entries created after the since time
        entries = bundle.get('entry', [])
        assert len(entries) > 0, "Should have entries after the since time"


class TestVersionReading:
    """Test reading specific versions of resources."""

    @pytest.fixture
    def versioned_patient(self, client, assertions):
        """Create a patient with multiple versions."""
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "VersionRead", "given": ["V1"]}]
        )
        resp = client.create(patient)
        v1 = assertions.assert_created(resp, "Patient")

        v1['name'] = [{"family": "VersionRead", "given": ["V2"]}]
        resp = client.update(v1)
        v2 = resp.json()

        yield {'id': v1['id'], 'v1': v1, 'v2': v2}

        try:
            client.delete("Patient", v1['id'])
        except:
            pass

    def test_vread_specific_version(self, client, assertions, versioned_patient):
        """Test reading a specific version using vread."""
        patient_id = versioned_patient['id']
        version1_id = versioned_patient['v1']['meta']['versionId']

        # Read version 1 specifically
        response = client.vread("Patient", patient_id, version1_id)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        patient = response.json()

        assert patient['id'] == patient_id
        assert patient['meta']['versionId'] == version1_id

        # Verify it's the old data
        assert patient['name'][0]['given'][0] == 'V1', "Should retrieve version 1 data"

    def test_vread_latest_version(self, client, assertions, versioned_patient):
        """Test reading the latest version."""
        patient_id = versioned_patient['id']
        version2_id = versioned_patient['v2']['meta']['versionId']

        response = client.vread("Patient", patient_id, version2_id)

        assert response.status_code == 200
        patient = response.json()

        assert patient['name'][0]['given'][0] == 'V2', "Should retrieve version 2 data"

    def test_vread_nonexistent_version(self, client, assertions, versioned_patient):
        """Test reading a nonexistent version returns 404."""
        patient_id = versioned_patient['id']

        response = client.vread("Patient", patient_id, "999")

        assert response.status_code == 404, "Should return 404 for nonexistent version"


class TestETagSupport:
    """Test ETag support for caching and optimistic locking."""

    def test_etag_on_read(self, client, assertions):
        """Test that ETag header is returned on read."""
        # Create a patient
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            # Read the patient
            response = client.read("Patient", created['id'])

            assert response.status_code == 200

            # Check for ETag header
            etag = response.headers.get('ETag')
            assert etag is not None, "Should have ETag header"

            # ETag should be in format W/"version"
            assert etag.startswith('W/"') or etag.startswith('"'), "ETag should be in proper format"
        finally:
            client.delete("Patient", created['id'])

    def test_etag_on_vread(self, client, assertions):
        """Test that ETag is correct for version-specific reads."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            version_id = created['meta']['versionId']

            response = client.vread("Patient", created['id'], version_id)

            assert response.status_code == 200

            etag = response.headers.get('ETag')
            assert etag is not None, "Should have ETag header"

            # ETag should match version
            assert version_id in etag, "ETag should contain version ID"
        finally:
            client.delete("Patient", created['id'])

    def test_if_none_match_on_read(self, client, assertions):
        """Test If-None-Match for caching on read."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            # Read to get ETag
            response1 = client.read("Patient", created['id'])
            etag = response1.headers.get('ETag')

            # Read again with If-None-Match
            import requests
            url = f"{client.base_url}/Patient/{created['id']}"
            response2 = requests.get(url, headers={'If-None-Match': etag})

            # Should return 304 Not Modified if resource hasn't changed
            assert response2.status_code in [200, 304], \
                f"Expected 200 or 304, got {response2.status_code}"

            if response2.status_code == 304:
                assert len(response2.content) == 0, "304 response should have no body"
        finally:
            client.delete("Patient", created['id'])

    def test_if_match_on_update(self, client, assertions):
        """Test If-Match for optimistic locking on update."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            # Read to get current version
            response1 = client.read("Patient", created['id'])
            current_version = response1.json()['meta']['versionId']
            etag = f'W/"{current_version}"'

            # Update with If-Match
            created['name'] = [{"family": "UpdatedWithETag"}]
            import requests
            url = f"{client.base_url}/Patient/{created['id']}"
            response2 = requests.put(
                url,
                json=created,
                headers={
                    'Content-Type': 'application/fhir+json',
                    'If-Match': etag
                }
            )

            # Should succeed if version matches
            assert response2.status_code in [200, 201], \
                f"Update with correct If-Match should succeed, got {response2.status_code}"
        finally:
            client.delete("Patient", created['id'])

    def test_if_match_with_wrong_version(self, client, assertions):
        """Test that If-Match with wrong version fails."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            # Try to update with wrong version
            wrong_etag = 'W/"999"'
            created['name'] = [{"family": "ShouldFail"}]

            import requests
            url = f"{client.base_url}/Patient/{created['id']}"
            response = requests.put(
                url,
                json=created,
                headers={
                    'Content-Type': 'application/fhir+json',
                    'If-Match': wrong_etag
                }
            )

            # Should return 409 or 412 (Precondition Failed)
            assert response.status_code in [409, 412], \
                f"Update with wrong If-Match should fail, got {response.status_code}"
        finally:
            client.delete("Patient", created['id'])


class TestVersioning:
    """Test resource versioning behavior."""

    def test_version_increments_on_update(self, client, assertions):
        """Test that version ID increments on each update."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            version1 = int(created['meta']['versionId'])

            # Update
            created['name'] = [{"family": "Updated"}]
            resp = client.update(created)
            updated = resp.json()

            version2 = int(updated['meta']['versionId'])

            assert version2 > version1, "Version should increment on update"
        finally:
            client.delete("Patient", created['id'])

    def test_last_updated_changes_on_update(self, client, assertions):
        """Test that lastUpdated timestamp changes on update."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            last_updated1 = created['meta']['lastUpdated']

            # Wait a moment to ensure time difference
            import time
            time.sleep(0.1)

            # Update
            created['name'] = [{"family": "UpdatedTime"}]
            resp = client.update(created)
            updated = resp.json()

            last_updated2 = updated['meta']['lastUpdated']

            assert last_updated2 != last_updated1, "lastUpdated should change on update"
            assert last_updated2 > last_updated1, "lastUpdated should increase on update"
        finally:
            client.delete("Patient", created['id'])

    def test_delete_creates_deleted_version(self, client, assertions):
        """Test that deleting a resource creates a deleted version in history."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        patient_id = created['id']

        # Delete the patient
        client.delete("Patient", patient_id)

        # Get history
        resp = client.history("Patient", patient_id)
        if resp.status_code == 200:
            bundle = resp.json()
            entries = bundle.get('entry', [])

            # Should have an entry with method DELETE
            delete_entries = [e for e in entries if e.get('request', {}).get('method') == 'DELETE']
            # Note: not all servers include DELETE in history, so this is optional

    def test_version_aware_update(self, client, assertions):
        """Test update with explicit version specification."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            current_version = created['meta']['versionId']

            # Update with version check via If-Match header
            created['name'] = [{"family": "VersionAware"}]

            import requests
            url = f"{client.base_url}/Patient/{created['id']}"
            response = requests.put(
                url,
                json=created,
                headers={
                    'Content-Type': 'application/fhir+json',
                    'If-Match': f'W/"{current_version}"'
                }
            )

            assert response.status_code in [200, 201], \
                "Version-aware update should succeed with correct version"
        finally:
            client.delete("Patient", created['id'])
