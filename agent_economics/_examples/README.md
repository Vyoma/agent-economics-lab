Packaged copies of the five files in `examples/`, so `agent-economics demo`
runs without a clone and `agent-economics demo --extract .` hands you the
templates to edit.

They are copies, which is a drift risk, so
`tests/test_packaging.py` fails the build if any of them stops being
byte-identical to the file in `examples/` that it mirrors.
