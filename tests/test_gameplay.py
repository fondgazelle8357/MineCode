import copy
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError
from minecode_runtime.gameplay import MAX_OUTPUT, Registry, load_registry, search_techniques


class GameplayTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_registry()

    def test_inventory_and_context(self):
        self.assertEqual(len(self.registry.entries), 24)
        self.assertEqual(len({e.category for e in self.registry.entries}), 9)
        for entry in self.registry.entries:
            self.assertTrue(entry.sources)
            self.assertTrue(entry.version_relevance)
            self.assertTrue(entry.known_uncertainty)
            self.assertIn('MineCode analysis', entry.automation_relevance)

    def test_aliases_and_natural_queries(self):
        for query, expected in [('IPC', 'instant-pearl-catch'), ('What is a P-crit?', 'p-crit'),
                                ('Ｗ－ｔａｐ', 'w-tap'), ('stunslam', 'stun-slam'), ('slam', 'smash')]:
            self.assertEqual(search_techniques(query).results[0].id, expected)
        self.assertEqual(search_techniques('unlisted nonexistent terminology').results, [])
        self.assertEqual(search_techniques('IPC', category='shield').results, [])
        self.assertEqual(search_techniques('shipping').results, [])  # IPC is not a substring search.

    def test_duplicates_and_broken_links_fail_closed(self):
        original = self.registry.model_dump()
        mutations = [lambda d: d['entries'].append(copy.deepcopy(d['entries'][0])),
                     lambda d: d['entries'][1]['aliases'].append('Ｗ－ＴＡＰ'),
                     lambda d: d['entries'][0]['related'].append('missing'),
                     lambda d: d['entries'][0]['aliases'].append('!!!')]
        for mutate in mutations:
            data = copy.deepcopy(original)
            mutate(data)
            with self.assertRaises(ValidationError):
                Registry.model_validate(data)

    def test_missing_context_and_invalid_provenance(self):
        for field in ['version_relevance', 'server_dependence', 'timing_dependence', 'sources']:
            data = self.registry.model_dump()
            del data['entries'][0][field]
            with self.assertRaises(ValidationError):
                Registry.model_validate(data)
        data = self.registry.model_dump()
        data['entries'][0]['sources'][0]['url'] = 'file:///private'
        with self.assertRaises(ValidationError):
            Registry.model_validate(data)

    def test_bounds_and_determinism(self):
        for query, limit in [('',3),('!'*5,3),('a'*301,3),('mace',True),('mace',6),('mace',0)]:
            with self.assertRaises(ValueError):
                search_techniques(query, limit)
        self.assertEqual(search_techniques('mace').model_dump(), search_techniques('mace').model_dump())
        for entry in self.registry.entries:
            self.assertLessEqual(len(search_techniques(entry.name, 5).model_dump_json()), MAX_OUTPUT)

    def test_result_limit_reports_omitted_matches(self):
        self.assertGreater(len(search_techniques('mace', 5).results), 1)
        self.assertTrue(search_techniques('mace', 1).truncated)
        self.assertFalse(search_techniques('IPC', 1).truncated)

    def test_large_valid_entries_keep_whole_provenance(self):
        data = self.registry.model_dump()
        for entry in data['entries']:
            for key in ['definition','mechanic','version_relevance','server_dependence','timing_dependence',
                        'client_server_relevance','development_relevance','automation_relevance','known_uncertainty']:
                entry[key] = 'mace ' * 150
        registry = Registry.model_validate(data)
        result = search_techniques('mace', 5, registry=registry)
        self.assertTrue(result.truncated)
        self.assertTrue(result.results)
        self.assertLessEqual(len(result.model_dump_json()), MAX_OUTPUT)
        self.assertTrue(all(e.sources for e in result.results))

    def test_registry_file_size_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'oversized.json'
            path.write_bytes(b' ' * 262145)
            with self.assertRaises(ValueError):
                load_registry(path)
