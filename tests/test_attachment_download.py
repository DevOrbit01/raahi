from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import gui


class AttachmentDownloadTests(unittest.TestCase):
    def test_protected_image_uses_verified_chrome_only_at_export(self):
        url = 'https://www.eauctionsindia.com/storage/images/photo.webp'
        item = {'listingId': '123', 'source': 'eauctionsindia', 'images': url, 'pdfLinks': url}
        for status, content_type in [(403, 'text/html'), (200, 'text/html')]:
            with self.subTest(status=status):
                app = SimpleNamespace(
                    root=SimpleNamespace(after=lambda delay, action: action()),
                    update_status=Mock(), log=Mock(), open_file_btn=Mock(),
                    download_selected_btn=Mock(), start_btn=Mock(), eauctions_access_btn=Mock(),
                )
                blocked = SimpleNamespace(status_code=status, content=b'<html>challenge</html>', headers={'Content-Type': content_type})
                image = SimpleNamespace(status_code=200, content=b'actual image', headers={'Content-Type': 'image/webp'})
                with TemporaryDirectory() as folder, patch.object(gui, 'save_items_to_excel', return_value='results.xlsx'), patch.object(gui, 'mark_items_seen') as seen, patch.object(gui.messagebox, 'showinfo'), patch.object(gui.requests, 'get', return_value=blocked) as request, patch.object(gui, 'fetch_chrome_attachment', return_value=image) as chrome:
                    gui.ScraperGUI.run_download_thread(app, [item], folder, False)
                    request.assert_not_called()
                    chrome.assert_not_called()
                    gui.ScraperGUI.run_download_thread(app, [item], folder, True)
                    request.assert_called_once()
                    chrome.assert_called_once_with(url)
                    self.assertEqual((Path(folder)/'images/123/media_1.webp').read_bytes(), image.content)
                    self.assertEqual((Path(folder)/'documents/123/document_1.webp').read_bytes(), image.content)
                    seen.assert_called_with([item])

    def test_excel_export_downloads_shared_image_notice_once(self):
        app = SimpleNamespace(
            root=SimpleNamespace(after=lambda delay, action: action()),
            update_status=Mock(), log=Mock(), open_file_btn=Mock(), download_selected_btn=Mock(),
            start_btn=Mock(), eauctions_access_btn=Mock(),
        )
        url = 'https://example.com/notice.jpg'
        item = {'listingId': '123', 'images': url, 'pdfLinks': url}
        events = []
        response = SimpleNamespace(status_code=200, content=b'notice bytes', headers={'Content-Type': 'image/jpeg'})
        with TemporaryDirectory() as folder, patch.object(gui, 'save_items_to_excel', side_effect=lambda *a, **kw: events.append('excel') or 'results.xlsx'), patch.object(gui, 'mark_items_seen') as seen, patch.object(gui.messagebox, 'showinfo'), patch.object(gui.requests, 'get', side_effect=lambda *a, **kw: events.append('download') or response) as request:
            gui.ScraperGUI.run_download_thread(app, [item], folder, False)
            request.assert_not_called()
            gui.ScraperGUI.run_download_thread(app, [item], folder, True)
            request.assert_called_once()
            self.assertEqual(events, ['excel', 'excel', 'download'])
            self.assertEqual((Path(folder)/'images/123/media_1.jpg').read_bytes(), response.content)
            self.assertEqual((Path(folder)/'documents/123/document_1.jpg').read_bytes(), response.content)
            seen.assert_called_with([item])

    def test_failed_attachment_warns_and_can_be_retried(self):
        app = SimpleNamespace(
            root=SimpleNamespace(after=lambda delay, action: action()),
            update_status=Mock(), log=Mock(),
            open_file_btn=Mock(), download_selected_btn=Mock(),
            start_btn=Mock(), eauctions_access_btn=Mock(),
        )
        item = {"listingId": "123", "images": "", "pdfLinks": "https://example.com/notice.jpg"}
        blocked = SimpleNamespace(status_code=403, content=b"blocked", headers={})
        html = SimpleNamespace(status_code=200, content=b"<html>verification</html>", headers={"Content-Type": "text/html"})
        notice = SimpleNamespace(status_code=200, content=b"notice bytes", headers={"Content-Type": "image/jpeg"})
        with TemporaryDirectory() as folder, patch.object(gui, "save_items_to_excel", return_value="results.xlsx"), patch.object(gui, "mark_items_seen") as seen, patch.object(gui.messagebox, "showwarning") as warning, patch.object(gui.messagebox, "showinfo") as info, patch.object(gui.requests, "get", side_effect=[blocked, html, notice]):
            gui.ScraperGUI.run_download_thread(app, [item], folder, True)
            seen.assert_called_with([])
            warning.assert_called_once()
            info.assert_not_called()
            gui.ScraperGUI.run_download_thread(app, [item], folder, True)
            seen.assert_called_with([])
            self.assertEqual(warning.call_count, 2)
            gui.ScraperGUI.run_download_thread(app, [item], folder, True)
            seen.assert_called_with([item])
            info.assert_called_once()
            self.assertEqual((Path(folder) / "documents/123/document_1.jpg").read_bytes(), notice.content)


if __name__ == "__main__":
    unittest.main()
