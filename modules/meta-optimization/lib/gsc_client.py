"""Shared GSC API client with auth, rate limiting, pagination, and error retries."""

import time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GSCClient:
    def __init__(self, service_account_path, rate_limit_sleep=1.0):
        self.creds = service_account.Credentials.from_service_account_file(
            service_account_path,
            scopes=['https://www.googleapis.com/auth/webmasters',
                    'https://www.googleapis.com/auth/webmasters.readonly']
        )
        self.service = build('searchconsole', 'v1', credentials=self.creds)
        self.rate_limit_sleep = rate_limit_sleep

    def list_sites(self):
        resp = self.service.sites().list().execute()
        return resp.get('siteEntry', [])

    def query_search_analytics(self, site_url, start_date, end_date,
                                dimensions=None, filters=None,
                                row_limit=25000, start_row=0):
        body = {
            'startDate': start_date,
            'endDate': end_date,
            'dimensions': dimensions or ['query'],
            'rowLimit': row_limit,
            'startRow': start_row,
        }
        if filters:
            body['dimensionFilterGroups'] = [{'filters': filters}]

        for attempt in range(3):
            try:
                resp = self.service.searchanalytics().query(
                    siteUrl=site_url, body=body
                ).execute()
                time.sleep(self.rate_limit_sleep)
                return resp.get('rows', [])
            except HttpError as e:
                if e.resp.status in (429, 500, 503) and attempt < 2:
                    wait = (attempt + 1) * 10
                    print(f"  GSC API error {e.resp.status}, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    def get_queries_for_page(self, site_url, page_url, start_date, end_date,
                              row_limit=100):
        filters = [{
            'dimension': 'page',
            'operator': 'equals',
            'expression': page_url
        }]
        return self.query_search_analytics(
            site_url, start_date, end_date,
            dimensions=['query'], filters=filters, row_limit=row_limit
        )

    def get_all_pages(self, site_url, start_date, end_date):
        all_rows = []
        start_row = 0
        while True:
            rows = self.query_search_analytics(
                site_url, start_date, end_date,
                dimensions=['page'], row_limit=25000, start_row=start_row
            )
            if not rows:
                break
            all_rows.extend(rows)
            start_row += len(rows)
            if len(rows) < 25000:
                break
        return all_rows

    def submit_url_for_indexing(self, url):
        """Submit URL_UPDATED notification via Indexing API."""
        indexing = build('indexing', 'v3', credentials=self.creds)
        body = {'url': url, 'type': 'URL_UPDATED'}
        for attempt in range(3):
            try:
                resp = indexing.urlNotifications().publish(body=body).execute()
                time.sleep(self.rate_limit_sleep)
                return resp
            except HttpError as e:
                if e.resp.status in (429, 500, 503) and attempt < 2:
                    time.sleep((attempt + 1) * 10)
                else:
                    raise
