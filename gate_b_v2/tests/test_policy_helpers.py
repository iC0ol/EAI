from gate_b_v2.policy import coerce_bool


def test_coerce_bool_handles_yaml_strings_and_native_bools():
    assert coerce_bool(True) is True
    assert coerce_bool(False) is False
    assert coerce_bool("True") is True
    assert coerce_bool("false") is False
    assert coerce_bool("1") is True
    assert coerce_bool(0) is False
