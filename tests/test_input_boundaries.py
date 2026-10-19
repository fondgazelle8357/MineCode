"""Input boundary regressions, with deadlines for hostile input."""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import io
import struct
import zipfile
from contextlib import nullcontext
from unittest.mock import patch

from minecode_runtime.diagnostics import analyze
from minecode_runtime.failure_evidence import diagnose
from minecode_runtime.gradle import TASK_PATTERN, validate_task
from minecode_runtime.inspection import inspect, without_comments
from minecode_runtime.models import FailureEnvironment
from minecode_runtime.reference_cache import ReferenceCache
from minecode_runtime import local_sources


class InputBoundaryTests(unittest.TestCase):
    def run_bounded(self, code):
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unclosed_gradle_strings_do_not_stall_inspection(self):
        self.run_bounded(
            'from minecode_runtime.inspection import without_comments; '
            's = chr(34) + chr(92) * 5000; assert without_comments(s) == s'
        )

    def test_comment_removal_preserves_strings_and_token_boundaries(self):
        text = 'url = "https://example.org/a//b" // comment\nfoo/* comment */bar'
        clean = without_comments(text)
        self.assertIn('"https://example.org/a//b"', clean)
        self.assertNotIn('comment', clean)
        self.assertRegex(clean, r'foo\s+bar')

    def test_gradle_tasks_cannot_be_options_or_empty_path_components(self):
        for task in ['-I:build', '--init-script:build', '--offline:build', 'x::y:build', ':x:-y:build']:
            with self.subTest(task=task):
                self.assertIsNone(re.fullmatch(TASK_PATTERN, task))
                with self.assertRaises(ValueError):
                    validate_task(task)
        for task in ['build', ':build', ':client:build', 'client:runClient', 'a-b:c_d:test']:
            with self.subTest(task=task):
                validate_task(task)

    def test_deep_metadata_produces_warnings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'fabric.mod.json').write_text('[' * 3000 + '0' + ']' * 3000)
            (root / 'gradle').mkdir()
            (root / 'gradle/libs.versions.toml').write_text('x = ' + '[' * 3000 + '0' + ']' * 3000)
            profile = inspect(root)
            self.assertTrue(any('JSON' in message for message in profile.warnings))
            self.assertTrue(any('TOML' in message for message in profile.warnings))

    def test_pathological_logs_are_bounded_before_analysis_and_redaction(self):
        self.run_bounded(
            'from minecode_runtime.failure_evidence import diagnose; '
            'from minecode_runtime.diagnostics import analyze; '
            's = "a." * 63000 + "\\nCaused by: OutOfMemoryError: heap"; '
            'a = analyze(s); d = diagnose(s); '
            'assert a.input_truncated and d.input_truncated; '
            'assert d.category == "memory"; assert "line 2:" in d.evidence[0]'
        )

    def test_oversized_lines_cannot_leak_a_partial_secret(self):
        result = diagnose('password=' + 's' * 3000 + '\nCaused by: OutOfMemoryError: heap')
        self.assertTrue(result.input_truncated)
        self.assertNotIn('ssss', result.model_dump_json())
        self.assertEqual(result.category, 'memory')

    def test_redaction_expansion_cannot_exceed_analysis_input_limit(self):
        result = diagnose('token=x\n' * 16000)
        self.assertTrue(result.input_truncated)
        self.assertNotIn('token=x', result.model_dump_json())

    def test_redaction_keeps_valid_environment_and_repair_bounds(self):
        from minecode_runtime.failure_evidence import RepairEvidence
        result = diagnose('failure', FailureEnvironment(minecraft='token=x ' * 10, dependency='token=x ' * 20),
                          source='token=x ' * 30,
                          repair=RepairEvidence(attempted='token=x ' * 125))
        self.assertLessEqual(len(result.environment.minecraft), 80)
        self.assertLessEqual(len(result.environment.dependency), 160)
        self.assertLessEqual(len(result.source), 240)
        self.assertLessEqual(len(result.attempted_repair.attempted), 1000)
        self.assertNotIn('token=x', result.model_dump_json())

    def test_cached_snapshot_reads_do_not_need_a_writer_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'project'
            project.mkdir()
            cache = ReferenceCache(project, root / 'cache')
            source = {'id': 'docs', 'url': 'https://example.org/docs'}
            folder = cache.folder(source)
            location = folder / 'snapshot'
            location.mkdir(parents=True)
            snapshot = {'source_id': 'docs', 'location': str(location), 'kind': 'document', 'revision': 'test'}
            (location / 'document.txt').write_text('cached evidence')
            (folder / 'current.json').write_text(json.dumps(snapshot))
            (folder / 'fetch.lock').write_text('stale or active writer')
            self.assertEqual(cache.snapshot(source), snapshot)
            self.assertTrue((folder / 'fetch.lock').exists())
            with self.assertRaises(ValueError):
                cache.snapshot(source, refresh=True)

    def test_cache_accepts_linked_ancestors_but_rejects_linked_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / 'project'
            project.mkdir()
            home = root / 'home'
            home.mkdir()
            alias = root / 'home-alias'
            try:
                alias.symlink_to(home, target_is_directory=True)
            except OSError:
                self.skipTest('Creating directory symlinks is unavailable')
            cache = ReferenceCache(project, alias / '.minecode' / 'cache')
            self.assertEqual(cache.root, home / '.minecode' / 'cache')
            with self.assertRaises(ValueError):
                ReferenceCache(project, alias)
            with self.assertRaises(ValueError):
                ReferenceCache(project, alias / '..' / 'project' / 'cache')


class ArchiveBoundaryTests(unittest.TestCase):
    @staticmethod
    def archive(count=2, *, local_zip64=False):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as jar:
            for index in range(count):
                with jar.open(f'Example{index}.java', 'w', force_zip64=local_zip64) as entry:
                    entry.write(b'class Example { int needle; }')
        return output.getvalue()

    @staticmethod
    def zip64(raw):
        end = len(raw) - 22
        _, _, _, count, total, size, offset, _ = struct.unpack('<4s4H2LH', raw[end:])
        return (raw[:end] + struct.pack('<4sQ2H2L4Q', b'PK\x06\x06', 44, 45, 45, 0, 0,
                                       count, total, size, offset)
                + struct.pack('<4sLQL', b'PK\x06\x07', 0, end, 1)
                + struct.pack('<4s4H2LH', b'PK\x05\x06', 0, 0, 0xffff, 0xffff, 0xffffffff, 0xffffffff, 0))

    def rejected_before_indexing(self, raw, message='archive|ZIP|directory', **limits):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'small-sources.jar'
            path.write_bytes(raw)
            state = path.stat()
            snapshot = dict(location=str(path), size=state.st_size, mtime_ns=state.st_mtime_ns)
            for operation in (lambda: local_sources.matches(snapshot, {'needle'}),
                              lambda: local_sources.read(snapshot, 'Example0.java')):
                with self.subTest(operation=operation), (patch.multiple(local_sources, **limits) if limits else nullcontext()), \
                     patch.object(local_sources.zipfile, 'ZipFile') as constructor:
                    with self.assertRaisesRegex(ValueError, message):
                        operation()
                    constructor.assert_not_called()

    def test_classic_zip64_comments_and_prepended_archives_remain_readable(self):
        classic = self.archive()
        comment = classic[:-2] + struct.pack('<H', 7) + b'comment'
        for raw in (classic, comment, b'stub' + classic, self.zip64(classic),
                    b'stub' + self.zip64(classic), self.archive(local_zip64=True), self.archive(0)):
            with self.subTest(size=len(raw)), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'sources.jar'
                path.write_bytes(raw)
                state = path.stat()
                snapshot = dict(location=str(path), size=state.st_size, mtime_ns=state.st_mtime_ns)
                rows = local_sources.matches(snapshot, {'needle'})
                self.assertEqual(len(rows), 0 if raw == self.archive(0) else 2)
                if rows:
                    self.assertIn('int needle', local_sources.read(snapshot, 'Example0.java'))

    def test_excessive_classic_and_zip64_counts_rejected_before_indexing(self):
        for raw in (self.archive(3), self.zip64(self.archive(3))):
            self.rejected_before_indexing(raw, 'archive_entry_limit', MAX_ENTRIES=2)

    def test_directory_bytes_are_capped_before_indexing(self):
        for raw in (self.archive(), self.zip64(self.archive())):
            self.rejected_before_indexing(raw, 'archive_directory_byte_limit', MAX_DIRECTORY=46)

    def test_forged_small_entry_count_cannot_bypass_the_index_limit(self):
        raw = bytearray(self.archive(3))
        struct.pack_into('<2H', raw, len(raw) - 22 + 8, 1, 1)
        self.rejected_before_indexing(raw, 'archive_entry_limit', MAX_ENTRIES=2)

    def test_malformed_directory_records_and_footers_rejected_before_indexing(self):
        original = self.archive()
        directory = struct.unpack_from('<L', original, len(original) - 22 + 16)[0]
        mutations = []
        bad = bytearray(original)
        bad[directory:directory + 4] = b'NOPE'
        mutations.append(bad)
        bad = bytearray(original)
        struct.pack_into('<H', bad, directory + 28, 65535)
        mutations.append(bad)
        for position, format_, value in ((4, '<H', 1), (8, '<2H', (3, 3)), (16, '<L', len(original)),
                                         (20, '<H', 5)):
            bad = bytearray(original)
            struct.pack_into(format_, bad, len(bad) - 22 + position,
                             *(value if isinstance(value, tuple) else (value,)))
            mutations.append(bad)
        mutations.extend((original[:-1], original[-22:]))
        for raw in mutations:
            with self.subTest(raw=bytes(raw[-22:])):
                self.rejected_before_indexing(raw)

    def test_missing_split_or_extensible_zip64_metadata_is_rejected(self):
        original = self.archive()
        extended = self.zip64(original)
        missing = bytearray(original)
        struct.pack_into('<2H', missing, len(missing) - 22 + 8, 0xffff, 0xffff)
        bad_size = bytearray(extended)
        struct.pack_into('<Q', bad_size, len(bad_size) - 98 + 4, 45)
        split = bytearray(extended)
        struct.pack_into('<L', split, len(split) - 42 + 16, 2)
        wrong_offset = bytearray(extended)
        struct.pack_into('<Q', wrong_offset, len(wrong_offset) - 42 + 8, 0)
        for raw in (missing, bad_size, split, wrong_offset):
            self.rejected_before_indexing(raw, 'ZIP64|directory')


if __name__ == '__main__':
    unittest.main()
