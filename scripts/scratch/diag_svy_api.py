# scripts/scratch/diag_svy_api.py
# Ground-truth API introspection for the INSTALLED svy 0.19.0 stack.
#
# INTENT: enumerate the real, installed API surface of svy/svy-rs/svy-io so the smoke
#   test (smoke_svy_a.py) and the downstream skill revision encode observed behavior,
#   not the partly-aspirational online docs. Triggered by smoke_svy.py failing at
#   `svy.Design(..., fpc="fpc_pop")` -> TypeError: unexpected keyword argument 'fpc'.
# REASONING: the online research (preliminary_notes/03) documented
#   `svy.Design(wgt=, stratum=, psu=, ssu=, prob=, fpc=)` and `svy.io.read_stata(...)`,
#   but the installed reality differs. Introspection (inspect.signature + dir + docstrings)
#   is authoritative; docs are not. Every probe is wrapped so one failure never aborts the
#   whole map -- this script must emit the COMPLETE surface in a single run.
# ASSUMES: svy imports; a Design/Sample can be built once the true Design signature is known.
#   Synthetic frame mirrors the smoke test's columns so namespace method calls are realistic.

# --- Config ---
import inspect
import importlib
import traceback

import numpy as np
import polars as pl
import svy


def show_sig(label, obj):
    # INTENT: print a callable's signature + first docstring line; degrade gracefully.
    # REASONING: signature is the primary evidence; docstring first line disambiguates
    #   uninformative *args/**kwargs signatures.
    try:
        sig = inspect.signature(obj)
        print(f"  SIG {label}{sig}")
    except (ValueError, TypeError) as e:
        print(f"  SIG {label}: <no signature: {e!r}>")
    try:
        doc = inspect.getdoc(obj)
        if doc:
            first = doc.strip().splitlines()[0]
            print(f"  DOC {label}: {first}")
    except Exception as e:  # noqa: BLE001
        print(f"  DOC {label}: <unavailable: {e!r}>")


print("=" * 70)
print("svy 0.19.0 API INTROSPECTION")
print("=" * 70)
print(f"svy.__version__ = {svy.__version__}")
print(f"svy.__file__    = {getattr(svy, '__file__', '<none>')}")
print(f"polars          = {pl.__version__}")
print(f"numpy           = {np.__version__}")
print()

# --- Top-level module surface ---
print("--- dir(svy) [public] ---")
_pub = [a for a in dir(svy) if not a.startswith("_")]
print(f"  {_pub}")
print()

# --- Constructor signatures for the documented top-level classes ---
print("--- Top-level class __init__ signatures ---")
for _name in ("Design", "Sample", "RepWeights", "Cat", "Cap"):
    _obj = getattr(svy, _name, None)
    if _obj is None:
        print(f"  {_name}: ABSENT from svy namespace")
        continue
    print(f"  [{_name}] present ({type(_obj).__name__})")
    show_sig(f"{_name}.__init__", getattr(_obj, "__init__", _obj))
    # Also show the class-level docstring first line for context.
    try:
        _cdoc = inspect.getdoc(_obj)
        if _cdoc:
            print(f"  CLASSDOC {_name}: {_cdoc.strip().splitlines()[0]}")
    except Exception:  # noqa: BLE001
        pass
print()

# --- Build a synthetic frame mirroring the smoke test columns ---
rng = np.random.default_rng(42)
n_strata, n_psu, n_obs = 4, 6, 20
n = n_strata * n_psu * n_obs
stratum = np.repeat(np.arange(1, n_strata + 1), n_psu * n_obs)
psu = np.repeat(np.arange(1, n_strata * n_psu + 1), n_obs)
weight = rng.uniform(0.5, 5.0, size=n)
income = 30000.0 + 500.0 * stratum + rng.normal(0.0, 5000.0, size=n)
age = rng.integers(18, 81, size=n).astype(float)
gender = rng.choice(["Male", "Female"], size=n)
_p = 1.0 / (1.0 + np.exp(-(-1.0 + 0.02 * age + 0.5 * (gender == "Male"))))
employed = rng.binomial(1, _p).astype(float)
visit_count = rng.poisson(np.exp(0.5 + 0.01 * age / 10.0)).astype(float)
fpc_pop = np.select(
    [stratum == 1, stratum == 2, stratum == 3, stratum == 4],
    [5000.0, 6000.0, 7000.0, 8000.0],
)
df = pl.DataFrame({
    "stratum": stratum, "psu": psu, "weight": weight, "income": income,
    "age": age, "gender": gender, "employed": employed,
    "visit_count": visit_count, "fpc_pop": fpc_pop,
})
print(f"Synthetic frame: {df.height} rows x {df.width} cols\n")

# --- Build a Design using ONLY parameters the real signature accepts ---
# INTENT: construct a valid Design without guessing -- match real param names to columns.
# REASONING: smoke_svy.py passed fpc=; the installed sig rejected it. Derive accepted params
#   from the signature and map by name so this works regardless of the exact naming.
print("--- Design construction (signature-driven) ---")
design = None
sample = None
try:
    _dsig = inspect.signature(svy.Design.__init__)
    _params = [p for p in _dsig.parameters if p != "self"]
    print(f"  Design accepts params: {_params}")
    # Candidate value map: try several likely names -> our columns.
    _candidates = {
        "wgt": "weight", "weight": "weight", "weights": "weight",
        "stratum": "stratum", "strata": "stratum", "strata": "stratum",
        "psu": "psu", "cluster": "psu", "clusters": "psu",
        "ssu": None, "prob": None, "probs": None,
        "fpc": "fpc_pop", "fpc_psu": "fpc_pop", "fpc_ssu": None,
    }
    _kwargs = {}
    for _p in _params:
        if _p in _candidates and _candidates[_p] is not None:
            _kwargs[_p] = _candidates[_p]
    print(f"  Constructing svy.Design(**{_kwargs})")
    design = svy.Design(**_kwargs)
    print(f"  Design built OK -> {type(design).__name__}")
    print(f"  dir(design) [public]: {[a for a in dir(design) if not a.startswith('_')]}")
except Exception as e:  # noqa: BLE001
    print(f"  Design construction FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()
print()

# --- Probe whether fpc is accepted at all (the original failure) ---
print("--- fpc acceptance probe (original failure point) ---")
for _try in (
    {"wgt": "weight", "stratum": "stratum", "psu": "psu", "fpc": "fpc_pop"},
    {"weight": "weight", "stratum": "stratum", "psu": "psu", "fpc": "fpc_pop"},
):
    try:
        _d = svy.Design(**_try)
        print(f"  ACCEPTED: svy.Design(**{_try}) -> OK")
    except Exception as e:  # noqa: BLE001
        print(f"  REJECTED: svy.Design(**{_try}) -> {type(e).__name__}: {e}")
print()

# --- Build a Sample (try positional and data= keyword) ---
print("--- Sample construction ---")
if design is not None:
    _ssig = inspect.signature(svy.Sample.__init__)
    print(f"  Sample.__init__ params: {[p for p in _ssig.parameters if p != 'self']}")
    for _label, _mk in (
        ("positional df", lambda: svy.Sample(df, design=design)),
        ("data= keyword", lambda: svy.Sample(data=df, design=design)),
    ):
        try:
            sample = _mk()
            print(f"  Sample built via {_label} -> {type(sample).__name__}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  Sample via {_label} FAILED: {type(e).__name__}: {e}")
print()

# --- Namespace introspection on the constructed Sample ---
if sample is not None:
    print(f"--- dir(sample) [public]: {[a for a in dir(sample) if not a.startswith('_')]}")
    for _ns_name in ("estimation", "weighting", "glm", "wrangling"):
        _ns = getattr(sample, _ns_name, None)
        print(f"\n=== sample.{_ns_name} ===")
        if _ns is None:
            print(f"  ABSENT")
            continue
        _methods = [a for a in dir(_ns) if not a.startswith("_")]
        print(f"  methods/attrs: {_methods}")
        for _m in _methods:
            _attr = getattr(_ns, _m, None)
            if callable(_attr):
                show_sig(f"{_ns_name}.{_m}", _attr)
    print()

# --- svy-io resolution ---
print("--- svy-io module resolution ---")
_io = getattr(svy, "io", None)
if _io is not None:
    print(f"  svy.io present (submodule) -> {getattr(_io, '__name__', '<?>')}")
else:
    print("  svy.io ABSENT as submodule; trying separate packages")
    for _cand in ("svy_io", "svyio"):
        try:
            _io = importlib.import_module(_cand)
            print(f"  imported '{_cand}' -> {getattr(_io, '__file__', '<?>')}")
            break
        except Exception as e:  # noqa: BLE001
            print(f"  import {_cand} FAILED: {type(e).__name__}: {e}")
if _io is not None:
    _io_pub = [a for a in dir(_io) if not a.startswith("_")]
    print(f"  dir(io) [public]: {_io_pub}")
    for _fn in _io_pub:
        _obj = getattr(_io, _fn, None)
        if callable(_obj):
            show_sig(f"io.{_fn}", _obj)
print()

# --- GLM family probe (structure only; discovery, not correctness) ---
print("--- glm.fit family probe ---")
if sample is not None and getattr(sample, "glm", None) is not None:
    for _fam, _y in (("gaussian", "income"), ("binomial", "employed"),
                     ("poisson", "visit_count"), ("gamma", "income")):
        try:
            _m = sample.glm.fit(y=_y, x=["age", "gender"], family=_fam)
            _cols = _m.to_polars().columns if hasattr(_m, "to_polars") else "<no to_polars>"
            print(f"  family={_fam!r} OK -> result {type(_m).__name__}; coef cols {_cols}")
            if _fam == "binomial":
                # capture margins() shape for the probe section of the smoke test
                try:
                    _mg = _m.margins()
                    print(f"    margins() OK -> {type(_mg).__name__}; "
                          f"{_mg.to_polars().columns if hasattr(_mg, 'to_polars') else repr(_mg)[:120]}")
                except Exception as e:  # noqa: BLE001
                    print(f"    margins() FAILED: {type(e).__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  family={_fam!r} FAILED: {type(e).__name__}: {e}")
print()

print("=" * 70)
print("INTROSPECTION COMPLETE")
print("=" * 70)


# =============================================================================
# EXECUTION LOG
# =============================================================================
#
# Executed: 2026-07-15 02:26:29
# Command: python3 /daaf/scripts/scratch/diag_svy_api.py
# Duration: 2s
# Exit code: 1
#
# --- STDOUT ---
# ======================================================================
# svy 0.19.0 API INTROSPECTION
# ======================================================================
# svy.__version__ = 0.19.0
# svy.__file__    = /usr/local/lib/python3.12/dist-packages/svy/__init__.py
# polars          = 1.39.3
# numpy           = 2.4.2
# 
# --- dir(svy) [public] ---
#   ['Cap', 'CaseStyle', 'Cat', 'Categorical', 'Category', 'CellEst', 'ChiSquare', 'Cross', 'DF', 'DT', 'DatasetError', 'DescribeResult', 'Design', 'DimensionError', 'Estimate', 'Estimation', 'EstimationMethod', 'FDist', 'Feature', 'FitMethod', 'GLM', 'GLMFit', 'GLMPred', 'LabelError', 'LetterCase', 'LinkFunction', 'MeasurementType', 'MethodError', 'ModelError', 'ModelType', 'Number', 'OnePropSizeMethod', 'PPSMethod', 'ParamEst', 'PopParam', 'PopSize', 'QuantileMethod', 'RE', 'RandomState', 'RankScoreMethod', 'RepWeights', 'Sample', 'SampleSize', 'Selection', 'Singleton', 'SingletonHandling', 'SingletonInfo', 'SingletonResult', 'SingletonSummary', 'StratumInfo', 'SvyError', 'TTestOneGroup', 'TTestTwoGroups', 'Table', 'TableStats', 'TableType', 'TableUnits', 'Target', 'TargetMean', 'TargetProp', 'TargetTwoMeans', 'TargetTwoProps', 'Threshold', 'TrimConfig', 'TrimResult', 'all_horizontal', 'annotations', 'any_horizontal', 'categorical', 'coalesce', 'col', 'cols', 'concat_str', 'core', 'create_from_csv', 'create_from_dta', 'create_from_parquet', 'create_from_sas', 'create_from_sav', 'create_from_spss', 'create_from_stata', 'datasets', 'enable_debug', 'enable_logging', 'engine', 'errors', 'estimation', 'extensions', 'io', 'lit', 'logging', 'max_horizontal', 'metadata', 'min_horizontal', 'read_csv', 'read_dta', 'read_parquet', 'read_sas', 'read_sav', 'read_spss', 'read_stata', 'register_sample_accessor', 'regression', 'scan_csv', 'scan_parquet', 'seed_from_random_state', 'selection', 'serialize', 'size', 'sum_horizontal', 'temporary_log_level', 'ui', 'utils', 'weighting', 'when', 'wrangling', 'write_csv', 'write_dta', 'write_parquet', 'write_sas', 'write_sav', 'write_spss', 'write_stata']
# 
# --- Top-level class __init__ signatures ---
#   [Design] present (type)
#   SIG Design.__init__(self, row_index: 'str | None' = None, stratum: 'str | Sequence[str] | None' = None, wgt: 'str | None' = None, prob: 'str | None' = None, hit: 'str | None' = None, mos: 'str | None' = None, psu: 'str | Sequence[str] | None' = None, ssu: 'str | Sequence[str] | None' = None, pop_size: 'str | PopSize | None' = None, wr: 'bool' = False, rep_wgts: 'RepWeights | None' = None) -> 'None'
#   DOC Design.__init__: Initialize self.  See help(type(self)) for accurate signature.
#   [Sample] present (type)
#   SIG Sample.__init__(self, data: 'pl.DataFrame', design: 'Design | None' = None, *, catalog: 'LabellingCatalog | None' = None, questionnaire: 'Questionnaire | None' = None) -> 'None'
#   DOC Sample.__init__: Initialize self.  See help(type(self)) for accurate signature.
#   CLASSDOC Sample: A sample class for survey data.
#   [RepWeights] present (StructMeta)
#   SIG RepWeights.__init__(self, /, *args, **kwargs)
#   DOC RepWeights.__init__: Initialize self.  See help(type(self)) for accurate signature.
#   CLASSDOC RepWeights: Strict definition of Replicate Weights.
#   [Cat] present (type)
#   SIG Cat.__init__(self, name: 'str', ref: 'str | int | float | None' = None) -> None
#   DOC Cat.__init__: Initialize self.  See help(type(self)) for accurate signature.
#   CLASSDOC Cat: Explicitly treat a variable as categorical.
#   [Cap] present (type)
#   SIG Cap.__init__(self, stat: 'str', k: 'float' = 1.0) -> None
#   DOC Cap.__init__: Initialize self.  See help(type(self)) for accurate signature.
#   CLASSDOC Cap: Statistical threshold for capping values.
# 
# Synthetic frame: 480 rows x 9 cols
# 
# --- Design construction (signature-driven) ---
#   Design accepts params: ['row_index', 'stratum', 'wgt', 'prob', 'hit', 'mos', 'psu', 'ssu', 'pop_size', 'wr', 'rep_wgts']
#   Constructing svy.Design(**{'stratum': 'stratum', 'wgt': 'weight', 'psu': 'psu'})
#   Design built OK -> Design
#   dir(design) [public]: ['PRINT_WIDTH', 'fill_missing', 'hit', 'method', 'mos', 'pop_size', 'prob', 'psu', 'rep_wgts', 'row_index', 'set_default_print_width', 'show', 'specified_fields', 'ssu', 'stratum', 'update', 'update_rep_weights', 'wgt', 'wr']
# 
# --- fpc acceptance probe (original failure point) ---
#   REJECTED: svy.Design(**{'wgt': 'weight', 'stratum': 'stratum', 'psu': 'psu', 'fpc': 'fpc_pop'}) -> TypeError: Design.__init__() got an unexpected keyword argument 'fpc'
#   REJECTED: svy.Design(**{'weight': 'weight', 'stratum': 'stratum', 'psu': 'psu', 'fpc': 'fpc_pop'}) -> TypeError: Design.__init__() got an unexpected keyword argument 'weight'
# 
# --- Sample construction ---
#   Sample.__init__ params: ['data', 'design', 'catalog', 'questionnaire']
#   Sample built via positional df -> Sample
# 
# --- dir(sample) [public]: ['PRINT_WIDTH', 'categorical', 'clone', 'data', 'deff_w', 'describe', 'design', 'dtypes', 'estimation', 'fpc', 'glm', 'labels', 'meta', 'n_columns', 'n_psus', 'n_records', 'n_strata', 'psus', 'rep_wgts', 'resolve_labels', 'sampling', 'set_categories', 'set_data', 'set_default_print_width', 'set_design', 'set_missing', 'set_na_as_level', 'set_print_width', 'set_type', 'set_value_labels', 'set_var_label', 'set_var_labels', 'show_data', 'singleton', 'ssus', 'strata', 'update_data', 'update_design', 'use_scheme', 'use_weight', 'warn', 'warnings', 'weighting', 'wrangling']
# 
# === sample.estimation ===
#   methods/attrs: ['mean', 'median', 'prop', 'ratio', 'total']
#   SIG estimation.mean(y: 'str | Sequence[str]', *, by: 'str | Sequence[str] | None' = None, where: 'WhereArg' = None, method: "Literal['taylor', 'replication'] | None" = None, deff: 'bool' = False, fay_coef: 'float' = 0.0, as_factor: 'bool' = False, variance_center: "Literal['rep_mean', 'estimate']" = 'rep_mean', alpha: 'float' = 0.05, drop_nulls: 'bool' = False) -> 'Estimate | list[Estimate]'
#   DOC estimation.mean: Estimate population mean with standard errors.
#   SIG estimation.median(y: 'str | Sequence[str]', *, by: 'str | Sequence[str] | None' = None, where: 'WhereArg' = None, method: "Literal['taylor', 'replication'] | None" = None, fay_coef: 'float' = 0.0, q_method: "Literal['higher', 'lower', 'nearest', 'linear', 'middle']" = 'higher', variance_center: "Literal['rep_mean', 'estimate']" = 'rep_mean', alpha: 'float' = 0.05, drop_nulls: 'bool' = False) -> 'Estimate | list[Estimate]'
#   DOC estimation.median: Estimate population median with standard errors.
#   SIG estimation.prop(y: 'str | Sequence[str]', *, by: 'str | Sequence[str] | None' = None, where: 'WhereArg' = None, method: "Literal['taylor', 'replication'] | None" = None, ci_method: "Literal['logit', 'beta', 'korn-graubard', 'wilson']" = 'logit', deff: 'bool' = False, fay_coef: 'float' = 0.0, variance_center: "Literal['rep_mean', 'estimate']" = 'rep_mean', alpha: 'float' = 0.05, drop_nulls: 'bool' = False) -> 'Estimate | list[Estimate]'
#   DOC estimation.prop: Estimate population proportion with standard errors.
#   SIG estimation.ratio(y: 'str | Sequence[str]', x: 'str | Sequence[str]', *, by: 'str | Sequence[str] | None' = None, where: 'WhereArg' = None, method: "Literal['taylor', 'replication'] | None" = None, deff: 'bool' = False, fay_coef: 'float' = 0.0, variance_center: "Literal['rep_mean', 'estimate']" = 'rep_mean', alpha: 'float' = 0.05, drop_nulls: 'bool' = False) -> 'Estimate | list[Estimate]'
#   DOC estimation.ratio: Estimate population ratio (y/x) with standard errors.
#   SIG estimation.total(y: 'str | Sequence[str]', *, by: 'str | Sequence[str] | None' = None, where: 'WhereArg' = None, method: "Literal['taylor', 'replication'] | None" = None, deff: 'bool' = False, fay_coef: 'float' = 0.0, as_factor: 'bool' = False, variance_center: "Literal['rep_mean', 'estimate']" = 'rep_mean', alpha: 'float' = 0.05, drop_nulls: 'bool' = False) -> 'Estimate | list[Estimate]'
#   DOC estimation.total: Estimate population total with standard errors.
# 
# === sample.weighting ===
#   methods/attrs: ['adjust', 'build_aux_matrix', 'calibrate', 'calibrate_matrix', 'control_aux_template', 'controls_margins_template', 'create_brr_wgts', 'create_bs_wgts', 'create_jk_wgts', 'create_sdr_wgts', 'create_variance_strata', 'normalize', 'poststratify', 'rake', 'trim']
#   SIG weighting.adjust(resp_status: 'str', by: 'str | Sequence[str] | None', *, resp_mapping: 'DomainScalarMap | None' = None, wgt_name: 'str' = 'nr_wgt', ignore_reps: 'bool' = False, unknown_to_inelig: 'bool' = True, update_design_wgts: 'bool' = True, respondents_only: 'bool' = True, trimming: 'TrimConfig | None' = None) -> 'Any'
#   SIG weighting.build_aux_matrix(*, x: 'Sequence[Feature]', by: 'str | Sequence[str] | None' = None, by_na: "Literal['error', 'level', 'drop']" = 'error', na_label: 'str' = '__NA__') -> 'tuple[np.ndarray, dict[Category, Number] | dict[Category, dict[Category, Number]]]'
#   SIG weighting.calibrate(*, controls: 'dict[Feature, Any]', by: 'str | Sequence[str] | None' = None, scale: 'Number | list[Number] | np.ndarray' = 1.0, bounded: 'bool' = False, wgt_name: 'str' = 'calib_wgt', update_design_wgts: 'bool' = True, ignore_reps: 'bool' = False, strict: 'bool' = True, trimming: 'TrimConfig | None' = None) -> 'Any'
#   SIG weighting.calibrate_matrix(*, aux_vars: 'np.ndarray', control: 'Any', by: 'str | Sequence[str] | None' = None, scale: 'Number | Sequence[Number] | np.ndarray' = 1.0, wgt_name: 'str' = 'calib_wgt', update_design_wgts: 'bool' = True, labels: 'Sequence[Category] | None' = None, weights_only: 'bool' = False, bounded: 'bool' = False, ignore_reps: 'bool' = False, strict: 'bool' = True, trimming: 'TrimConfig | None' = None) -> 'Any'
#   SIG weighting.control_aux_template(*, x: 'Sequence[Feature]', by: 'str | Sequence[str] | None' = None, by_na: "Literal['error', 'level', 'drop']" = 'error', na_label: 'str' = '__NA__') -> 'dict[Category, Number] | dict[Category, dict[Category, Number]]'
#   SIG weighting.controls_margins_template(*, margins: 'Mapping[str, str]', cat_na: 'str' = 'level', na_label: 'str' = '__NA__') -> 'dict[str, dict[Category, float]]'
#   SIG weighting.create_brr_wgts(n_reps: 'int | None' = None, *, rep_prefix: 'str | None' = None, fay_coef: 'float' = 0.0, rstate: 'int | None' = None, drop_nulls: 'bool' = False) -> 'Any'
#   SIG weighting.create_bs_wgts(n_reps: 'int' = 500, *, rep_prefix: 'str | None' = None, drop_nulls: 'bool' = False, rstate: 'RandomState' = None) -> 'Any'
#   SIG weighting.create_jk_wgts(*, paired: 'bool' = False, rep_prefix: 'str | None' = None, rstate: 'int | None' = None, drop_nulls: 'bool' = False) -> 'Any'
#   SIG weighting.create_sdr_wgts(n_reps: 'int' = 4, *, rep_prefix: 'str | None' = None, order_col: 'str | None' = None, drop_nulls: 'bool' = False) -> 'Any'
#   SIG weighting.create_variance_strata(*, method: "Literal['brr', 'jk2']", order_by: 'str | Sequence[str] | None' = None, shuffle: 'bool' = False, into: 'str' = 'svy_var_stratum', rstate: 'int | None' = None) -> 'Any'
#   SIG weighting.normalize(controls: 'DomainScalarMap | Number | None' = None, *, by: 'str | Sequence[str] | None' = None, wgt_name: 'str' = 'norm_wgt', ignore_reps: 'bool' = False, update_design_wgts: 'bool' = True) -> 'Any'
#   SIG weighting.poststratify(controls: 'DomainScalarMap | Number | None' = None, *, factors: 'DomainScalarMap | Number | None' = None, by: 'str | Sequence[str] | None' = None, wgt_name: 'str' = 'ps_wgt', ignore_reps: 'bool' = False, update_design_wgts: 'bool' = True, strict: 'bool' = True, trimming: 'TrimConfig | None' = None) -> 'Any'
#   SIG weighting.rake(*, controls: 'ControlsType | None' = None, factors: 'ControlsType | None' = None, wgt_name: 'str' = 'rk_wgt', ignore_reps: 'bool' = False, ll_bound: 'float | None' = None, up_bound: 'float | None' = None, tol: 'float' = 0.0001, max_iter: 'int' = 100, display_iter: 'bool' = False, update_design_wgts: 'bool' = True, strict: 'bool' = True, trimming: 'TrimConfig | None' = None) -> 'Sample'
#   SIG weighting.trim(upper=None, lower=None, by=None, redistribute: 'bool' = True, min_cell_size: 'int' = 10, max_iter: 'int' = 10, tol: 'float' = 1e-06, wgt_name: 'str | None' = 'trim_wgt', update_design_wgts: 'bool' = True) -> "'Sample'"
# 
# === sample.glm ===
#   methods/attrs: ['PRINT_WIDTH', 'coefs', 'fit', 'fitted', 'margins', 'predict', 'set_default_print_width', 'set_print_width', 'stats', 'to_polars']
# Traceback (most recent call last):
#   File "/daaf/scripts/scratch/diag_svy_api.py", line 175, in <module>
#     _attr = getattr(_ns, _m, None)
#             ^^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/dist-packages/svy/regression/base.py", line 202, in coefs
#     return self._ensure_fitted().coefs
#            ^^^^^^^^^^^^^^^^^^^^^
#   File "/usr/local/lib/python3.12/dist-packages/svy/regression/base.py", line 137, in _ensure_fitted
#     raise ModelError.not_fitted(where="GLM")
# svy.errors.model_errors.ModelError: 
#   ❌ Model not fitted [MODEL_NOT_FITTED]
#   Cannot call 'predict' because the model has not been fitted yet.
#   - where: GLM
#   Hint: Call .fit() on the estimator first.
# 
#
# --- STDERR ---
# (captured in STDOUT above via 2>&1)
#
# =============================================================================
