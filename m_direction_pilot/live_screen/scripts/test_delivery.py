"""Validate delivered values against the immutable attempt records and local raw arrays."""
import csv
import gzip
import json
import unittest

import numpy as np

from live_screen.io import ROOT,OUT,read_json,read_csv,sha256
from live_screen.analysis import results
from live_screen.audit import verify,Ledger


class DeliveryTests(unittest.TestCase):
    def test_public_trace_roundtrip_every_array_and_branch(self):
        index=read_csv(OUT/'trace_index.csv')
        self.assertEqual(len(index),len(results()))
        for row in index:
            p=ROOT/row['public_path'];self.assertEqual(sha256(p),row['public_sha256'])
            self.assertEqual(sha256(ROOT/row['local_npz']),row['local_npz_sha256'])
            arrays=json.loads(row['arrays']);collected={k:[] for k in arrays}
            with gzip.open(p,'rt',newline='') as f:
                for r in csv.DictReader(f):collected[r['array']].append(json.loads(r['values_json']))
            with np.load(ROOT/row['local_npz']) as raw:
                self.assertEqual(set(raw.files),set(arrays))
                for key,spec in arrays.items():
                    value=np.asarray(collected[key],dtype=spec['dtype']).reshape(spec['shape'])
                    np.testing.assert_array_equal(value,raw[key],err_msg=f"{row['branch_id']}: {key}")

    def test_allocation_missingness_ledger_and_preserved_protocol(self):
        verify();records=results();index={r['branch_id']:r for r in records}
        actual=read_csv(OUT/'all160_allocations_actual.csv');plan=read_csv(OUT/'branch_plan.csv')
        self.assertEqual(len(actual),160);self.assertEqual(len({r['branch_id'] for r in actual}),160)
        for row,p in zip(actual,plan):
            self.assertEqual({k:row[k] for k in p},p)
            r=index.get(p['branch_id'])
            if r and r['status']=='completed':self.assertEqual(int(row['Y']),int(r['ever_success']))
            else:self.assertEqual(row['Y'],'')
        self.assertEqual(len(read_csv(OUT/'all12_states_actual.csv')),12)
        events=Ledger().events();started=[e for e in events if e['event']=='started'];ended=[e for e in events if e['event']=='finished']
        self.assertEqual(len(started),len(ended));self.assertEqual(len(started),len(records));self.assertLessEqual(len(started),160)
        a=read_json(OUT/'final_audit.json');self.assertTrue(a['passed'])
        self.assertEqual(a['unused_allocations'],160-len(records))
        self.assertEqual(a['partial_integration_steps'],0)


if __name__=='__main__':unittest.main(verbosity=2)
