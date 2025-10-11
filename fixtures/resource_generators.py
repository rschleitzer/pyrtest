"""FHIR R5 resource generators for testing."""
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from faker import Faker

fake = Faker()


class FHIRResourceGenerator:
    """Generate valid FHIR R5 resources for testing."""

    @staticmethod
    def generate_id() -> str:
        """Generate a unique resource ID."""
        return str(uuid.uuid4())

    @staticmethod
    def generate_identifier(system: Optional[str] = None, value: Optional[str] = None) -> Dict[str, str]:
        """Generate an identifier."""
        return {
            "system": system or f"http://hospital.org/identifiers/{fake.word()}",
            "value": value or fake.bothify(text='???-####-####')
        }

    @staticmethod
    def generate_human_name(
        family: Optional[str] = None,
        given: Optional[List[str]] = None,
        use: str = "official"
    ) -> Dict[str, Any]:
        """Generate a HumanName."""
        return {
            "use": use,
            "family": family or fake.last_name(),
            "given": given or [fake.first_name()]
        }

    @staticmethod
    def generate_address(
        line: Optional[List[str]] = None,
        city: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate an Address."""
        return {
            "use": "home",
            "type": "physical",
            "line": line or [fake.street_address()],
            "city": city or fake.city(),
            "postalCode": postal_code or fake.postcode(),
            "country": country or fake.country_code()
        }

    @staticmethod
    def generate_contact_point(
        system: str = "phone",
        value: Optional[str] = None,
        use: str = "mobile"
    ) -> Dict[str, str]:
        """Generate a ContactPoint."""
        if not value:
            value = fake.phone_number() if system == "phone" else fake.email()
        return {
            "system": system,
            "value": value,
            "use": use
        }

    @staticmethod
    def generate_reference(resource_type: str, resource_id: str, display: Optional[str] = None) -> Dict[str, str]:
        """Generate a Reference."""
        ref = {"reference": f"{resource_type}/{resource_id}"}
        if display:
            ref["display"] = display
        return ref

    @staticmethod
    def generate_codeable_concept(
        system: str,
        code: str,
        display: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a CodeableConcept."""
        concept = {
            "coding": [{
                "system": system,
                "code": code
            }]
        }
        if display:
            concept["coding"][0]["display"] = display
        return concept

    @staticmethod
    def generate_patient(**overrides) -> Dict[str, Any]:
        """Generate a valid Patient resource.

        Args:
            **overrides: Override any field in the generated patient

        Returns:
            Patient resource dictionary
        """
        patient = {
            "resourceType": "Patient",
            "identifier": [FHIRResourceGenerator.generate_identifier()],
            "name": [FHIRResourceGenerator.generate_human_name()],
            "gender": fake.random_element(["male", "female", "other", "unknown"]),
            "birthDate": fake.date_of_birth(minimum_age=0, maximum_age=100).isoformat(),
            "address": [FHIRResourceGenerator.generate_address()],
            "telecom": [
                FHIRResourceGenerator.generate_contact_point("phone"),
                FHIRResourceGenerator.generate_contact_point("email", use="home")
            ],
            "active": True
        }

        # Merge overrides
        patient.update(overrides)
        return patient

    @staticmethod
    def generate_practitioner(**overrides) -> Dict[str, Any]:
        """Generate a valid Practitioner resource.

        Args:
            **overrides: Override any field

        Returns:
            Practitioner resource dictionary
        """
        practitioner = {
            "resourceType": "Practitioner",
            "identifier": [FHIRResourceGenerator.generate_identifier(
                system="http://hl7.org/fhir/sid/us-npi"
            )],
            "name": [FHIRResourceGenerator.generate_human_name()],
            "telecom": [FHIRResourceGenerator.generate_contact_point("phone", use="work")],
            "address": [FHIRResourceGenerator.generate_address()],
            "gender": fake.random_element(["male", "female", "other", "unknown"]),
            "active": True,
            "qualification": [{
                "code": FHIRResourceGenerator.generate_codeable_concept(
                    "http://terminology.hl7.org/CodeSystem/v2-0360",
                    "MD",
                    "Doctor of Medicine"
                )
            }]
        }

        practitioner.update(overrides)
        return practitioner

    @staticmethod
    def generate_observation(
        patient_ref: Optional[Dict[str, str]] = None,
        code_system: str = "http://loinc.org",
        code: str = "8867-4",
        code_display: str = "Heart rate",
        value_quantity: Optional[Dict[str, Any]] = None,
        value_codeable_concept: Optional[Dict[str, Any]] = None,
        value_string: Optional[str] = None,
        **overrides
    ) -> Dict[str, Any]:
        """Generate a valid Observation resource.

        Args:
            patient_ref: Reference to Patient (will generate if not provided)
            code_system: Code system for observation code
            code: Observation code
            code_display: Display text for code
            value_quantity: Value with unit (e.g., {"value": 80, "unit": "beats/minute"})
            value_codeable_concept: CodeableConcept value (e.g., {"coding": [...]})
            value_string: String value
            **overrides: Override any field

        Returns:
            Observation resource dictionary
        """
        if not patient_ref:
            patient_id = FHIRResourceGenerator.generate_id()
            patient_ref = FHIRResourceGenerator.generate_reference("Patient", patient_id)

        observation = {
            "resourceType": "Observation",
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "vital-signs",
                    "display": "Vital Signs"
                }]
            }],
            "code": FHIRResourceGenerator.generate_codeable_concept(
                code_system,
                code,
                code_display
            ),
            "subject": patient_ref,
            "effectiveDateTime": datetime.now().isoformat()
        }

        # Add value (only one value type should be present)
        if value_codeable_concept is not None:
            observation["valueCodeableConcept"] = value_codeable_concept
        elif value_string is not None:
            observation["valueString"] = value_string
        elif value_quantity is not None:
            observation["valueQuantity"] = value_quantity
        else:
            # Default to quantity if no value specified
            observation["valueQuantity"] = {
                "value": fake.random_int(60, 100),
                "unit": "beats/minute",
                "system": "http://unitsofmeasure.org",
                "code": "/min"
            }

        observation.update(overrides)
        return observation

    @staticmethod
    def generate_invalid_patient(issue: str = "missing_required") -> Dict[str, Any]:
        """Generate an invalid Patient for negative testing.

        Args:
            issue: Type of issue ("missing_required", "invalid_type", "invalid_value")

        Returns:
            Invalid Patient resource
        """
        if issue == "missing_required":
            # Missing resourceType
            return {
                "name": [FHIRResourceGenerator.generate_human_name()]
            }
        elif issue == "invalid_type":
            # Wrong data type for birthDate
            return {
                "resourceType": "Patient",
                "birthDate": 12345  # Should be string
            }
        elif issue == "invalid_value":
            # Invalid gender value
            return {
                "resourceType": "Patient",
                "gender": "invalid_gender_value"
            }
        else:
            return {}

    @staticmethod
    def generate_patient_batch(count: int, **common_overrides) -> List[Dict[str, Any]]:
        """Generate multiple patients with varied attributes.

        Args:
            count: Number of patients to generate
            **common_overrides: Common fields for all patients

        Returns:
            List of Patient resources
        """
        patients = []
        genders = ["male", "female", "other", "unknown"]

        for i in range(count):
            patient = FHIRResourceGenerator.generate_patient(
                gender=genders[i % len(genders)],
                **common_overrides
            )
            patients.append(patient)

        return patients
