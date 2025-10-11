# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**pyrtest** is a comprehensive black-box HTTP API test suite for validating FHIR R5 (Fast Healthcare Interoperability Resources) server implementations. The test suite validates CRUD operations, search functionality, bundles, history/versioning, conditional operations, pagination, and error handling against a FHIR R5 server.

## Running Tests

### Basic Commands

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

# Run tests with specific marker
pytest -m crud
pytest -m search
pytest -m bundle

# Run and stop on first failure
pytest -x

# Run with print statements shown
pytest -s

# Run with coverage
pytest --cov=. --cov-report=html
```

### Configuration

The FHIR server base URL is configured via environment variable:
```bash
export FHIR_BASE_URL=http://localhost:8080/fhir
```

Default is `http://localhost:8080/fhir` if not specified.

## Architecture

### Core Components

1. **FHIRClient** (`utils/fhir_client.py`)
   - HTTP client wrapper for all FHIR operations
   - Handles URL construction, headers, and request/response flow
   - Methods: `create()`, `read()`, `update()`, `delete()`, `search()`, `history()`
   - Conditional operations: `conditional_create()`, `conditional_update()`, `conditional_delete()`
   - Automatically sets `Accept: application/fhir+json` and `Content-Type: application/fhir+json`

2. **FHIRAssertions** (`utils/assertions.py`)
   - FHIR-specific assertion helpers
   - Methods include `assert_created()`, `assert_read_success()`, `assert_bundle()`, etc.
   - Provides detailed error messages including OperationOutcome diagnostics
   - Supports dot-notation field path assertions (e.g., `"name.0.family"`)

3. **FHIRResourceGenerator** (`fixtures/resource_generators.py`)
   - Generates valid FHIR R5 resources for testing using Faker
   - Methods: `generate_patient()`, `generate_observation()`, `generate_practitioner()`
   - Supports overrides for specific fields
   - Can generate invalid resources for negative testing

4. **Test Fixtures** (`conftest.py`)
   - `client` fixture: Provides FHIRClient with automatic resource tracking
   - `assertions` fixture: Provides FHIRAssertions helper
   - `cleanup_created_resources` fixture: Automatically deletes resources created during tests
   - Resource tracking: Created resources are automatically tracked and cleaned up after each test

### Resource Cleanup System

The test suite implements automatic cleanup to avoid polluting the test FHIR server:

- `client.create()` is wrapped to track all created resources
- After each test, tracked resources are automatically deleted
- For resources created in bundles, cleanup uses conditional delete with test-specific markers
- A purge endpoint is called for deleted resource types: `{base_url}/purgeschema/{ResourceType}/{purge_key}`
- Purge key is defined in `conftest.py`: `c522382c-8656-463e-8277-b913e4466f53`

### Test Organization

Tests are organized by functionality:
- **CRUD Tests**: `test_patient_crud.py`, `test_observation_crud.py`
- **Search Tests**: `test_patient_search.py`, `test_patient_search_advanced.py`, `test_search_chaining.py`, `test_search_includes.py`
- **Bundle Tests**: `test_bundles.py`
- **History Tests**: `test_history_versioning.py`
- **Conditional Operations**: `test_conditional_create.py`
- **Pagination Tests**: `test_patient_pagination.py`
- **Error Handling**: `test_error_handling.py`

## Writing New Tests

### Standard Test Pattern

```python
def test_example(client, assertions):
    """Test description."""
    # 1. Generate test data
    patient = FHIRResourceGenerator.generate_patient(
        name=[{"family": "TestName", "given": ["John"]}]
    )

    # 2. Perform operation
    response = client.create(patient)

    # 3. Assert results
    created = assertions.assert_created(response, "Patient")
    assert created['name'][0]['family'] == "TestName"
```

### Important Patterns

1. **Always use fixtures**: Tests should accept `client` and `assertions` parameters
2. **Resource cleanup is automatic**: Resources created via `client.create()` are tracked and deleted
3. **Bundle resources need markers**: For cleanup, use distinctive family names or identifiers in bundle tests
4. **Use generators**: Always use `FHIRResourceGenerator` to create test data
5. **Descriptive names**: Test names should clearly explain what is being validated

### Test Structure Convention

Tests are organized into classes by operation type:
- `TestPatientCreate` - creation tests
- `TestPatientRead` - read tests
- `TestPatientUpdate` - update tests
- `TestPatientDelete` - delete tests
- `TestPatientWorkflow` - end-to-end workflow tests

## FHIR R5 Specifics

### Status Codes

- `201 Created` - Resource created, includes Location header
- `200 OK` - Resource read/updated, conditional create found existing
- `204 No Content` or `200 OK` - Resource deleted
- `404 Not Found` - Resource doesn't exist
- `410 Gone` - Resource was deleted
- `400 Bad Request` - Invalid resource structure
- `409 Conflict` or `412 Precondition Failed` - Version conflict

### Bundle Types

- `transaction` - All-or-nothing, rolled back on any error
- `batch` - Independent entries, partial success allowed
- `searchset` - Search results
- `history` - History results

### Search Modifiers

- `:exact` - Exact string match
- `:contains` - Substring match
- `:missing` - Check if parameter is missing
- `:not` - Negation
- `:above` / `:below` - Hierarchical codes

### Search Prefixes

- `eq` - Equal (default)
- `ne` - Not equal
- `gt` - Greater than
- `lt` - Less than
- `ge` - Greater or equal
- `le` - Less or equal
- `sa` - Starts after
- `eb` - Ends before

## Debugging Tips

1. **View full response**: Use `pytest -s` to see print statements
2. **Check OperationOutcome**: Assertions automatically include OperationOutcome diagnostics in error messages
3. **Inspect tracked resources**: Check `_created_resources` in `conftest.py` for cleanup issues
4. **Test cleanup**: If tests fail, check the cleanup fixture is working properly

## Key Implementation Details

1. **URL Construction**: FHIRClient uses `urljoin` with a trailing slash base URL internally to ensure proper path joining
2. **Bundle Handling**: Bundle resources are POSTed to the base URL (not `/Bundle`) for transaction/batch processing
3. **Version Tracking**: Updates increment `meta.versionId`
4. **Conditional Operations**: Use `If-None-Exist` header or query parameters depending on operation
5. **Search Results**: Always return Bundle with `resourceType: "Bundle"`
