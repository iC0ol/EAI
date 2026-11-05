"""Pure Python logical ACT counter; matching policy/internal entry counts once."""
class CallGuard:
    def __init__(self, reserve, note):
        self.reserve = reserve; self.note = note
        self.pending = None; self.active = None; self.policy_entries = 0; self.internal_entries = 0

    def expect(self, item):
        if self.pending is not None or self.active is not None:
            raise RuntimeError('unfinished model call')
        self.pending = item

    def policy_enter(self, branch, keys=None, batch=None, *, data=None):
        # Reserve first: implicit/failed attempts are not refunded.
        ordinal = self.reserve('ACT', 'model', 'policy_entry')
        self.policy_entries += 1
        if data is not None:
            keys = data.keys() if isinstance(data, dict) else []
            batch = data['image'].shape[0] if isinstance(data, dict) and 'image' in data else -1
        if self.active is not None or self.pending is None:
            raise RuntimeError('unplanned/reentrant ACTPolicy call')
        item = self.pending; self.pending = None
        expected = {'image', 'qpos', 'cam_extrinsics'}
        if item['branch'] == 'official_posterior':
            raise RuntimeError('posterior forbidden in grasp diagnostic')
        if branch != item['branch'] or set(keys) != expected or batch != 1:
            raise RuntimeError('wrong branch/keys/batch; prior labels forbidden')
        self.active = dict(item=item, ordinal=ordinal, internal=0)
        self.note('POLICY_ENTER', self.active)
        return self.active

    def internal_enter(self, has_labels=None, batch=None, *, data=None):
        if self.active is None or self.active['internal'] != 0:
            self.reserve('ACT', 'model', 'implicit_or_extra_internal_forward')
            raise RuntimeError('unplanned/extra internal model forward')
        self.active['internal'] += 1
        self.internal_entries += 1
        if data is not None:
            has_labels = isinstance(data, dict) and data.get('actions') is not None
            batch = data['image'].shape[0] if isinstance(data, dict) and 'image' in data else -1
        posterior = self.active['item']['branch'] == 'official_posterior'
        if has_labels != posterior or batch != 1:
            raise RuntimeError('internal prior/posterior or batch mismatch')
        self.note('INTERNAL_FORWARD_ENTER', self.active)

    def complete(self):
        if self.active is None or self.active['internal'] != 1:
            raise RuntimeError('expected exactly one internal forward')
        self.note('POLICY_COMPLETE', self.active)
        self.active = None
