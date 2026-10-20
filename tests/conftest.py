from pathlib import Path
import pytest
import yaml
from spatial_pilot.scenes import build_scene
from spatial_pilot.oracle import label_scene

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='session')
def config():
    return yaml.safe_load((ROOT/'configs/pilot.yaml').read_text())


@pytest.fixture(scope='session')
def verified(config):
    cache = {}
    def get(family, variant):
        key = (family, variant)
        if key not in cache:
            scene = build_scene(family, variant, config)
            cache[key] = (scene, label_scene(scene, config))
        return cache[key]
    return get
