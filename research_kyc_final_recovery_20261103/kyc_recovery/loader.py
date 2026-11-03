"""Real shared import chain; never aliases/deletes or patches sys.modules."""
from .common import *
import importlib
import inspect
import sys

EXPECTED = {
    'common': R/'scripts/common.py', 'experiment_lib': R/'scripts/experiment_lib.py',
    'utils': K/'utils.py', 'eval': K/'eval.py', 'models': K/'models/__init__.py',
    'cam_embedding': K/'cam_embedding.py', 'models.act': K/'models/act.py',
    'models.detr_vae': K/'models/detr_vae.py',
}
ORDER = ['experiment_lib', 'common', 'utils', 'eval', 'models', 'cam_embedding',
         'models.act', 'models.detr_vae']


def origins(module):
    return dict(name=module.__name__, file=str(Path(module.__file__).resolve()),
                spec_origin=str(Path(module.__spec__.origin).resolve()),
                module_id=id(module), spec_name=module.__spec__.name,
                sys_modules_same_object=sys.modules.get(module.__name__) is module)


def load_actual():
    # Validate preexisting names rather than evicting or augmenting them.
    for name, path in EXPECTED.items():
        if name in sys.modules:
            require(Path(sys.modules[name].__file__).resolve() == path.resolve(),
                    'wrong preexisting upstream identity: '+name)
    for path in [str(K), str(R/'scripts')]:
        if path not in sys.path:
            sys.path.insert(0, path)
    modules = {}
    records = []
    for name in ORDER:
        module = importlib.import_module(name)
        record = origins(module)
        require(Path(record['file']) == EXPECTED[name].resolve()
                and Path(record['spec_origin']) == EXPECTED[name].resolve()
                and record['sys_modules_same_object'], 'wrong actual upstream import: '+name)
        modules[name] = module; records.append(record)
    lib, official = modules['experiment_lib'], modules['common']
    require(official.ROOT == lib.ROOT == R and lib.DATA == R/'assets/liftrand_eef_delta.hdf5',
            'ROOT/DATA semantics mismatch')
    require(lib.atomic_json is official.atomic_json and lib.utc is official.utc,
            'upstream helper identity mismatch')
    require(sys.modules['common'] is not sys.modules['kyc_recovery.common'], 'harness namespace collision')
    return modules, dict(order=ORDER, modules=records, ROOT=str(official.ROOT), DATA=str(lib.DATA),
                        helpers={n:dict(module=getattr(official,n).__module__,
                         source=inspect.getsourcefile(getattr(official,n))) for n in ['atomic_json','utc']},
                        harness_common=origins(sys.modules['kyc_recovery.common']),
                        constructor_signatures={'ACTPolicy':str(inspect.signature(modules['models.act'].ACTPolicy)),
                          'DETRVAE.forward':str(inspect.signature(modules['models.detr_vae'].DETRVAE.forward)),
                          'Dataset':str(inspect.signature(modules['utils'].EpisodicDataset))})
