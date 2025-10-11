"""FHIR HTTP Client for testing FHIR servers."""
import os
import requests
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin, urlencode


class FHIRClient:
    """HTTP client for FHIR R5 server interactions."""

    def __init__(self, base_url: Optional[str] = None):
        """Initialize FHIR client.

        Args:
            base_url: Base URL of FHIR server (default: http://localhost:8080/fhir)
        """
        url = base_url or os.environ.get('FHIR_BASE_URL', 'http://localhost:8080/fhir')
        # Store without trailing slash for external use
        self.base_url = url.rstrip('/')
        # Store with trailing slash for urljoin
        self._base_url_with_slash = self.base_url + '/'
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        })

    def _url(self, path: str) -> str:
        """Construct full URL from path."""
        # Strip leading slash from path to avoid double slashes
        if path.startswith('/'):
            path = path[1:]
        return urljoin(self._base_url_with_slash, path)

    def create(self, resource: Dict[str, Any]) -> requests.Response:
        """Create a resource (POST).

        Args:
            resource: FHIR resource dictionary

        Returns:
            Response object
        """
        resource_type = resource['resourceType']
        # Special handling for Bundle - post to root endpoint for processing
        if resource_type == 'Bundle':
            return self.session.post(
                self.base_url,
                json=resource
            )
        return self.session.post(
            self._url(resource_type),
            json=resource
        )

    def read(self, resource_type: str, resource_id: str) -> requests.Response:
        """Read a resource by ID (GET).

        Args:
            resource_type: Type of resource (e.g., 'Patient')
            resource_id: Resource ID

        Returns:
            Response object
        """
        return self.session.get(
            self._url(f"{resource_type}/{resource_id}")
        )

    def vread(self, resource_type: str, resource_id: str, version_id: str) -> requests.Response:
        """Read a specific version of a resource.

        Args:
            resource_type: Type of resource
            resource_id: Resource ID
            version_id: Version ID

        Returns:
            Response object
        """
        return self.session.get(
            self._url(f"{resource_type}/{resource_id}/_history/{version_id}")
        )

    def update(self, resource: Dict[str, Any], if_match: Optional[str] = None) -> requests.Response:
        """Update a resource (PUT).

        Args:
            resource: FHIR resource dictionary with id
            if_match: Optional ETag for conditional update

        Returns:
            Response object
        """
        resource_type = resource['resourceType']
        resource_id = resource['id']
        headers = {}
        if if_match:
            headers['If-Match'] = if_match

        return self.session.put(
            self._url(f"{resource_type}/{resource_id}"),
            json=resource,
            headers=headers
        )

    def delete(self, resource_type: str, resource_id: str) -> requests.Response:
        """Delete a resource (DELETE).

        Args:
            resource_type: Type of resource
            resource_id: Resource ID

        Returns:
            Response object
        """
        return self.session.delete(
            self._url(f"{resource_type}/{resource_id}")
        )

    def search(self, resource_type: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Search for resources (GET).

        Args:
            resource_type: Type of resource to search
            params: Search parameters

        Returns:
            Response object with Bundle
        """
        url = self._url(resource_type)
        if params:
            url += '?' + urlencode(params, doseq=True)
        return self.session.get(url)

    def conditional_create(self, resource: Dict[str, Any], search_params: Dict[str, Any]) -> requests.Response:
        """Conditional create using If-None-Exist header.

        Args:
            resource: FHIR resource dictionary
            search_params: Search parameters for condition

        Returns:
            Response object
        """
        resource_type = resource['resourceType']
        headers = {
            'If-None-Exist': urlencode(search_params)
        }
        return self.session.post(
            self._url(resource_type),
            json=resource,
            headers=headers
        )

    def conditional_update(self, resource: Dict[str, Any], search_params: Dict[str, Any]) -> requests.Response:
        """Conditional update based on search criteria.

        Args:
            resource: FHIR resource dictionary
            search_params: Search parameters for condition

        Returns:
            Response object
        """
        resource_type = resource['resourceType']
        url = self._url(resource_type) + '?' + urlencode(search_params)
        return self.session.put(url, json=resource)

    def conditional_delete(self, resource_type: str, search_params: Dict[str, Any]) -> requests.Response:
        """Conditional delete based on search criteria.

        Args:
            resource_type: Type of resource
            search_params: Search parameters for condition

        Returns:
            Response object
        """
        url = self._url(resource_type) + '?' + urlencode(search_params)
        return self.session.delete(url)

    def history(self, resource_type: Optional[str] = None, resource_id: Optional[str] = None,
                params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Get history of changes.

        Args:
            resource_type: Optional resource type (None for system-level history)
            resource_id: Optional resource ID (requires resource_type)
            params: Optional parameters like _count, _since

        Returns:
            Response object with Bundle of history
        """
        if resource_id and resource_type:
            url = self._url(f"{resource_type}/{resource_id}/_history")
        elif resource_type:
            url = self._url(f"{resource_type}/_history")
        else:
            url = self._url("_history")

        if params:
            url += '?' + urlencode(params, doseq=True)
        return self.session.get(url)

    def type_history(self, resource_type: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Get history for all resources of a type.

        Args:
            resource_type: Resource type
            params: Optional parameters like _count, _since

        Returns:
            Response object with Bundle of history
        """
        return self.history(resource_type=resource_type, params=params)

    def system_history(self, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Get system-wide history.

        Args:
            params: Optional parameters like _count, _since

        Returns:
            Response object with Bundle of history
        """
        return self.history(params=params)
