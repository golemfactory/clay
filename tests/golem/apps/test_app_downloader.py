from mock import Mock, patch

import requests

import golem.apps.downloader as downloader
from golem.testutils import TempDirFixture

ROOT_PATH = 'golem.apps.downloader'

APP_KEY = 'test-app_0.1.0_asdf1234.json'
BUCKET_LISTING_XML = f'''<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
    <Name>golem-app-definitions</Name>
    <Contents>
        <Key>{APP_KEY}</Key>
        <LastModified>2020-02-28T08:49:34.000Z</LastModified>
        <ETag>&quot;1c5dbeaaf0589820b799448664d24864&quot;</ETag>
        <Size>357</Size>
        <StorageClass>STANDARD</StorageClass>
    </Contents>
</ListBucketResult>
'''


class TestAppDownloader(TempDirFixture):

    @patch(f'{ROOT_PATH}.get_bucket_listing')
    @patch(f'{ROOT_PATH}.download_definition')
    def test_download_definitions(self, download_mock, bucket_listing_mock):
        apps_path = self.new_path / 'apps'
        apps_path.mkdir(exist_ok=True)
        existing_app_path = apps_path / APP_KEY
        existing_app_path.touch()
        new_app_key = 'downloaded_app.json'
        metadata = [
            Mock(spec=downloader.Contents, key=APP_KEY),
            Mock(spec=downloader.Contents, key=new_app_key),
        ]
        bucket_listing_mock.return_value = Mock(
            spec=downloader.ListBucketResult, contents=metadata)

        new_definitions = downloader.download_definitions(apps_path)

        self.assertEqual(len(new_definitions), 1)
        download_mock.assert_called_once_with(
            new_app_key, apps_path / new_app_key)
        self.assertEqual(download_mock.call_count, 1)

    @patch('requests.get')
    def test_get_bucket_listing(self, mock_get):
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.content = BUCKET_LISTING_XML
        mock_get.return_value = response

        result = downloader.get_bucket_listing()

        self.assertEqual(len(result.contents), 1)
        self.assertEqual(result.contents[0].key, APP_KEY)
