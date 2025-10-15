"""
Comprehensive tests for FHIR R5 composite search parameters on Observations.

Tests three types of composite parameters:
1. code-value-quantity: Combines code with quantity value
2. code-value-concept: Combines code with codeable concept value  
3. component-code-value-quantity: Combines component code with component quantity value
"""

import pytest
from utils.fhir_client import FHIRClient
from fixtures.resource_generators import FHIRResourceGenerator
from utils.assertions import FHIRAssertions


class TestCodeValueQuantityComposite:
    """Test code-value-quantity composite search parameter."""

    @pytest.fixture
    def test_observations(self, client, assertions):
        """Create blood pressure observations with varying values."""
        observations = []

        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")
        patient_ref = FHIRResourceGenerator.generate_reference("Patient", created_patient['id'])

        # Observation 1: High systolic BP (180 mmHg)
        obs1 = FHIRResourceGenerator.generate_observation(
            patient_ref=patient_ref,
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

        # Observation 2: Normal systolic BP (120 mmHg)
        obs2 = FHIRResourceGenerator.generate_observation(
            patient_ref=patient_ref,
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

        # Observation 3: Different code (diastolic BP, 90 mmHg)
        obs3 = FHIRResourceGenerator.generate_observation(
            patient_ref=patient_ref,
            code_system="http://loinc.org",
            code="8462-4",
            code_display="Diastolic blood pressure",
            value_quantity={
                "value": 90,
                "unit": "mmHg",
                "system": "http://unitsofmeasure.org",
                "code": "mm[Hg]"
            }
        )
        resp = client.create(obs3)
        observations.append(assertions.assert_created(resp, "Observation"))

        # Observation 4: Systolic BP without system (150 mmHg)
        obs4 = FHIRResourceGenerator.generate_observation(
            patient_ref=patient_ref,
            code="8480-6",
            code_display="Systolic blood pressure",
            value_quantity={
                "value": 150,
                "unit": "mmHg"
            }
        )
        resp = client.create(obs4)
        observations.append(assertions.assert_created(resp, "Observation"))

        return observations

    def test_code_value_quantity_gt(self, client, assertions, test_observations):
        """Test composite search with greater than prefix."""
        # Search for systolic BP > 150
        response = client.search("Observation", {
            "code-value-quantity": "http://loinc.org|8480-6$gt150"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 1  # Only obs1 (180) should match
        assert bundle["entry"][0]["resource"]["valueQuantity"]["value"] == 180

    def test_code_value_quantity_lt(self, client, assertions, test_observations):
        """Test composite search with less than prefix."""
        # Search for systolic BP < 150
        response = client.search("Observation", {
            "code-value-quantity": "http://loinc.org|8480-6$lt150"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 1  # Only obs2 (120) should match
        assert bundle["entry"][0]["resource"]["valueQuantity"]["value"] == 120

    def test_code_value_quantity_ge(self, client, assertions, test_observations):
        """Test composite search with greater or equal prefix."""
        # Search for systolic BP >= 150
        response = client.search("Observation", {
            "code-value-quantity": "http://loinc.org|8480-6$ge150"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should match obs1 (180) and obs4 (150)
        assert bundle["total"] >= 2

    def test_code_value_quantity_eq(self, client, assertions, test_observations):
        """Test composite search with exact match (default)."""
        # Search for systolic BP = 120
        response = client.search("Observation", {
            "code-value-quantity": "http://loinc.org|8480-6$120"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 1
        assert bundle["entry"][0]["resource"]["valueQuantity"]["value"] == 120

    def test_code_value_quantity_without_system(self, client, assertions, test_observations):
        """Test composite search without code system."""
        # Search without system - should match all systolic BP > 140
        response = client.search("Observation", {
            "code-value-quantity": "8480-6$gt140"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should match obs1 (180) and obs4 (150)
        assert bundle["total"] >= 2

    def test_code_value_quantity_no_match_wrong_code(self, client, assertions, test_observations):
        """Test that wrong code returns no results."""
        # Search for glucose > 100 (code doesn't exist in our data)
        response = client.search("Observation", {
            "code-value-quantity": "http://loinc.org|2339-0$gt100"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 0

    def test_code_value_quantity_no_match_value_out_of_range(self, client, assertions, test_observations):
        """Test that out-of-range value returns no results."""
        # Search for systolic BP > 200 (none exist)
        response = client.search("Observation", {
            "code-value-quantity": "http://loinc.org|8480-6$gt200"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 0


class TestCodeValueConceptComposite:
    """Test code-value-concept composite search parameter."""

    @pytest.fixture
    def test_observations(self, client, assertions):
        """Create observations with codeable concept values."""
        observations = []

        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")
        patient_ref = FHIRResourceGenerator.generate_reference("Patient", created_patient['id'])

        # Observation 1: Interpretation = High
        obs1 = FHIRResourceGenerator.generate_observation(
            patient_ref=patient_ref,
            code_system="http://loinc.org",
            code="8480-6",
            code_display="Systolic blood pressure",
            value_codeable_concept={
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                    "code": "H",
                    "display": "High"
                }]
            }
        )
        resp = client.create(obs1)
        observations.append(assertions.assert_created(resp, "Observation"))

        # Observation 2: Interpretation = Normal
        obs2 = FHIRResourceGenerator.generate_observation(
            patient_ref=patient_ref,
            code_system="http://loinc.org",
            code="8480-6",
            code_display="Systolic blood pressure",
            value_codeable_concept={
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                    "code": "N",
                    "display": "Normal"
                }]
            }
        )
        resp = client.create(obs2)
        observations.append(assertions.assert_created(resp, "Observation"))

        # Observation 3: Different observation code, value = High
        obs3 = FHIRResourceGenerator.generate_observation(
            patient_ref=patient_ref,
            code_system="http://loinc.org",
            code="8462-4",
            code_display="Diastolic blood pressure",
            value_codeable_concept={
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                    "code": "H",
                    "display": "High"
                }]
            }
        )
        resp = client.create(obs3)
        observations.append(assertions.assert_created(resp, "Observation"))

        return observations

    def test_code_value_concept_with_systems(self, client, assertions, test_observations):
        """Test composite search with both code and value systems."""
        # Search for systolic BP with High interpretation
        response = client.search("Observation", {
            "code-value-concept": "http://loinc.org|8480-6$http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation|H"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 1
        assert bundle["entry"][0]["resource"]["code"]["coding"][0]["code"] == "8480-6"

    def test_code_value_concept_code_only(self, client, assertions, test_observations):
        """Test composite search with code only (no value system)."""
        # Search for systolic BP with Normal interpretation (no value system)
        response = client.search("Observation", {
            "code-value-concept": "http://loinc.org|8480-6$N"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 1

    def test_code_value_concept_no_systems(self, client, assertions, test_observations):
        """Test composite search without any systems."""
        # Search without systems
        response = client.search("Observation", {
            "code-value-concept": "8480-6$H"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 1


class TestComponentCodeValueQuantityComposite:
    """Test component-code-value-quantity composite search parameter."""

    @pytest.fixture
    def test_observations(self, client, assertions):
        """Create blood pressure observations with components."""
        observations = []

        # Create patient
        patient = FHIRResourceGenerator.generate_patient()
        resp = client.create(patient)
        created_patient = assertions.assert_created(resp, "Patient")
        patient_ref = FHIRResourceGenerator.generate_reference("Patient", created_patient['id'])

        # Observation 1: BP with high systolic component (180/90)
        obs1 = {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "85354-9",
                    "display": "Blood pressure panel"
                }]
            },
            "subject": patient_ref,
            "component": [
                {
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "8480-6",
                            "display": "Systolic blood pressure"
                        }]
                    },
                    "valueQuantity": {
                        "value": 180,
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]"
                    }
                },
                {
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "8462-4",
                            "display": "Diastolic blood pressure"
                        }]
                    },
                    "valueQuantity": {
                        "value": 90,
                        "unit": "mmHg",
                        "system": "http://unitsofmeasure.org",
                        "code": "mm[Hg]"
                    }
                }
            ]
        }
        resp = client.create(obs1)
        observations.append(assertions.assert_created(resp, "Observation"))

        # Observation 2: BP with normal systolic component (120/80)
        obs2 = {
            "resourceType": "Observation",
            "status": "final",
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "85354-9",
                    "display": "Blood pressure panel"
                }]
            },
            "subject": patient_ref,
            "component": [
                {
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "8480-6",
                            "display": "Systolic blood pressure"
                        }]
                    },
                    "valueQuantity": {
                        "value": 120,
                        "unit": "mmHg"
                    }
                },
                {
                    "code": {
                        "coding": [{
                            "system": "http://loinc.org",
                            "code": "8462-4",
                            "display": "Diastolic blood pressure"
                        }]
                    },
                    "valueQuantity": {
                        "value": 80,
                        "unit": "mmHg"
                    }
                }
            ]
        }
        resp = client.create(obs2)
        observations.append(assertions.assert_created(resp, "Observation"))

        return observations

    def test_component_code_value_quantity_gt(self, client, assertions, test_observations):
        """Test component composite search with greater than."""
        # Search for BP panels with systolic component > 150
        response = client.search("Observation", {
            "component-code-value-quantity": "http://loinc.org|8480-6$gt150"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 1
        # Verify it has the high systolic component
        comp = bundle["entry"][0]["resource"]["component"]
        systolic = [c for c in comp if c["code"]["coding"][0]["code"] == "8480-6"][0]
        assert systolic["valueQuantity"]["value"] == 180

    def test_component_code_value_quantity_lt(self, client, assertions, test_observations):
        """Test component composite search with less than."""
        # Search for BP panels with systolic component < 150
        response = client.search("Observation", {
            "component-code-value-quantity": "http://loinc.org|8480-6$lt150"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 1
        # Verify it has the normal systolic component
        comp = bundle["entry"][0]["resource"]["component"]
        systolic = [c for c in comp if c["code"]["coding"][0]["code"] == "8480-6"][0]
        assert systolic["valueQuantity"]["value"] == 120

    def test_component_code_value_quantity_diastolic(self, client, assertions, test_observations):
        """Test component search on diastolic component."""
        # Search for BP panels with diastolic component > 85
        response = client.search("Observation", {
            "component-code-value-quantity": "http://loinc.org|8462-4$gt85"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        assert bundle["total"] == 1
        # Verify it has the high diastolic component
        comp = bundle["entry"][0]["resource"]["component"]
        diastolic = [c for c in comp if c["code"]["coding"][0]["code"] == "8462-4"][0]
        assert diastolic["valueQuantity"]["value"] == 90

    def test_component_code_value_quantity_no_system(self, client, assertions, test_observations):
        """Test component search without code system."""
        # Search without system
        response = client.search("Observation", {
            "component-code-value-quantity": "8480-6$ge120"
        })

        bundle = assertions.assert_bundle(response, "Observation")
        # Should match both observations
        assert bundle["total"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
