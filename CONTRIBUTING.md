# Contributing to pyrtest

Thank you for considering contributing to pyrtest! This document provides guidelines for contributing to the project.

## How to Contribute

### Reporting Issues

- Use the GitHub issue tracker
- Describe the issue clearly with reproduction steps
- Include the FHIR server type and version you're testing against
- Provide relevant log output or error messages

### Suggesting Enhancements

- Open an issue describing the enhancement
- Explain why this enhancement would be useful
- Provide examples of how it would work

### Pull Requests

1. Fork the repository
2. Create a new branch for your feature (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run the tests to ensure they pass
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Development Guidelines

### Code Style

- Follow PEP 8 style guide for Python code
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and small

### Test Structure

```python
def test_descriptive_name(client, assertions):
    """Brief description of what this test validates.

    This test ensures that [specific behavior] works correctly
    when [specific conditions].
    """
    # Arrange - Set up test data
    resource = FHIRResourceGenerator.generate_patient(
        name=[{"family": "Test"}]
    )

    # Act - Perform the operation
    response = client.create(resource)

    # Assert - Verify the results
    created = assertions.assert_created(response, "Patient")
    assert created['name'][0]['family'] == "Test"
```

### Testing Guidelines

1. **Use Descriptive Test Names**: Test names should clearly indicate what is being tested
   - Good: `test_search_patient_by_family_name_exact_match`
   - Bad: `test_search1`

2. **Include Docstrings**: Every test should have a docstring explaining:
   - What is being tested
   - Expected behavior
   - Any special conditions or edge cases

3. **Use Fixtures**: Leverage pytest fixtures for common setup
   - `client` - FHIR client instance
   - `assertions` - Assertion helper instance
   - Create custom fixtures for common test resources

4. **Clean Up Resources**: All created resources are automatically cleaned up by the `cleanup_created_resources` fixture

5. **Test Both Success and Failure**: Include positive and negative test cases
   ```python
   def test_create_valid_patient(client, assertions):
       """Test successful patient creation."""
       # Test valid case

   def test_create_invalid_patient_missing_required(client, assertions):
       """Test patient creation fails with missing required fields."""
       # Test invalid case
   ```

6. **Use Test Markers**: Mark tests appropriately
   ```python
   import pytest

   @pytest.mark.crud
   def test_create_patient(client, assertions):
       """CRUD test for patient creation."""
       pass

   @pytest.mark.slow
   def test_large_bundle(client, assertions):
       """Test with large bundle (takes longer)."""
       pass
   ```

### Adding New Resource Tests

When adding tests for a new FHIR resource type:

1. Create a new test file: `tests/test_<resourcetype>_crud.py`
2. Add resource generator to `fixtures/resource_generators.py`
3. Include tests for:
   - Basic CRUD operations
   - Search parameters specific to that resource
   - Resource-specific validation rules
   - Relationships to other resources

Example structure:
```python
"""Tests for <ResourceType> CRUD operations."""
import pytest
from fixtures.resource_generators import FHIRResourceGenerator

class TestResourceTypeCreate:
    """Tests for creating <ResourceType> resources."""

    def test_create_valid_resource(self, client, assertions):
        """Test creating a valid <ResourceType>."""
        pass

class TestResourceTypeRead:
    """Tests for reading <ResourceType> resources."""

    def test_read_existing_resource(self, client, assertions):
        """Test reading an existing <ResourceType>."""
        pass

class TestResourceTypeUpdate:
    """Tests for updating <ResourceType> resources."""
    pass

class TestResourceTypeDelete:
    """Tests for deleting <ResourceType> resources."""
    pass
```

### Running Tests Locally

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_patient_crud.py

# Run with coverage
pytest --cov=. --cov-report=html

# Run with verbose output
pytest -vv

# Run tests matching pattern
pytest -k "search"

# Stop on first failure
pytest -x
```

### Documentation

- Update README.md if adding new features
- Add inline comments for complex logic
- Update docstrings when changing function behavior

### Commit Messages

Use clear, descriptive commit messages:

```
Add search tests for Observation resource

- Implement basic search by code and subject
- Add tests for date range searches
- Include tests for search modifiers
```

## Questions?

If you have questions about contributing, please open an issue for discussion.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback
- Keep discussions focused on the project

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
