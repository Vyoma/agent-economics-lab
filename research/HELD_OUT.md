# The detector on code it has never seen

The rule was abstracted from five defects in `agent_economics` and then
evaluated on `agent_economics`. That is fitting to your own training set, and
no claim survives it. This is the held-out run: the same detector, unchanged,
pointed at six mature standard-library packages.

Read the negative result first.

## What it did not do

**It found no defect in any standard-library package.** The divergences below
are real -- these call sites genuinely disagree -- and every one inspected was
deliberate. `asyncio._ensure_resolved(..., flags=)` is passed by four callers
and omitted by `selector_events.py:642`, because that path connects to an
already-resolved address where lookup flags do not apply and `flags=0` is
correct.

So the honest claim is not "a defect detector that works on any codebase". On
mature code this produces a short, readable list of intentional design
decisions. Converting a divergence into a defect took domain knowledge in every
case where it worked.

## What it did do

It found a defect in **itself**, immediately, which is the reason to run
held-out evaluations at all. The first run reported `__init__(..., stdout=)` as
"1 caller passes, 33 omit" across asyncio. That is not one function with
disagreeing callers; it is 34 unrelated constructors conflated by name. The
detector matched call sites to definitions by name alone, which happened to be
safe in a package of unique module-level functions and is garbage anywhere
else. Names that resolve ambiguously are now dropped entirely, and dunders with
them. Before that fix the six standard-library packages reported 78
divergences; after it, 34.

## The measurement

Generated on CPython 3.12.13.

| package | files | lines | divergences | per kLOC | lone dissenters |
|---|---|---|---|---|---|
| `agent_economics` | 27 | 11341 | 17 | 1.5 | 4 |
| `json` | 5 | 1317 | 7 | 5.32 | 0 |
| `logging` | 3 | 5047 | 1 | 0.2 | 0 |
| `email` | 29 | 10415 | 6 | 0.58 | 2 |
| `http` | 5 | 5841 | 1 | 0.17 | 0 |
| `asyncio` | 33 | 14377 | 7 | 0.49 | 3 |
| `unittest` | 13 | 6798 | 12 | 1.77 | 2 |

## agent_economics: most lopsided divergences

```
make_evidence_bundle(..., dependency_edges=)  5 pass / 1 omit
    the omits: assurance.py:524
make_evidence_bundle(..., label_source=)  5 pass / 1 omit
    the omits: assurance.py:524
make_evidence_bundle(..., source_version=)  5 pass / 1 omit
    the omits: assurance.py:524
_numeric_issue(..., integer=)  2 pass / 8 omit
    the passes: evidence.py:86, evidence.py:308
_numeric_issue(..., maximum=)  2 pass / 8 omit
    the passes: evidence.py:260, evidence.py:299
```


## json: most lopsided divergences

```
iterencode(..., _one_shot=)  1 pass / 2 omit
    the passes: encoder.py:200
loads(..., cls=)  1 pass / 1 omit
    the omits: tool.py:65
loads(..., object_hook=)  1 pass / 1 omit
    the omits: tool.py:65
loads(..., object_pairs_hook=)  1 pass / 1 omit
    the omits: tool.py:65
loads(..., parse_constant=)  1 pass / 1 omit
    the omits: tool.py:65
```


## logging: most lopsided divergences

```
convert_with_key(..., replace=)  2 pass / 3 omit
    the passes: config.py:353, config.py:370
```


## email: most lopsided divergences

```
get_param(..., header=)  1 pass / 8 omit
    the passes: message.py:768
set_param(..., header=)  1 pass / 5 omit
    the passes: contentmanager.py:120
set_param(..., replace=)  2 pass / 4 omit
    the passes: contentmanager.py:189, contentmanager.py:120
_add_multipart(..., _disp=)  2 pass / 1 omit
    the omits: message.py:1195
get_payload(..., decode=)  7 pass / 12 omit
    the passes: contentmanager.py:65, contentmanager.py:72, encoders.py:30
```


## http: most lopsided divergences

```
parse_headers(..., _class=)  1 pass / 1 omit
    the omits: client.py:355
```


## asyncio: most lopsided divergences

```
add_done_callback(..., context=)  1 pass / 32 omit
    the passes: tasks.py:351
_ensure_resolved(..., flags=)  4 pass / 1 omit
    the omits: selector_events.py:642
_ensure_resolved(..., proto=)  4 pass / 1 omit
    the omits: base_events.py:1470
ensure_future(..., loop=)  5 pass / 2 omit
    the omits: tasks.py:898, tasks.py:508
_create_connection_transport(..., server_side=)  1 pass / 2 omit
    the passes: base_events.py:1637
```


## unittest: most lopsided divergences

```
testPartExecutor(..., subTest=)  1 pass / 4 omit
    the passes: case.py:538
_createClassOrModuleLevelException(..., info=)  2 pass / 6 omit
    the passes: suite.py:320, suite.py:182
_calls_repr(..., prefix=)  1 pass / 3 omit
    the passes: mock.py:989
_makeLoader(..., testNamePatterns=)  1 pass / 2 omit
    the passes: loader.py:475
create_autospec(..., _name=)  2 pass / 1 omit
    the omits: mock.py:688
```


## Reading the table honestly

After the conflation fix, the four most mature packages sit well below one
divergence per kLOC. `agent_economics` and `unittest` sit above it.

That separation is suggestive and it is not evidence. "Maturity" is not
measured here, the sample is six packages, `json` is small enough that its rate
rests on seven divergences, and nothing establishes that divergence density
tracks defect density in either direction. A reader who concludes "this repo is
three times buggier than asyncio" has read something that was not written.

What the table supports is narrower: the detector emits a list short enough to
read by hand on every package tried, which is the minimum bar for a reading
aid, and the density is not so uniform that it is obviously measuring nothing.

## What this settles about the method

The compounding claim was that each defect yields a shape, each shape
enumerates sites, so the detector improves with use. This run is evidence for
the loop and against the strong form of the claim.

For: the loop ran, on the tool itself, and produced a real correction that no
amount of staring at `agent_economics` would have surfaced.

Against: enumeration without domain knowledge did not convert into defects on
unfamiliar code. The three prospective findings in this repository were found
because the author knew which of eighteen divergences would matter. That is a
reading aid for an expert, not an oracle, and the difference is the whole
distance between a tool and a moat.
