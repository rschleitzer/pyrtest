# pyrtest - Comprehensive FHIR R5 Test Suite

> A Python-based black-box HTTP API test suite for validating FHIR R5 server implementations

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![pytest](https://img.shields.io/badge/testing-pytest-yellow.svg)](https://pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Overview

**pyrtest** is a comprehensive test suite designed to validate FHIR R5 (Fast Healthcare Interoperability Resources) server implementations through black-box HTTP API testing. It ensures your FHIR server correctly implements the FHIR R5 specification.

### What pyrtest tests

- ✅ **CRUD Operations** - Create, Read, Update, Delete for all resource types
- ✅ **Search Operations** - All search parameter types (string, token, date, reference, number, quantity)
- ✅ **Search Modifiers** - `:exact`, `:contains`, `:missing`, `:not`, `:above`, `:below`
- ✅ **Search Prefixes** - Date/number comparisons (`gt`, `lt`, `ge`, `le`, `eq`, `ne`, `sa`, `eb`)
- ✅ **Search Chaining** - Forward chaining (`.`) and reverse chaining (`_has`)
- ✅ **Search Includes** - `_include`, `_revinclude`, and `:iterate` for recursive includes
- ✅ **Result Parameters** - `_count`, `_sort`, `_summary`, `_elements`, `_total`
- ✅ **Bundles** - Transaction, batch, history, and search result bundles
- ✅ **Conditional Operations** - Conditional create, update, delete
- ✅ **History & Versioning** - Resource history, version-specific reads
- ✅ **Validation** - Resource validation and error handling
- ✅ **Pagination** - Next/previous links, page navigation

## Quick Start

### Prerequisites

- Python 3.8 or higher
- A FHIR R5 server running and accessible via HTTP

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/pyrtest.git
cd pyrtest

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Set the FHIR server base URL (defaults to `http://localhost:3000/fhir`):

```bash
export FHIR_BASE_URL=http://localhost:8080/fhir
```

### Run Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_patient_crud.py

# Run specific test class
pytest tests/test_patient_crud.py::TestPatientCreate

# Run specific test
pytest tests/test_patient_crud.py::TestPatientCreate::test_create_valid_patient

# Run tests matching a pattern
pytest -k "search"

# Run with coverage report
pytest --cov=. --cov-report=html
```

## Project Structure

```
pyrtest/
├── README.md                     # This file
├── LICENSE                       # MIT License
├── requirements.txt              # Python dependencies
├── conftest.py                   # pytest configuration and shared fixtures
├── pyrtest.ini                    # pytest settings
├── .github/
│   └── workflows/
│       └── tests.yml            # GitHub Actions CI configuration
├── fixtures/
│   └── resource_generators.py   # FHIR resource generators for test data
├── utils/
│   ├── fhir_client.py           # HTTP client wrapper for FHIR operations
│   └── assertions.py            # FHIR-specific assertion helpers
└── tests/
    ├── test_patient_crud.py     # Patient CRUD operations
    ├── test_observation_crud.py # Observation CRUD operations
    ├── test_patient_search.py   # Patient search tests
    ├── test_patient_search_advanced.py  # Advanced search with modifiers
    ├── test_search_chaining.py  # Forward and reverse chaining
    ├── test_search_includes.py  # Include and revinclude tests
    ├── test_bundles.py          # Transaction and batch bundles
    ├── test_history_versioning.py  # History and versioning
    ├── test_conditional_create.py  # Conditional operations
    ├── test_patient_pagination.py  # Pagination tests
    └── test_error_handling.py   # Error handling and validation
```

## Test Categories

### CRUD Tests

Tests for basic Create, Read, Update, Delete operations:

- **test_patient_crud.py** - Patient lifecycle tests
- **test_observation_crud.py** - Observation lifecycle tests

Example operations tested:
- Creating valid resources
- Reading by ID
- Updating with version checking
- Soft delete and hard delete
- Conditional create/update

### Search Tests

Comprehensive search functionality tests:

- **test_patient_search.py** - Basic search parameters (name, gender, birthdate, identifier)
- **test_patient_search_advanced.py** - Modifiers (`:exact`, `:contains`, `:missing`)
- **test_search_chaining.py** - Chaining across resource references
- **test_search_includes.py** - Including referenced/referencing resources

Example searches tested:
- String parameters with partial matches
- Token parameters with system|value syntax
- Date comparisons with prefixes (gt, lt, ge, le)
- Reference parameters with Resource/ID format
- Multiple parameters (AND logic)
- Multiple values (OR logic with commas)
- Sorting and pagination

### Bundle Tests

Tests for FHIR bundle operations:

- **test_bundles.py** - Transaction and batch bundle processing

Example bundle operations:
- Transaction bundles with rollback on error
- Batch bundles with independent entries
- POST, PUT, DELETE operations in bundles
- Conditional operations in bundles
- Bundle response validation

### History & Versioning Tests

Tests for resource history and version management:

- **test_history_versioning.py** - Version tracking and history retrieval

Example operations:
- Retrieving resource history
- Reading specific versions
- Version increments on updates
- History bundle structure

### Conditional Operations Tests

Tests for conditional CRUD based on search criteria:

- **test_conditional_create.py** - Conditional create, update, delete

Example operations:
- Create-if-not-exists based on identifier
- Update matching search criteria
- Delete matching search criteria

### Pagination Tests

Tests for search result pagination:

- **test_patient_pagination.py** - Page navigation and bundle links

Example scenarios:
- First/next/previous/last page links
- Page size control with `_count`
- Total count with `_total=accurate`

### Error Handling Tests

Tests for proper error responses:

- **test_error_handling.py** - Validation and error scenarios

Example error cases:
- Invalid resource structure
- Missing required fields
- Invalid references
- Malformed search parameters
- Not found (404) responses
- Version conflicts (409)

## Utilities

### FHIRClient

HTTP client wrapper for FHIR operations:

```python
from utils.fhir_client import FHIRClient

client = FHIRClient()

# Create
response = client.create(patient_resource)

# Read
response = client.read("Patient", patient_id)

# Update
response = client.update(patient_resource)

# Delete
response = client.delete("Patient", patient_id)

# Search
response = client.search("Patient", {"family": "Smith", "gender": "male"})

# Conditional create
response = client.conditional_create(patient_resource, {"identifier": "http://hospital.org|MRN123"})

# History
response = client.history("Patient", patient_id)

# Transaction bundle
response = client.transaction(bundle_resource)
```

### FHIRAssertions

Helper methods for FHIR-specific assertions:

```python
from utils.assertions import FHIRAssertions

assertions = FHIRAssertions()

# Assert successful creation (201)
created = assertions.assert_created(response, "Patient")

# Assert successful read (200)
patient = assertions.assert_success(response)

# Assert search bundle
bundle = assertions.assert_bundle(response, "Patient")
assert bundle['total'] > 0

# Assert field values
assertions.assert_resource_field_equals(patient, "name.0.family", "Smith")

# Assert OperationOutcome
assertions.assert_operation_outcome(response, severity="error")
```

### FHIRResourceGenerator

Generate valid FHIR R5 resources for testing:

```python
from fixtures.resource_generators import FHIRResourceGenerator

# Generate with defaults
patient = FHIRResourceGenerator.generate_patient()

# Generate with overrides
patient = FHIRResourceGenerator.generate_patient(
    name=[{"family": "Smith", "given": ["John"]}],
    gender="male",
    birthDate="1980-05-15"
)

# Generate observation
observation = FHIRResourceGenerator.generate_observation(
    subject_id="Patient/123",
    code_text="Body Weight",
    value_quantity={"value": 75.5, "unit": "kg"}
)

# Generate batch of resources
patients = FHIRResourceGenerator.generate_patient_batch(10)

# Generate invalid resources for negative tests
invalid_patient = FHIRResourceGenerator.generate_invalid_patient("missing_required_field")
```

## Writing New Tests

### Basic Test Structure

```python
import pytest
from utils.fhir_client import FHIRClient
from utils.assertions import FHIRAssertions
from fixtures.resource_generators import FHIRResourceGenerator

def test_create_patient(client, assertions):
    """Test creating a valid patient resource."""
    # Generate test data
    patient = FHIRResourceGenerator.generate_patient(
        name=[{"family": "TestFamily", "given": ["TestGiven"]}]
    )

    # Perform operation
    response = client.create(patient)

    # Assert results
    created = assertions.assert_created(response, "Patient")
    assert created['name'][0]['family'] == "TestFamily"
    assert created['id'] is not None
```

### Using Fixtures

The `client` and `assertions` fixtures are automatically available:

```python
def test_with_cleanup(client, assertions):
    """Test with automatic cleanup of created resources."""
    patient = FHIRResourceGenerator.generate_patient()

    # This resource will be automatically deleted after the test
    response = client.create(patient)
    created = assertions.assert_created(response, "Patient")

    # Test continues...
```

### Testing Search Operations

```python
def test_search_by_family(client, assertions):
    """Test searching patients by family name."""
    # Create test patient
    patient = FHIRResourceGenerator.generate_patient(
        name=[{"family": "SearchTest", "given": ["John"]}]
    )
    response = client.create(patient)
    created = assertions.assert_created(response, "Patient")

    # Search for patient
    search_response = client.search("Patient", {"family": "SearchTest"})
    bundle = assertions.assert_bundle(search_response, "Patient")

    # Verify results
    assert bundle['total'] >= 1
    found = any(
        entry['resource']['id'] == created['id']
        for entry in bundle.get('entry', [])
    )
    assert found, "Created patient not found in search results"
```

## Configuration

### Environment Variables

- `FHIR_BASE_URL` - Base URL of FHIR server (default: `http://localhost:3000/fhir`)

### pytest Configuration

Edit `pyrtest.ini` to customize test behavior:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

## Continuous Integration

pyrtest includes GitHub Actions workflow for automated testing:

```yaml
# .github/workflows/tests.yml
name: Run FHIR Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest -v
```

## Contributing

Contributions are welcome! When adding new tests:

1. Follow existing test organization patterns
2. Use descriptive test names that explain what is being tested
3. Include docstrings explaining the test purpose
4. Use fixtures for common setup/teardown
5. Include both positive and negative test cases
6. Ensure created resources are tracked for automatic cleanup

### Running Tests During Development

```bash
# Run tests and stop on first failure
pytest -x

# Run tests with detailed output
pytest -vv

# Run specific test and show print statements
pytest -s tests/test_patient_crud.py::test_create_valid_patient

# Run tests in parallel (requires pytest-xdist)
pytest -n auto
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

Based on FHIR R5 specification: https://hl7.org/fhir/R5/

Built with:
- [pytest](https://pytest.org/) - Testing framework
- [requests](https://requests.readthedocs.io/) - HTTP library
- [Faker](https://faker.readthedocs.io/) - Test data generation

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Submit a pull request
- Contact the maintainers

---

**pyrtest** - Ensuring your FHIR R5 server implementation is robust, compliant, and production-ready.
