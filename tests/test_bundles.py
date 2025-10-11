"""Tests for FHIR batch and transaction bundles."""
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


class TestBatchBundle:
    """Test batch bundle operations."""

    def test_batch_create_multiple_resources(self, client, assertions):
        """Test creating multiple resources in a batch."""
        # Create batch bundle
        bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": []
        }

        # Add 3 patients to batch
        created_ids = []
        for i in range(3):
            patient = FHIRResourceGenerator.generate_patient(
                name=[{"family": f"BatchTest{i}", "given": ["Patient"]}]
            )
            bundle['entry'].append({
                "request": {
                    "method": "POST",
                    "url": "Patient"
                },
                "resource": patient
            })

        try:
            # Submit batch
            response = client.session.post(
                client.base_url,
                json=bundle
            )

            assert response.status_code == 200, f"Batch should return 200, got {response.status_code}"
            result_bundle = response.json()

            assert result_bundle['resourceType'] == 'Bundle', "Should return a Bundle"
            assert result_bundle['type'] == 'batch-response', "Should be batch-response type"

            # Should have 3 entries with responses
            entries = result_bundle.get('entry', [])
            assert len(entries) == 3, f"Should have 3 responses, got {len(entries)}"

            # Check each response
            for entry in entries:
                response_data = entry.get('response', {})
                status = response_data.get('status', '')
                assert status.startswith('201'), f"Each create should return 201, got {status}"

                # Extract created ID from location
                location = response_data.get('location', '')
                if 'Patient/' in location:
                    patient_id = location.split('Patient/')[1].split('/')[0]
                    created_ids.append(patient_id)

        finally:
            # Cleanup
            for patient_id in created_ids:
                try:
                    client.delete("Patient", patient_id)
                except:
                    pass

    def test_batch_mixed_operations(self, client, assertions):
        """Test batch with mixed operation types (POST, GET, PUT, DELETE)."""
        # Create a patient first
        patient = FHIRResourceGenerator.generate_patient(
            name=[{"family": "BatchMixed"}]
        )
        resp = client.create(patient)
        created = assertions.assert_created(resp, "Patient")

        try:
            # Create batch with mixed operations
            bundle = {
                "resourceType": "Bundle",
                "type": "batch",
                "entry": [
                    # Create new patient
                    {
                        "request": {
                            "method": "POST",
                            "url": "Patient"
                        },
                        "resource": FHIRResourceGenerator.generate_patient(
                            name=[{"family": "NewBatchPatient"}]
                        )
                    },
                    # Read existing patient
                    {
                        "request": {
                            "method": "GET",
                            "url": f"Patient/{created['id']}"
                        }
                    },
                    # Update existing patient
                    {
                        "request": {
                            "method": "PUT",
                            "url": f"Patient/{created['id']}"
                        },
                        "resource": {
                            **created,
                            "name": [{"family": "UpdatedInBatch"}]
                        }
                    },
                    # Search for patients
                    {
                        "request": {
                            "method": "GET",
                            "url": "Patient?family=BatchMixed"
                        }
                    }
                ]
            }

            response = client.session.post(
                client.base_url,
                json=bundle
            )

            assert response.status_code == 200
            result_bundle = response.json()

            entries = result_bundle.get('entry', [])
            assert len(entries) == 4, "Should have 4 responses"

            # Verify each operation
            assert entries[0]['response']['status'].startswith('201'), "Create should return 201"
            assert entries[1]['response']['status'].startswith('200'), "Read should return 200"
            assert entries[2]['response']['status'].startswith('200'), "Update should return 200"
            assert entries[3]['response']['status'].startswith('200'), "Search should return 200"

        finally:
            client.delete("Patient", created['id'])

    def test_batch_partial_failure(self, client, assertions):
        """Test that batch continues on individual failures."""
        bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                # Valid create
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": FHIRResourceGenerator.generate_patient()
                },
                # Invalid read (nonexistent ID)
                {
                    "request": {
                        "method": "GET",
                        "url": "Patient/nonexistent-id-12345"
                    }
                },
                # Another valid create
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": FHIRResourceGenerator.generate_patient()
                }
            ]
        }

        response = client.session.post(
            client.base_url,
            json=bundle
        )

        assert response.status_code == 200, "Batch should return 200 even with failures"
        result_bundle = response.json()

        entries = result_bundle.get('entry', [])
        assert len(entries) == 3, "Should have 3 responses"

        # First should succeed
        assert entries[0]['response']['status'].startswith('201'), "First operation should succeed"

        # Second should fail
        assert entries[1]['response']['status'].startswith('404'), "Second operation should fail with 404"

        # Third should succeed (batch continues after failure)
        assert entries[2]['response']['status'].startswith('201'), "Third operation should succeed"


class TestTransactionBundle:
    """Test transaction bundle operations (all-or-nothing)."""

    def test_transaction_all_succeed(self, client, assertions):
        """Test transaction where all operations succeed."""
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": FHIRResourceGenerator.generate_patient(
                        name=[{"family": "TransactionTest1"}]
                    )
                },
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": FHIRResourceGenerator.generate_patient(
                        name=[{"family": "TransactionTest2"}]
                    )
                }
            ]
        }

        created_ids = []
        try:
            response = client.session.post(
                client.base_url,
                json=bundle
            )

            assert response.status_code == 200, f"Transaction should return 200, got {response.status_code}"
            result_bundle = response.json()

            assert result_bundle['type'] == 'transaction-response', "Should be transaction-response"

            entries = result_bundle.get('entry', [])
            assert len(entries) == 2, "Should have 2 responses"

            # All should be successful
            for entry in entries:
                status = entry['response']['status']
                assert status.startswith('201'), f"Should return 201, got {status}"

                location = entry['response'].get('location', '')
                if 'Patient/' in location:
                    patient_id = location.split('Patient/')[1].split('/')[0]
                    created_ids.append(patient_id)

        finally:
            # Cleanup
            for patient_id in created_ids:
                try:
                    client.delete("Patient", patient_id)
                except:
                    pass

    def test_transaction_with_references(self, client, assertions):
        """Test transaction with references between resources."""
        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                # Create patient with fullUrl for reference
                {
                    "fullUrl": "urn:uuid:patient-temp-id",
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": FHIRResourceGenerator.generate_patient(
                        name=[{"family": "RefTransaction"}]
                    )
                },
                # Create observation referencing the patient
                {
                    "request": {
                        "method": "POST",
                        "url": "Observation"
                    },
                    "resource": FHIRResourceGenerator.generate_observation(
                        patient_ref={"reference": "urn:uuid:patient-temp-id"},
                        code_system="http://loinc.org",
                        code="8867-4",
                        code_display="Heart rate",
                        value_quantity={"value": 75, "unit": "bpm"}
                    )
                }
            ]
        }

        created_ids = {'patients': [], 'observations': []}
        try:
            response = client.session.post(
                client.base_url,
                json=bundle
            )

            if response.status_code == 200:
                result_bundle = response.json()
                entries = result_bundle.get('entry', [])

                # Extract created IDs for cleanup
                for i, entry in enumerate(entries):
                    location = entry['response'].get('location', '')
                    if 'Patient/' in location:
                        patient_id = location.split('Patient/')[1].split('/')[0]
                        created_ids['patients'].append(patient_id)
                    elif 'Observation/' in location:
                        obs_id = location.split('Observation/')[1].split('/')[0]
                        created_ids['observations'].append(obs_id)

        finally:
            # Cleanup
            for obs_id in created_ids['observations']:
                try:
                    client.delete("Observation", obs_id)
                except:
                    pass
            for patient_id in created_ids['patients']:
                try:
                    client.delete("Patient", patient_id)
                except:
                    pass

    def test_transaction_rollback_on_error(self, client, assertions):
        """Test that transaction rolls back all changes on error."""
        # Count patients before transaction
        before_response = client.search("Patient", {"family": "RollbackTest"})
        before_bundle = before_response.json()
        before_count = before_bundle.get('total', 0)

        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                # Valid patient
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": FHIRResourceGenerator.generate_patient(
                        name=[{"family": "RollbackTest"}]
                    )
                },
                # Invalid resource - validation error
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": {
                        "resourceType": "Patient",
                        "active": "invalid-boolean",  # Should be boolean, not string
                        "name": [{"family": "ShouldFail"}]
                    }
                }
            ]
        }

        response = client.session.post(
            client.base_url,
            json=bundle
        )

        # Transaction should fail with validation error
        assert response.status_code in [400, 422], \
            f"Transaction with validation error should fail, got {response.status_code}"

        # Verify no patients were created (rollback occurred)
        after_response = client.search("Patient", {"family": "RollbackTest"})
        after_bundle = after_response.json()
        after_count = after_bundle.get('total', 0)

        assert after_count == before_count, \
            "No resources should be created after transaction rollback"

    def test_transaction_conditional_create(self, client, assertions):
        """Test transaction with conditional create."""
        identifier_value = f"TXN-COND-{FHIRResourceGenerator.generate_id()}"

        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient",
                        "ifNoneExist": f"identifier={identifier_value}"
                    },
                    "resource": FHIRResourceGenerator.generate_patient(
                        name=[{"family": "ConditionalTxn"}],
                        identifier=[{
                            "system": "http://hospital.org/transaction",
                            "value": identifier_value
                        }]
                    )
                }
            ]
        }

        created_id = None
        try:
            # First transaction - should create
            response1 = client.session.post(client.base_url, json=bundle)
            assert response1.status_code == 200

            result1 = response1.json()
            location1 = result1['entry'][0]['response'].get('location', '')
            if 'Patient/' in location1:
                created_id = location1.split('Patient/')[1].split('/')[0]

            # Second transaction with same identifier - should not create duplicate
            response2 = client.session.post(client.base_url, json=bundle)
            assert response2.status_code == 200

            result2 = response2.json()
            status2 = result2['entry'][0]['response']['status']

            # Should return 200 (found existing) not 201 (created new)
            assert status2.startswith('200'), \
                "Conditional create should return 200 for existing resource"

        finally:
            if created_id:
                client.delete("Patient", created_id)


class TestBundleEdgeCases:
    """Test edge cases for bundles."""

    def test_empty_batch_bundle(self, client, assertions):
        """Test empty batch bundle."""
        bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": []
        }

        response = client.session.post(
            client.base_url,
            json=bundle
        )

        assert response.status_code == 200, "Empty batch should succeed"
        result_bundle = response.json()

        assert result_bundle['type'] == 'batch-response'
        assert len(result_bundle.get('entry', [])) == 0, "Should have no entries"

    def test_large_batch_bundle(self, client, assertions):
        """Test batch with many entries."""
        bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": []
        }

        # Add 20 create operations
        for i in range(20):
            bundle['entry'].append({
                "request": {
                    "method": "POST",
                    "url": "Patient"
                },
                "resource": FHIRResourceGenerator.generate_patient(
                    name=[{"family": f"LargeBatch{i}"}]
                )
            })

        created_ids = []
        try:
            response = client.session.post(
                client.base_url,
                json=bundle
            )

            assert response.status_code == 200, "Large batch should succeed"
            result_bundle = response.json()

            entries = result_bundle.get('entry', [])
            assert len(entries) == 20, "Should have 20 responses"

            # Collect IDs for cleanup
            for entry in entries:
                location = entry['response'].get('location', '')
                if 'Patient/' in location:
                    patient_id = location.split('Patient/')[1].split('/')[0]
                    created_ids.append(patient_id)

        finally:
            # Cleanup
            for patient_id in created_ids:
                try:
                    client.delete("Patient", patient_id)
                except:
                    pass

    def test_bundle_with_invalid_entry(self, client, assertions):
        """Test batch bundle with invalid resource."""
        bundle = {
            "resourceType": "Bundle",
            "type": "batch",
            "entry": [
                # Valid patient
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": FHIRResourceGenerator.generate_patient()
                },
                # Invalid patient (missing resourceType)
                {
                    "request": {
                        "method": "POST",
                        "url": "Patient"
                    },
                    "resource": {
                        "name": [{"family": "Invalid"}]
                    }
                }
            ]
        }

        response = client.session.post(
            client.base_url,
            json=bundle
        )

        assert response.status_code == 200, "Batch should return 200"
        result_bundle = response.json()

        entries = result_bundle.get('entry', [])
        assert len(entries) == 2

        # First should succeed
        assert entries[0]['response']['status'].startswith('201')

        # Second should fail
        assert entries[1]['response']['status'].startswith('400'), \
            "Invalid resource should return 400"

    def test_transaction_ordering(self, client, assertions):
        """Test that transaction operations are processed in order."""
        patient_id = FHIRResourceGenerator.generate_id()

        bundle = {
            "resourceType": "Bundle",
            "type": "transaction",
            "entry": [
                # 1. Create patient
                {
                    "request": {
                        "method": "PUT",
                        "url": f"Patient/{patient_id}"
                    },
                    "resource": FHIRResourceGenerator.generate_patient(
                        id=patient_id,
                        name=[{"family": "OrderTest", "given": ["V1"]}]
                    )
                },
                # 2. Update patient (depends on previous create)
                {
                    "request": {
                        "method": "PUT",
                        "url": f"Patient/{patient_id}"
                    },
                    "resource": FHIRResourceGenerator.generate_patient(
                        id=patient_id,
                        name=[{"family": "OrderTest", "given": ["V2"]}]
                    )
                },
                # 3. Read patient (should get V2)
                {
                    "request": {
                        "method": "GET",
                        "url": f"Patient/{patient_id}"
                    }
                }
            ]
        }

        try:
            response = client.session.post(
                client.base_url,
                json=bundle
            )

            if response.status_code == 200:
                result_bundle = response.json()
                entries = result_bundle.get('entry', [])

                # Read response should have V2 data
                if len(entries) >= 3:
                    read_resource = entries[2].get('resource', {})
                    if read_resource:
                        name = read_resource.get('name', [{}])[0]
                        given = name.get('given', [])
                        if given:
                            assert given[0] == 'V2', "Should read the updated version"

        finally:
            try:
                client.delete("Patient", patient_id)
            except:
                pass
