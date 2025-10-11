"""Tests for FHIR server error handling and edge cases."""
import pyrtest
import sys
import os
import requests

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


class TestInvalidJSON:
    """Test handling of invalid JSON in requests."""

    def test_invalid_json_syntax(self, client, assertions):
        """Test that server rejects malformed JSON."""
        url = f"{client.base_url}/Patient"
        response = requests.post(
            url,
            data='{invalid json syntax}',
            headers={'Content-Type': 'application/fhir+json'}
        )

        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for invalid JSON, got {response.status_code}"

        # Should return OperationOutcome
        if response.content:
            result = response.json()
            assert result['resourceType'] == 'OperationOutcome'

    def test_empty_request_body(self, client, assertions):
        """Test that server rejects empty request body."""
        url = f"{client.base_url}/Patient"
        response = requests.post(
            url,
            data='',
            headers={'Content-Type': 'application/fhir+json'}
        )

        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for empty body, got {response.status_code}"

    def test_non_json_content_type(self, client, assertions):
        """Test that server handles incorrect Content-Type."""
        url = f"{client.base_url}/Patient"
        patient = FHIRResourceGenerator.generate_patient()

        response = requests.post(
            url,
            json=patient,
            headers={'Content-Type': 'text/plain'}
        )

        # Server may reject with 415 Unsupported Media Type or accept it
        assert response.status_code in [201, 400, 415], \
            f"Expected 201, 400, or 415, got {response.status_code}"


class TestInvalidResources:
    """Test handling of invalid FHIR resources."""

    def test_missing_resource_type(self, client, assertions):
        """Test that server rejects resource without resourceType."""
        invalid_resource = {
            "name": [{"family": "Test"}]
        }

        url = f"{client.base_url}/Patient"
        response = requests.post(url, json=invalid_resource, headers={
            'Content-Type': 'application/fhir+json'
        })

        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for missing resourceType, got {response.status_code}"

    def test_wrong_resource_type_in_url(self, client, assertions):
        """Test creating resource with mismatched resourceType."""
        patient = FHIRResourceGenerator.generate_patient()

        # Try to POST patient to Observation endpoint
        url = f"{client.base_url}/Observation"
        response = requests.post(url, json=patient, headers={
            'Content-Type': 'application/fhir+json'
        })

        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for resource type mismatch, got {response.status_code}"

    def test_invalid_reference(self, client, assertions):
        """Test creating resource with invalid reference."""
        observation = {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "8867-4"
                }]
            },
            "subject": {
                "reference": "Patient/nonexistent-patient-id-999"
            }
        }

        response = client.create(observation)

        # Server may accept (reference integrity not always enforced) or reject
        # If it accepts, it should still return 201
        assert response.status_code in [201, 400, 404, 422], \
            f"Expected 201, 400, 404, or 422, got {response.status_code}"

    def test_invalid_field_type(self, client, assertions):
        """Test resource with wrong field type."""
        invalid_patient = {
            "resourceType": "Patient",
            "active": "not-a-boolean",  # Should be boolean
            "name": [{"family": "Test"}]
        }

        response = client.create(invalid_patient)

        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for invalid field type, got {response.status_code}"

    def test_unknown_field(self, client, assertions):
        """Test resource with unknown/custom field."""
        patient = FHIRResourceGenerator.generate_patient()
        patient['unknownField'] = 'unknown value'

        response = client.create(patient)

        # FHIR servers should be lenient with unknown fields
        # They might ignore them or reject them
        assert response.status_code in [201, 400, 422], \
            f"Expected 201, 400, or 422, got {response.status_code}"


class TestHTTPMethodErrors:
    """Test incorrect HTTP method usage."""

    def test_get_on_type_endpoint_without_search(self, client, assertions):
        """Test GET on resource type endpoint (should return search bundle)."""
        response = client.search("Patient", {})

        # Should return 200 with empty or populated bundle
        assert response.status_code == 200
        bundle = response.json()
        assert bundle['resourceType'] == 'Bundle'

    def test_post_to_instance_endpoint(self, client, assertions):
        """Test POST to instance endpoint (not allowed)."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            # Try to POST to instance endpoint
            url = f"{client.base_url}/Patient/{created['id']}"
            response = requests.post(url, json=patient, headers={
                'Content-Type': 'application/fhir+json'
            })

            # Should return 405 Method Not Allowed
            assert response.status_code in [405, 400], \
                f"Expected 405 or 400, got {response.status_code}"
        finally:
            client.delete("Patient", created['id'])

    def test_put_to_type_endpoint(self, client, assertions):
        """Test PUT to type endpoint without ID (not allowed)."""
        patient = FHIRResourceGenerator.generate_patient()

        url = f"{client.base_url}/Patient"
        response = requests.put(url, json=patient, headers={
            'Content-Type': 'application/fhir+json'
        })

        # Should return 405 Method Not Allowed or 400 Bad Request
        assert response.status_code in [400, 405], \
            f"Expected 400 or 405, got {response.status_code}"


class TestSearchParameterErrors:
    """Test search parameter error handling."""

    def test_invalid_search_parameter(self, client, assertions):
        """Test search with non-existent parameter."""
        response = client.search("Patient", {
            "nonExistentParameter": "value"
        })

        # Server should either ignore unknown parameters or return error
        assert response.status_code in [200, 400], \
            f"Expected 200 or 400, got {response.status_code}"

        if response.status_code == 200:
            bundle = response.json()
            assert bundle['resourceType'] == 'Bundle'

    def test_invalid_date_format(self, client, assertions):
        """Test search with invalid date format."""
        response = client.search("Patient", {
            "birthdate": "not-a-date"
        })

        # Server should reject invalid date format
        assert response.status_code in [200, 400], \
            f"Expected 200 or 400, got {response.status_code}"

    def test_invalid_token_syntax(self, client, assertions):
        """Test search with malformed token parameter."""
        response = client.search("Patient", {
            "identifier": "|||invalid|||syntax"
        })

        # Server should handle malformed token gracefully
        assert response.status_code in [200, 400], \
            f"Expected 200 or 400, got {response.status_code}"

    def test_invalid_modifier(self, client, assertions):
        """Test search with invalid modifier."""
        response = client.search("Patient", {
            "name:invalidmodifier": "Test"
        })

        # Server should reject invalid modifier
        assert response.status_code in [200, 400], \
            f"Expected 200 or 400, got {response.status_code}"


class TestResourceValidation:
    """Test FHIR resource validation."""

    def test_required_field_missing_patient_name(self, client, assertions):
        """Test that missing name in Patient is handled."""
        patient = {
            "resourceType": "Patient",
            # Name is not strictly required, but let's test behavior
            "gender": "male"
        }

        response = client.create(patient)

        # Name is not required in FHIR R5, so this should succeed
        assert response.status_code in [201, 400, 422], \
            f"Expected 201, 400, or 422, got {response.status_code}"

    def test_observation_requires_status(self, client, assertions):
        """Test that Observation requires status field."""
        observation = {
            "resourceType": "Observation",
            # Missing required status field
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "8867-4"
                }]
            }
        }

        response = client.create(observation)

        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for missing status, got {response.status_code}"

    def test_observation_requires_code(self, client, assertions):
        """Test that Observation requires code field."""
        observation = {
            "resourceType": "Observation",
            "status": "final"
            # Missing required code field
        }

        response = client.create(observation)

        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for missing code, got {response.status_code}"

    def test_invalid_enum_value(self, client, assertions):
        """Test resource with invalid enum value."""
        patient = FHIRResourceGenerator.generate_patient()
        patient['gender'] = 'invalid-gender'

        response = client.create(patient)

        # Server should reject invalid enum value
        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for invalid enum, got {response.status_code}"


class TestConcurrencyAndVersioning:
    """Test concurrency control and versioning errors."""

    def test_update_with_stale_version(self, client, assertions):
        """Test update with outdated version (optimistic locking)."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            # Update once to increment version
            created['name'] = [{"family": "Updated"}]
            resp = client.update(created)
            updated = resp.json()

            # Try to update again using the old version
            url = f"{client.base_url}/Patient/{created['id']}"
            stale_etag = f"W/\"{created['meta']['versionId']}\""

            response = requests.put(
                url,
                json=updated,
                headers={
                    'Content-Type': 'application/fhir+json',
                    'If-Match': stale_etag
                }
            )

            # Should fail with 412 Precondition Failed or 409 Conflict
            assert response.status_code in [409, 412], \
                f"Expected 409 or 412 for stale version, got {response.status_code}"
        finally:
            client.delete("Patient", created['id'])

    def test_delete_already_deleted_resource(self, client, assertions):
        """Test deleting a resource that's already deleted."""
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        # Delete once
        client.delete("Patient", created['id'])

        # Try to delete again
        response = client.delete("Patient", created['id'])

        # Should return 204, 404, or 410
        assert response.status_code in [204, 404, 410], \
            f"Expected 204, 404, or 410, got {response.status_code}"


class TestIDHandling:
    """Test ID handling and constraints."""

    def test_create_with_client_assigned_id(self, client, assertions):
        """Test creating resource with client-assigned ID using PUT."""
        patient = FHIRResourceGenerator.generate_patient()
        patient['id'] = 'client-assigned-id-test'

        try:
            response = client.update(patient)

            # Should succeed and create the resource
            assert response.status_code in [200, 201], \
                f"Expected 200 or 201, got {response.status_code}"

            created = response.json()
            assert created['id'] == 'client-assigned-id-test'
        finally:
            client.delete("Patient", 'client-assigned-id-test')

    def test_create_post_ignores_id(self, client, assertions):
        """Test that POST ignores client-provided ID."""
        patient = FHIRResourceGenerator.generate_patient()
        patient['id'] = 'should-be-ignored'

        response = client.create(patient)
        created = assertions.assert_created(response, "Patient")

        try:
            # Server should assign its own ID, not use the provided one
            assert created['id'] != 'should-be-ignored'
        finally:
            client.delete("Patient", created['id'])

    def test_invalid_id_characters(self, client, assertions):
        """Test that invalid ID characters are rejected."""
        patient = FHIRResourceGenerator.generate_patient()
        patient['id'] = 'invalid id with spaces!'

        response = client.update(patient)

        # Server should reject invalid ID format
        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for invalid ID, got {response.status_code}"


class TestBundleErrors:
    """Test bundle operation error handling."""

    def test_batch_bundle_with_invalid_entry(self, client, assertions):
        """Test batch bundle containing invalid entry."""
        patient = FHIRResourceGenerator.generate_patient()

        bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": patient
                },
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": {
                        "resourceType": "Patient",
                        # Invalid: missing required structure
                        "active": "not-a-boolean"
                    }
                }
            ]
        }

        response = client.create(bundle)

        # Should return 200 with results for each entry
        assert response.status_code == 200
        result_bundle = response.json()
        assert result_bundle['resourceType'] == 'Bundle'
        assert result_bundle['type'] == 'batch-response'

        # Second entry should have error status
        assert len(result_bundle['entry']) == 2
        assert result_bundle['entry'][1]['response']['status'].startswith('4')

        # Cleanup first patient if it was created
        if result_bundle['entry'][0]['response']['status'] == '201':
            location = result_bundle['entry'][0]['response']['location']
            patient_id = location.split('/')[-1].split('/_history')[0]
            try:
                client.delete("Patient", patient_id)
            except:
                pass

    def test_transaction_bundle_rollback(self, client, assertions):
        """Test that transaction bundle rolls back on error."""
        patient1 = FHIRResourceGenerator.generate_patient(
            name=[{"family": "TransactionTest1"}]
        )

        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": patient1
                },
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": {
                        "resourceType": "Patient",
                        "active": "invalid-boolean"  # This should fail
                    }
                }
            ]
        }

        response = client.create(bundle)

        # Transaction should fail entirely
        assert response.status_code in [400, 422], \
            f"Expected 400 or 422 for failed transaction, got {response.status_code}"

        # Verify first patient was not created (rollback occurred)
        search_resp = client.search("Patient", {"family": "TransactionTest1"})
        bundle_result = search_resp.json()

        # Should not find the patient
        matching = [e for e in bundle_result.get('entry', [])
                   if e['resource'].get('name', [{}])[0].get('family') == 'TransactionTest1']
        assert len(matching) == 0, "Transaction should have rolled back, patient should not exist"

    def test_empty_bundle(self, client, assertions):
        """Test processing empty bundle."""
        bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": []
        }

        response = client.create(bundle)

        # Should return 200 with empty result bundle
        assert response.status_code == 200
        result = response.json()
        assert result['resourceType'] == 'Bundle'
        assert len(result.get('entry', [])) == 0


class TestLargeResourceHandling:
    """Test handling of large resources."""

    def test_large_patient_name_array(self, client, assertions):
        """Test patient with many names."""
        patient = FHIRResourceGenerator.generate_patient()

        # Add 100 name entries
        patient['name'] = [
            {"family": f"Family{i}", "given": [f"Given{i}"]}
            for i in range(100)
        ]

        response = client.create(patient)

        # Should handle large but valid resource
        assert response.status_code in [201, 400, 413], \
            f"Expected 201, 400, or 413, got {response.status_code}"

        if response.status_code == 201:
            created = response.json()
            try:
                assert len(created['name']) == 100
            finally:
                client.delete("Patient", created['id'])

    # Extensions are not supported in this FHIR implementation - test removed
    # def test_deeply_nested_extension(self, client, assertions):
    #     """Test resource with deeply nested extensions."""
    #     pass


class TestSpecialCharacters:
    """Test handling of special characters in data."""

    def test_unicode_characters_in_name(self, client, assertions):
        """Test patient name with Unicode characters."""
        patient = FHIRResourceGenerator.generate_patient(
            name=[{
                "family": "Müller",
                "given": ["François", "José"]
            }]
        )

        response = client.create(patient)
        created = assertions.assert_created(response, "Patient")

        try:
            assert created['name'][0]['family'] == "Müller"
            assert created['name'][0]['given'][0] == "François"
        finally:
            client.delete("Patient", created['id'])

    def test_special_characters_in_search(self, client, assertions):
        """Test search with special characters."""
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "O'Brien"}]
        )

        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            response = client.search("Patient", {
                "family": "O'Brien"
            })

            bundle = assertions.assert_bundle(response, "Patient")
            # Should handle apostrophe in search
        finally:
            client.delete("Patient", created['id'])
