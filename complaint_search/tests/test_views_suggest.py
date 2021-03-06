from django.conf import settings
from django.core.urlresolvers import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest import skip
from elasticsearch import TransportError
import mock
from complaint_search.es_interface import suggest

class SuggestTests(APITestCase):

    def setUp(self):
        pass

    @mock.patch('complaint_search.es_interface.suggest')
    def test_suggest_no_param(self, mock_essuggest):
        """
        Suggesting with no parameters
        """
        url = reverse('complaint_search:suggest')
        mock_essuggest.return_value = 'OK'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_essuggest.assert_called_once_with()
        self.assertEqual('OK', response.data)

    @mock.patch('complaint_search.es_interface.suggest')
    def test_suggest_text__valid(self, mock_essuggest):
        """
        Suggesting with no parameters
        """
        url = reverse('complaint_search:suggest')
        param = {"text": "Mortgage"}
        mock_essuggest.return_value = 'OK'
        response = self.client.get(url, param)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_essuggest.assert_called_once_with(**param)
        self.assertEqual('OK', response.data)

    @mock.patch('complaint_search.es_interface.suggest')
    def test_suggest_size__valid(self, mock_essuggest):
        """
        Suggesting with no parameters
        """
        url = reverse('complaint_search:suggest')
        param = {"size": 50}
        mock_essuggest.return_value = 'OK'
        response = self.client.get(url, param)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_essuggest.assert_called_once_with(**param)
        self.assertEqual('OK', response.data)

    @mock.patch('complaint_search.es_interface.search')
    def test_search_with_size__invalid_smaller_than_min_number(self, mock_essearch):
        url = reverse('complaint_search:search')
        params = {"size": 0}
        mock_essearch.return_value = 'OK'
        response = self.client.get(url, params)
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)
        mock_essearch.assert_not_called()
        self.assertDictEqual(
            {"size": ["Ensure this value is greater than or equal to 1."]}, 
            response.data)

    @mock.patch('complaint_search.es_interface.suggest')
    def test_suggest_size__invalid_exceed_number(self, mock_essuggest):
        """
        Suggesting with no parameters
        """
        url = reverse('complaint_search:suggest')
        param = {"size": 100001}
        mock_essuggest.return_value = 'OK'
        response = self.client.get(url, param)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_essuggest.assert_not_called()
        self.assertDictEqual(
            {"size": ["Ensure this value is less than or equal to 100000."]}, 
            response.data)

    @mock.patch('complaint_search.es_interface.suggest')
    def test_suggest_cors_headers(self, mock_essuggest):
        """
        Make sure the response has CORS headers in debug mode
        """
        settings.DEBUG = True
        url = reverse('complaint_search:suggest')
        mock_essuggest.return_value = 'OK'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.has_header('Access-Control-Allow-Origin'))

    @mock.patch('complaint_search.es_interface.suggest')
    def test_suggest__transport_error_with_status_code(self, mock_essuggest):
        mock_essuggest.side_effect = TransportError(status.HTTP_404_NOT_FOUND, "Error")
        url = reverse('complaint_search:suggest')
        param = {"text": "test"}
        response = self.client.get(url, param)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertDictEqual({"error": "Elasticsearch error: Error"}, response.data)

    @mock.patch('complaint_search.es_interface.suggest')
    def test_suggest__transport_error_without_status_code(self, mock_essuggest):
        mock_essuggest.side_effect = TransportError('N/A', "Error")
        url = reverse('complaint_search:suggest')
        param = {"text": "test"}
        response = self.client.get(url, param)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertDictEqual({"error": "Elasticsearch error: Error"}, response.data)


