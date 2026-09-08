# Oracle Layout

`base/` contains the canonical L1, L2, and L3 files. `coevolved/` contains only the 573 files retained after human adjudication. These are the only two directories loaded by the evaluator.

Machine-readable metadata:

- `base_manifest.json`: task, level, relative path, and exact pytest item count.
- `manifest.json`: retained candidate metadata, paper-facing round, contract traces, relative path, and exact pytest item count.

One pytest file can contain parameterized tests and therefore contribute more than one item. This is why 573 retained files correspond to 589 pytest items.
