import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import workshop_service as service


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.content = self.root / 'content'
        self.content.mkdir()
        self.acf = self.root / 'appworkshop_431960.acf'
        self.original = b'''"AppWorkshop"
{
 "SizeOnDisk" "3"
 "NeedsDownload" "1"
 "NeedsUpdate" "1"
 "WorkshopItemsInstalled"
 {
  "100001" { "size" "3" "manifest" "11" }
 }
 "WorkshopItemDetails"
 {
  "100001" { "manifest" "11" }
  "100002" { "manifest" "22" "timeupdated" "123" }
 }
}
'''
        self.acf.write_bytes(self.original)
        for ident in ('100001', '100002'):
            folder = self.content / ident
            folder.mkdir()
            (folder / 'data.bin').write_bytes(b'abc')

    def inspect(self):
        return service.inspect(self.acf, self.content, 431960)

    def test_scan_is_read_only_and_filters_appid(self):
        ws = self.root / 'steamapps' / 'workshop'
        ws.mkdir(parents=True)
        (ws / self.acf.name).write_bytes(self.original)
        rows = service.scan(str(self.root), 431960)
        self.assertEqual(len(rows), 1)
        self.assertEqual(service.scan(str(self.root), 4000), [])
        self.assertEqual((ws / self.acf.name).read_bytes(), self.original)

    def test_repair_preserves_existing_records_flags_and_backup(self):
        before = self.inspect()
        result = service.repair(before, process_check=lambda: False)
        after = self.inspect()
        self.assertEqual(result['added'], 1)
        self.assertEqual(len(after['installed']), 2)
        self.assertEqual(after['installed']['100001'], before['installed']['100001'])
        self.assertEqual(service.core.field_value(after['text'], 'NeedsDownload'), '1')
        self.assertEqual(service.core.field_value(after['text'], 'NeedsUpdate'), '1')
        self.assertEqual(result['backup'].read_bytes(), self.original)
        self.assertEqual((self.content / '100002' / 'data.bin').read_bytes(), b'abc')
        self.assertEqual(after['candidates'], [])

    def test_missing_download_is_not_repair_candidate(self):
        (self.content / '100002' / 'data.bin').unlink()
        (self.content / '100002').rmdir()
        self.assertEqual(self.inspect()['candidates'], [])

    def test_steam_running_refuses_without_write(self):
        with self.assertRaises(RuntimeError):
            service.repair(self.inspect(), process_check=lambda: True)
        self.assertEqual(self.acf.read_bytes(), self.original)

    def test_changed_manifest_refuses(self):
        row = self.inspect()
        self.acf.write_bytes(self.original + b'\n')
        with self.assertRaises(RuntimeError):
            service.repair(row, process_check=lambda: False)

    def test_missing_block_refuses(self):
        self.acf.write_bytes(self.original.replace(b'WorkshopItemsInstalled', b'MissingInstalled'))
        row = self.inspect()
        self.assertEqual(row['candidates'], [])
        with self.assertRaises(ValueError):
            service.repair(row, process_check=lambda: False)

    def test_empty_folder_refuses(self):
        (self.content / '100002' / 'data.bin').unlink()
        with self.assertRaises(ValueError):
            service.repair(self.inspect(), process_check=lambda: False)
        self.assertEqual(self.acf.read_bytes(), self.original)

    def test_steam_starts_before_commit_refuses(self):
        with self.assertRaises(RuntimeError):
            service.repair(self.inspect(), process_check=unittest.mock.Mock(side_effect=[False, True]))
        self.assertEqual(self.acf.read_bytes(), self.original)

    def test_atomic_replace_failure_keeps_original_and_backup(self):
        with patch('workshop_service.os.replace', side_effect=OSError('test failure')):
            with self.assertRaises(OSError):
                service.repair(self.inspect(), process_check=lambda: False)
        self.assertEqual(self.acf.read_bytes(), self.original)
        self.assertEqual(len(list(self.root.glob('appworkshop_backup_*.acf'))), 1)
        self.assertEqual(list(self.root.glob('.wefix-*')), [])


if __name__ == '__main__':
    unittest.main()
