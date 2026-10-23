import datetime
import tempfile
import unittest
from pathlib import Path

import numpy as np

from live_screen.io import ROOT,OUT,LOCAL,read_json,read_csv,config,sha256
from live_screen.audit import Ledger
from live_screen.analysis import gate,signed_summary
from live_screen.baselines import features,matrix,fit_all,eigen_jacobian
from m_direction.perturb import DIRECTIONS,intervention


def synthetic(episode,sid,nominal=1,values=None):
    base={'source_episode':episode,'state_id':sid,'split':'development','stage':'B1','status':'completed',
          'geometry':{'object_rotation':np.eye(3),'task_rotation':np.eye(3),'contact_rotation':None}}
    rows=[base|{'branch_id':f'{sid}_n','direction':'nominal','sign':0,'ever_success':bool(nominal)}]
    for d in DIRECTIONS:
        for sign in [-1,1]:
            y=values.get((d,sign),nominal) if values else nominal
            rows.append(base|{'branch_id':f'{sid}_{d}_{sign}','direction':d,'sign':sign,'ever_success':bool(y)})
    return rows


class CoreTests(unittest.TestCase):
    def test_plan_split_and_all160_nominal_accounting(self):
        p=read_csv(OUT/'branch_plan.csv');self.assertEqual(len(p),160)
        self.assertEqual(len({r['branch_id'] for r in p}),160)
        self.assertEqual([sum(r['stage']==s for r in p) for s in ['A','B1','B2','B3']],[4,56,48,52])
        self.assertEqual(sum(r['direction']=='nominal' for r in p),16)
        self.assertFalse(any(r['stage']=='B2' and r['direction']=='nominal' for r in p))
        s=read_csv(OUT/'frozen_state_manifest.csv')
        dev={r['source_episode'] for r in s if r['split']=='development'};held={r['source_episode'] for r in s if r['split']=='held-out'}
        self.assertEqual((len(dev),len(held),len(dev&held)),(4,2,0))

    def test_perturbations_equal_norm_other4_unchanged_and_clip_rejected(self):
        a=np.array([.12,-.23,.35,.1,-.1,.2,1.])
        for d in DIRECTIONS:
            for sign in [-1,1]:
                action,delta=intervention(a,d,sign,.2)
                self.assertAlmostEqual(np.linalg.norm(delta),.2,places=14)
                np.testing.assert_array_equal(action[3:],a[3:])
        with self.assertRaises(ValueError):intervention([.8,0,0,0,0,0,1],'x',1,.2)

    def test_full3x3_design_and_frame_norm(self):
        axes=np.stack([features(DIRECTIONS[x]) for x in ['x','y','z']])
        all6=np.stack([features(d) for d in DIRECTIONS.values()])
        self.assertEqual(np.linalg.matrix_rank(axes),3);self.assertEqual(np.linalg.matrix_rank(all6),6)
        p=np.array([1.5,.8,.7,.2,-.1,.05]);M=matrix(p)
        R=np.array([[0.,-1,0],[1,0,0],[0,0,1]])
        for d in DIRECTIONS.values():
            self.assertAlmostEqual(float(features(d)@p),float(d@M@d))
            self.assertAlmostEqual(np.linalg.norm(R.T@d),1.)
            np.testing.assert_allclose(features(d),features(-d),atol=0,rtol=0)
        eps=1e-6
        numeric=np.column_stack([(np.linalg.eigvalsh(matrix(p+eps*e))-np.linalg.eigvalsh(matrix(p-eps*e)))/(2*eps) for e in np.eye(6)])
        np.testing.assert_allclose(eigen_jacobian(p),numeric,atol=1e-8,rtol=0)

    def test_warning_requires_different_sources_and_directions(self):
        a=synthetic('ep1','S00',1,{('x',1):0})
        self.assertFalse(signed_summary(a)['strong_symmetric_PSD_warning'])
        b=synthetic('ep2','S02',1,{('y',1):0})
        self.assertTrue(signed_summary(a+b)['strong_asymmetry_warning'])
        self.assertFalse(gate('B1',a+b)['continue'])
        same=synthetic('ep1','S01',1,{('y',1):0})
        self.assertFalse(signed_summary(a+same)['strong_symmetric_PSD_warning'])

    def test_improvement_is_negative_and_uninformative_stops(self):
        rows=synthetic('ep1','S00',0,{('x',1):1})
        self.assertEqual(next(r['delta_Y'] for r in signed_summary(rows)['signed_rows'] if r['direction']=='x' and r['sign']==1),-1)
        noinfo=synthetic('ep1','S00')+synthetic('ep2','S02')
        self.assertFalse(gate('B1',noinfo)['continue'])
        self.assertIn('insufficient',gate('B1',noinfo)['decision'])

    def test_attempt_guard_includes_failures_and_stage_caps(self):
        LOCAL.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=LOCAL) as temp:
            ledger=Ledger(Path(temp));first={'branch_id':'A0','stage':'A'}
            ledger.reserve(first,False)
            with self.assertRaises(RuntimeError):ledger.reserve(first,False)
            with self.assertRaises(RuntimeError):ledger.reserve({'branch_id':'A1','stage':'A'},False)
            ledger.append({'event':'finished','branch_id':'A0','stage':'A','status':'invalid'})
            for i in range(1,4):
                ledger.reserve({'branch_id':f'A{i}','stage':'A'},False);ledger.append({'event':'finished','branch_id':f'A{i}','stage':'A'})
            with self.assertRaises(RuntimeError):ledger.reserve({'branch_id':'A4','stage':'A'},False)

    def test_fixed_fits_are_dev_only_and_contact_missing_is_unavailable(self):
        values={(d,s):int(d in ['y','z','yz']) for d in DIRECTIONS for s in [-1,1]}
        dev=synthetic('ep1','S00',1,values)+synthetic('ep2','S02',1,values)
        held=[r|{'split':'held-out','stage':'B3'} for r in synthetic('forbidden','S08',0)]
        fits=fit_all(dev+held)
        for name in ['world_diag','world_full_PSD3x3','object_full_PSD3x3','task_full_PSD3x3']:
            self.assertTrue(fits[name]['available'],fits[name])
            M=fits[name]['matrix'];self.assertAlmostEqual(np.trace(M),3,places=6)
            self.assertGreaterEqual(np.linalg.eigvalsh(M).min(),-1e-7)
            self.assertNotIn('forbidden',fits[name]['dev_ranks']['informative_episodes'])
        self.assertFalse(fits['contact_full_PSD3x3_if_reliable']['available'])

    def test_preregistration_and_absolute_deadline(self):
        r=read_json(OUT/'registration.json')
        for p,h in r['frozen_files'].items():self.assertEqual(sha256(ROOT/p),h,p)
        self.assertEqual(r['new_simulation_steps'],0)
        self.assertEqual(datetime.datetime.fromtimestamp(config()['absolute_outer_deadline_unix'],datetime.timezone.utc).isoformat(),'2026-10-23T21:00:40+00:00')


if __name__=='__main__':unittest.main(verbosity=2)
