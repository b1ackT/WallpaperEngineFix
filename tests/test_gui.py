"""Exercise the real Tk event loop with isolated service fixtures."""
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from wallpaper_gui import App


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.app = App()
        self.app.withdraw()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        for timer in self.app.tk.call('after', 'info'):
            self.app.after_cancel(timer)
        self.app.destroy()

    def wait_for_worker(self):
        deadline = time.monotonic() + 5
        while self.app.busy and time.monotonic() < deadline:
            self.app.update()
            time.sleep(0.01)
        self.assertFalse(self.app.busy)

    def test_scan_renders_rows_and_enables_selected_repair(self):
        row = dict(appid=431960, candidates=['100002'], installed={'100001': ''},
                   details={'100001': {}, '100002': {}}, folders={'100001', '100002'},
                   status='可补全记录', reason='测试数据', path=Path('fixture.acf'))
        with patch('wallpaper_gui.service.scan', return_value=[row]) as scan:
            self.app.scan_button.invoke()
            self.wait_for_worker()
        scan.assert_called_once()
        self.assertEqual(len(self.app.table.get_children()), 1)
        self.assertIn('disabled', self.app.repair_button.state())
        self.app.table.selection_set('0')
        self.app.update()
        self.assertNotIn('disabled', self.app.repair_button.state())
        self.assertIn('fixture.acf', self.app.detail.cget('text'))

    def test_scan_failure_restores_controls(self):
        with patch('wallpaper_gui.service.scan', side_effect=ValueError('模拟读取失败')):
            with patch('wallpaper_gui.messagebox.showerror') as error:
                self.app.scan_button.invoke()
                self.wait_for_worker()
                error.assert_called_once()
        self.assertNotIn('disabled', self.app.scan_button.state())
        self.assertIn('模拟读取失败', self.app.log_text.get('1.0', 'end'))
