"""Tests for clients module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from extraction_service.clients import CellarClient, EchaClient


class TestCellarClient:
    """Tests for CellarClient."""
    
    def test_build_sparql_query_no_cursor(self):
        """Test SPARQL query building without cursor."""
        client = CellarClient()
        query = client.build_sparql_query(cursor=None, limit=10, offset=0)
        
        assert "LIMIT 10" in query
        assert "OFFSET 0" in query
        assert "32011L0065" in query  # RoHS in watchlist
        assert "FILTER(?modified >" not in query  # No cursor filter
    
    def test_build_sparql_query_with_cursor(self):
        """Test SPARQL query building with cursor."""
        client = CellarClient()
        cursor = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        query = client.build_sparql_query(cursor=cursor, limit=10, offset=0)
        
        assert "FILTER(?modified > '2024-01-01T12:00:00'" in query
    
    @patch('clients.SPARQLWrapper')
    def test_discover_documents(self, mock_sparql):
        """Test document discovery."""
        # Mock SPARQL response
        mock_results = {
            "results": {
                "bindings": [
                    {
                        "celex": {"value": "32011L0065"},
                        "modified": {"value": "2024-01-01T12:00:00Z"},
                        "title": {"value": "RoHS Directive"},
                        "date": {"value": "2011-06-08"},
                    }
                ]
            }
        }
        
        mock_sparql_instance = MagicMock()
        mock_sparql_instance.query().convert.return_value = mock_results
        mock_sparql.return_value = mock_sparql_instance
        
        client = CellarClient()
        client.sparql = mock_sparql_instance
        
        documents = client.discover_documents()
        
        assert len(documents) == 1
        assert documents[0]["celex"] == "32011L0065"
        assert documents[0]["title"] == "RoHS Directive"
    
    @patch('extraction_service.clients.httpx.Client')
    def test_fetch_formex_xml_success(self, mock_client):
        """Test Formex XML fetching."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<xml>test</xml>"
        mock_response.content = b"<xml>test</xml>"
        mock_response.headers = {
            "ETag": "test-etag",
            "Last-Modified": "Mon, 01 Jan 2024 12:00:00 GMT",
        }
        
        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        client = CellarClient()
        client.client = mock_client_instance
        
        result = client.fetch_formex_xml("32011L0065")
        
        assert result is not None
        xml_content, cache_headers = result
        assert xml_content == "<xml>test</xml>"
        assert cache_headers["etag"] == "test-etag"
    
    @patch('clients.httpx.Client')
    def test_fetch_formex_xml_not_modified(self, mock_client):
        """Test Formex XML fetching with 304 Not Modified."""
        mock_response = Mock()
        mock_response.status_code = 304
        
        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        client = CellarClient()
        client.client = mock_client_instance
        
        result = client.fetch_formex_xml("32011L0065", etag="test-etag")
        
        assert result is None


class TestEchaClient:
    """Tests for EchaClient."""
    
    @patch('clients.httpx.Client')
    def test_fetch_candidate_list(self, mock_client):
        """Test ECHA candidate list fetching."""
        # Mock HTML response
        html = """
        <table>
            <tr><th>Substance</th><th>CAS</th><th>Date</th><th>Reason</th></tr>
            <tr>
                <td>Lead</td>
                <td>7439-92-1</td>
                <td>2008-10-28</td>
                <td>Toxic</td>
            </tr>
        </table>
        """
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = html
        
        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value = mock_client_instance
        
        client = EchaClient()
        client.client = mock_client_instance
        
        substances = client.fetch_candidate_list()
        
        assert len(substances) == 1
        assert substances[0]["substance_name"] == "Lead"
        assert substances[0]["cas_number"] == "7439-92-1"
    
    def test_cache_validity(self):
        """Test cache TTL check."""
        client = EchaClient()
        
        # No cache
        assert not client._is_cache_valid()
        
        # Set cache
        client._cache = [{"test": "data"}]
        client._cache_timestamp = datetime.now(timezone.utc)
        
        # Cache should be valid
        assert client._is_cache_valid()
    
    def test_detect_changes(self):
        """Test change detection."""
        client = EchaClient()
        
        previous_list = [
            {"substance_name": "Lead", "cas_number": "7439-92-1"},
            {"substance_name": "Cadmium", "cas_number": "7440-43-9"},
        ]
        
        # Mock current list with one added, one modified
        client._cache = [
            {"substance_name": "Lead", "cas_number": "7439-92-1"},  # Unchanged
            {"substance_name": "Cadmium", "cas_number": "MODIFIED"},  # Modified
            {"substance_name": "Mercury", "cas_number": "7439-97-6"},  # Added
        ]
        client._cache_timestamp = datetime.now(timezone.utc)
        
        changes = client.detect_changes(previous_list)
        
        assert len(changes["added"]) == 1
        assert len(changes["modified"]) == 1
        assert len(changes["unchanged"]) == 1
