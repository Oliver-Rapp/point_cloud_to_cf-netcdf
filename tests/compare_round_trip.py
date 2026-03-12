"""
Round-trip comparison script.

Runs all forward + reverse conversions and numerically compares each output
against its input. Produces a human-readable Markdown test report at
tests/test_report.md.

Usage:
    python tests/compare_round_trip.py

Paths are relative to the repo root; run from there with .venv active.
"""

import os
import sys
import subprocess
import numpy as np
import laspy
import netCDF4 as nc
from datetime import datetime, timezone
from plyfile import PlyData

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = "/home/oliver/Documents/MET/Test_Point_Clouds"
OUT_DIR    = os.path.join(REPO_ROOT, "output", "test_round_trip")
REPORT_OUT = os.path.join(REPO_ROOT, "tests", "test_report.md")

LAS_SRC  = f"{DATA_DIR}/DJI_sample_100k.las"
PLY_SRC  = f"{DATA_DIR}/VNIR_sample_100k.ply"
ATTRS_LAS = os.path.join(REPO_ROOT, "tests", "test_attrs_las.yml")
ATTRS_PLY = os.path.join(REPO_ROOT, "tests", "test_attrs_ply.yml")
VM        = os.path.join(REPO_ROOT, "config", "variable_mapping.yml")
CRS_YAML  = os.path.join(REPO_ROOT, "config", "cf_crs.yml")
PROJ4_33N = "+proj=utm +zone=33 +north +ellps=WGS84 +datum=WGS84 +units=m +no_defs"

os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
all_results = {}   # {test_id: {check_name: (pass, detail)}}
all_errors  = {}   # {test_id: error_string}  — for failed conversions


def record(test_id, check, passed, detail=""):
    all_results.setdefault(test_id, {})[check] = (passed, detail)


def run_cmd(cmd, test_id):
    """Run a shell command; return True on success."""
    print(f"\n[{test_id}] $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if result.returncode != 0:
        all_errors[test_id] = result.stderr[-2000:] or result.stdout[-2000:]
        print(f"  FAILED (exit {result.returncode})")
        print(result.stderr[-500:])
        return False
    print("  OK")
    return True


def netcdf_path(name):
    return os.path.join(OUT_DIR, f"{name}.nc")


def out_path(name, ext):
    return os.path.join(OUT_DIR, f"{name}.{ext}")


# ---------------------------------------------------------------------------
# Forward conversions
# ---------------------------------------------------------------------------
def forward_conversions():
    py = sys.executable
    ok = {}

    # T1: LAS → NC, CRS from VLRs
    ok['T1'] = run_cmd([
        py, "pc_to_netcdf.py",
        "-las", LAS_SRC, "-uga", ATTRS_LAS, "-vm", VM,
        "-o", netcdf_path("T1_las_crs_from_vlr"),
    ], "T1")

    # T2: LAS → NC, CRS from explicit YAML
    ok['T2'] = run_cmd([
        py, "pc_to_netcdf.py",
        "-las", LAS_SRC, "-uga", ATTRS_LAS, "-vm", VM,
        "-crs", CRS_YAML,
        "-o", netcdf_path("T2_las_crs_from_yaml"),
    ], "T2")

    # T3: LAS → NC, CRS from proj4 string
    ok['T3'] = run_cmd([
        py, "pc_to_netcdf.py",
        "-las", LAS_SRC, "-uga", ATTRS_LAS, "-vm", VM,
        "-proj4", PROJ4_33N,
        "-o", netcdf_path("T3_las_crs_from_proj4"),
    ], "T3")

    # T4: PLY → NC, CRS from header comment
    ok['T4'] = run_cmd([
        py, "pc_to_netcdf.py",
        "-ply", PLY_SRC, "-uga", ATTRS_PLY, "-vm", VM,
        "-o", netcdf_path("T4_ply_crs_from_comment"),
    ], "T4")

    # T5: PLY → NC, CRS from explicit YAML
    ok['T5'] = run_cmd([
        py, "pc_to_netcdf.py",
        "-ply", PLY_SRC, "-uga", ATTRS_PLY, "-vm", VM,
        "-crs", CRS_YAML,
        "-o", netcdf_path("T5_ply_crs_from_yaml"),
    ], "T5")

    return ok


# ---------------------------------------------------------------------------
# Reverse conversions
# ---------------------------------------------------------------------------
def reverse_conversions(fwd_ok):
    py = sys.executable
    ok = {}

    # T6: NC → LAS (round-trip of T1)
    if fwd_ok.get('T1'):
        ok['T6'] = run_cmd([
            py, "netcdf_to_pc.py",
            netcdf_path("T1_las_crs_from_vlr"),
            "--format", "las",
            "--output", out_path("T6_las_roundtrip", "las"),
        ], "T6")

    # T7: NC → PLY (cross-format: LAS source → PLY output)
    if fwd_ok.get('T1'):
        ok['T7'] = run_cmd([
            py, "netcdf_to_pc.py",
            netcdf_path("T1_las_crs_from_vlr"),
            "--format", "ply",
            "--output", out_path("T7_las_to_ply", "ply"),
        ], "T7")

    # T8: NC → PLY (round-trip of T4)
    if fwd_ok.get('T4'):
        ok['T8'] = run_cmd([
            py, "netcdf_to_pc.py",
            netcdf_path("T4_ply_crs_from_comment"),
            "--format", "ply",
            "--output", out_path("T8_ply_roundtrip", "ply"),
        ], "T8")

    # T9: NC → LAS (cross-format: PLY source → LAS output)
    if fwd_ok.get('T4'):
        ok['T9'] = run_cmd([
            py, "netcdf_to_pc.py",
            netcdf_path("T4_ply_crs_from_comment"),
            "--format", "las",
            "--output", out_path("T9_ply_to_las", "las"),
        ], "T9")

    return ok


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_netcdf_intermediate(test_id, nc_path, expected_vars, lat_range, lon_range):
    """Check a NetCDF intermediate file."""
    if not os.path.exists(nc_path):
        record(test_id, "NetCDF exists", False, "file not found")
        return

    record(test_id, "NetCDF exists", True)

    with nc.Dataset(nc_path) as ds:
        # Required variables
        for var in expected_vars:
            present = var in ds.variables
            record(test_id, f"var:{var} present", present,
                   "" if present else f"{var} missing from {list(ds.variables.keys())}")

        # CRS variable
        crs_present = 'crs' in ds.variables
        record(test_id, "crs variable present", crs_present)
        if crs_present:
            gm = ds['crs'].getncattr('grid_mapping_name') if 'grid_mapping_name' in ds['crs'].ncattrs() else None
            record(test_id, "crs:grid_mapping_name set", gm is not None, str(gm))

        # Lat/lon range
        if 'latitude' in ds.variables and 'longitude' in ds.variables:
            lat = ds['latitude'][:]
            lon = ds['longitude'][:]
            lat_ok = bool(np.all(np.isfinite(lat)) and lat_range[0] <= lat.min() and lat.max() <= lat_range[1])
            lon_ok = bool(np.all(np.isfinite(lon)) and lon_range[0] <= lon.min() and lon.max() <= lon_range[1])
            record(test_id, "lat range valid", lat_ok,
                   f"min={float(lat.min()):.4f} max={float(lat.max()):.4f} expected [{lat_range[0]},{lat_range[1]}]")
            record(test_id, "lon range valid", lon_ok,
                   f"min={float(lon.min()):.4f} max={float(lon.max()):.4f} expected [{lon_range[0]},{lon_range[1]}]")

        # Required global attributes
        required_ga = ['title', 'Conventions', 'featureType', 'geospatial_lat_min']
        for ga in required_ga:
            present = ga in ds.ncattrs()
            record(test_id, f"attr:{ga}", present)

        conventions = ds.getncattr('Conventions') if 'Conventions' in ds.ncattrs() else ''
        record(test_id, "Conventions=CF-1.8,ACDD-1.3", 'CF-1.8' in conventions and 'ACDD-1.3' in conventions,
               conventions)


def check_las_roundtrip(test_id, src_las, rt_las):
    """Numerically compare a round-tripped LAS against the original."""
    if not os.path.exists(rt_las):
        record(test_id, "output exists", False, "file not found")
        return
    record(test_id, "output exists", True)

    orig = laspy.read(src_las)
    rt   = laspy.read(rt_las)

    # Point count
    n_orig = len(orig.points)
    n_rt   = len(rt.points)
    record(test_id, "point count", n_orig == n_rt, f"{n_rt} (expected {n_orig})")

    # X, Y, Z — tolerance is the coarser of orig/rt scales (netcdf_to_pc uses fixed 0.001 m scale)
    orig_scale = float(orig.header.scales[0])
    rt_scale   = float(rt.header.scales[0])
    tol = max(orig_scale, rt_scale) * 2
    for ax in ('x', 'y', 'z'):
        o = np.array(getattr(orig, ax))
        r = np.array(getattr(rt, ax))
        if len(r) != len(o):
            record(test_id, f"{ax} accuracy", False, "point count mismatch, skipping")
            continue
        err = np.max(np.abs(o - r))
        passed = err <= tol
        record(test_id, f"{ax} accuracy", passed,
               f"max_err={err:.6f} m (orig_scale={orig_scale} m, rt_scale={rt_scale} m)")

    if len(orig.points) != len(rt.points):
        return

    # RGB colors — should round-trip exactly (0-255 → ×256 → ÷256 back to 0-255)
    for ch in ('red', 'green', 'blue'):
        try:
            o = np.array(getattr(orig, ch))
            r = np.array(getattr(rt, ch))
            # orig is uint16 (0-65535), rt is also uint16
            # Check they match (may be scaled ×256 if orig was 8-bit)
            if o.max() <= 255:
                # orig was 8-bit stored as uint16, rt should be ×256
                expected = o.astype('uint16') * 256
            else:
                expected = o
            match = np.array_equal(expected, r)
            record(test_id, f"{ch} round-trip", match,
                   f"max_diff={int(np.max(np.abs(expected.astype(int) - r.astype(int))))}")
        except Exception as e:
            record(test_id, f"{ch} round-trip", False, str(e))

    # GPS time — compare against original adjusted GPS time
    # Expected: rt_gps ≈ orig_gps  (should be within a few seconds due to leap second handling)
    try:
        o_gps = np.array(orig.gps_time)
        r_gps = np.array(rt.gps_time)
        err = np.max(np.abs(o_gps - r_gps))
        passed = err < 30  # within 30 s (18 s leap second offset is expected)
        record(test_id, "gps_time round-trip", passed, f"max_err={err:.3f} s")
    except Exception as e:
        record(test_id, "gps_time round-trip", False, str(e))

    # Scan angle — compare in degrees (LAS 1.4 uses 0.006° units, LAS 1.3 uses 1° units)
    try:
        o_sa = np.array(orig.scan_angle_rank).astype(np.float64)  # degrees, int8
        rt_fmt = rt.header.point_format.id
        if rt_fmt >= 6:
            r_sa = np.array(rt.scan_angle).astype(np.float64) * 0.006  # 0.006°/unit → degrees
        else:
            r_sa = np.array(rt.scan_angle_rank).astype(np.float64)
        err = float(np.max(np.abs(o_sa - r_sa)))
        # LAS 1.4 format quantizes at 0.006°; allow 1 step of precision
        record(test_id, "scan_angle round-trip", err <= 0.01, f"max_err={err:.4f} deg")
    except Exception as e:
        record(test_id, "scan_angle round-trip", False, str(e))

    # CRS in output LAS header
    try:
        with laspy.open(rt_las) as f:
            crs = f.header.parse_crs()
        record(test_id, "CRS in output LAS", crs is not None, str(crs.to_epsg()) if crs else "None")
    except Exception as e:
        record(test_id, "CRS in output LAS", False, str(e))


def check_ply_roundtrip(test_id, src_ply_path, rt_ply_path, is_cross_format=False):
    """Numerically compare a round-tripped PLY against the original."""
    if not os.path.exists(rt_ply_path):
        record(test_id, "output exists", False, "file not found")
        return
    record(test_id, "output exists", True)

    orig = PlyData.read(src_ply_path)['vertex']
    rt   = PlyData.read(rt_ply_path)['vertex']

    n_orig = len(orig)
    n_rt   = len(rt)
    record(test_id, "point count", n_orig == n_rt, f"{n_rt} (expected {n_orig})")

    if n_orig != n_rt:
        return

    # X, Y, Z
    for ax in ('x', 'y', 'z'):
        try:
            o = np.array(orig[ax], dtype=np.float64)
            r = np.array(rt[ax], dtype=np.float64)
            err = float(np.max(np.abs(o - r)))
            tol = 0.01  # 1 cm — PLY uses float32/float64, tolerate float32 rounding
            passed = err <= tol
            record(test_id, f"{ax} accuracy", passed, f"max_err={err:.8f} m (tol={tol} m)")
        except Exception as e:
            record(test_id, f"{ax} accuracy", False, str(e))

    if is_cross_format:
        return  # Skip property-level checks for cross-format tests

    # RGB — should be exact uint8 round-trip for PLY→NC→PLY
    for ch in ('red', 'green', 'blue'):
        try:
            o = np.array(orig[ch], dtype=np.int32)
            r = np.array(rt[ch], dtype=np.int32)
            match = np.array_equal(o, r)
            record(test_id, f"{ch} round-trip", match,
                   f"max_diff={int(np.max(np.abs(o - r)))}")
        except Exception as e:
            record(test_id, f"{ch} round-trip", False, str(e))

    # Normal vectors — float32 round-trip, check unit length
    for ax in ('nx', 'ny', 'nz'):
        try:
            o = np.array(orig[ax], dtype=np.float32)
            r = np.array(rt[ax], dtype=np.float32)
            err = float(np.max(np.abs(o.astype(np.float64) - r.astype(np.float64))))
            record(test_id, f"{ax} accuracy", err < 1e-5, f"max_err={err:.2e}")
        except Exception as e:
            record(test_id, f"{ax} accuracy", False, str(e))

    try:
        nx = np.array(rt['nx'], dtype=np.float64)
        ny = np.array(rt['ny'], dtype=np.float64)
        nz = np.array(rt['nz'], dtype=np.float64)
        lengths = np.sqrt(nx**2 + ny**2 + nz**2)
        unit_ok = bool(np.all(np.abs(lengths - 1.0) < 0.01))
        record(test_id, "normal vectors unit length", unit_ok,
               f"mean_len={float(lengths.mean()):.4f} max_dev={float(np.max(np.abs(lengths-1))):.4f}")
    except Exception as e:
        record(test_id, "normal vectors unit length", False, str(e))

    # View vectors (vx, vy, vz)
    for ax in ('vx', 'vy', 'vz'):
        try:
            o = np.array(orig[ax], dtype=np.float32)
            r = np.array(rt[ax], dtype=np.float32)
            err = float(np.max(np.abs(o.astype(np.float64) - r.astype(np.float64))))
            record(test_id, f"{ax} accuracy", err < 1e-5, f"max_err={err:.2e}")
        except Exception as e:
            record(test_id, f"{ax} accuracy", False, str(e))

    # Pixel coordinates — should round-trip exactly
    for ax in ('px', 'py'):
        try:
            o = np.array(orig[ax])
            r = np.array(rt[ax])
            match = np.array_equal(o, r)
            record(test_id, f"{ax} round-trip", match,
                   f"max_diff={int(np.max(np.abs(o.astype(int) - r.astype(int))))}")
        except Exception as e:
            record(test_id, f"{ax} round-trip", False, str(e))

    # Epoch time — float32 limited precision (~7 sig figures)
    try:
        o = np.array(orig['epoch'], dtype=np.float64)
        r = np.array(rt['epoch'], dtype=np.float64)
        err = float(np.max(np.abs(o - r)))
        record(test_id, "epoch time round-trip", err < 0.1, f"max_err={err:.6f} s")
    except Exception as e:
        record(test_id, "epoch time round-trip", False, str(e))

    # CRS comment in output PLY
    try:
        with open(rt_ply_path, 'rb') as f:
            for line in f:
                l = line.decode('utf-8', errors='replace').strip()
                if l.startswith('comment') and 'utm_crs' in l:
                    record(test_id, "utm_crs comment in PLY", True, l[8:60] + "...")
                    break
                if l == 'end_header':
                    record(test_id, "utm_crs comment in PLY", False, "comment not found")
                    break
    except Exception as e:
        record(test_id, "utm_crs comment in PLY", False, str(e))


def _check_t7_xyz():
    """T7 is LAS→NC→PLY (cross-format). Compare X/Y/Z of output PLY vs LAS source."""
    test_id = 'T7'
    ply_path = out_path("T7_las_to_ply", "ply")
    if not os.path.exists(ply_path):
        record(test_id, "output exists", False, "file not found")
        return
    record(test_id, "output exists", True)

    orig_las = laspy.read(LAS_SRC)
    rt_ply   = PlyData.read(ply_path)['vertex']

    n_orig = len(orig_las.points)
    n_rt   = len(rt_ply)
    record(test_id, "point count", n_orig == n_rt, f"{n_rt} (expected {n_orig})")

    if n_orig != n_rt:
        return

    for ax_las, ax_ply in (('x', 'x'), ('y', 'y'), ('z', 'z')):
        try:
            o = np.array(getattr(orig_las, ax_las), dtype=np.float64)
            r = np.array(rt_ply[ax_ply], dtype=np.float64)
            err = float(np.max(np.abs(o - r)))
            tol = 0.01
            record(test_id, f"{ax_las} accuracy (LAS→PLY)", err <= tol,
                   f"max_err={err:.6f} m (tol={tol} m)")
        except Exception as e:
            record(test_id, f"{ax_las} accuracy (LAS→PLY)", False, str(e))

    # CRS comment in output PLY
    try:
        with open(ply_path, 'rb') as f:
            for line in f:
                l = line.decode('utf-8', errors='replace').strip()
                if l.startswith('comment') and 'utm_crs' in l:
                    record(test_id, "utm_crs comment in PLY", True, l[8:60] + "...")
                    break
                if l == 'end_header':
                    record(test_id, "utm_crs comment in PLY", False, "comment not found")
                    break
    except Exception as e:
        record(test_id, "utm_crs comment in PLY", False, str(e))


def _check_t9_xyz():
    """T9 is PLY→NC→LAS (cross-format). Compare X/Y/Z of output LAS vs PLY source."""
    test_id = 'T9'
    las_path = out_path("T9_ply_to_las", "las")
    if not os.path.exists(las_path):
        record(test_id, "output exists", False, "file not found")
        return
    record(test_id, "output exists", True)

    orig_ply = PlyData.read(PLY_SRC)['vertex']
    rt_las   = laspy.read(las_path)

    n_orig = len(orig_ply)
    n_rt   = len(rt_las.points)
    record(test_id, "point count", n_orig == n_rt, f"{n_rt} (expected {n_orig})")

    if n_orig != n_rt:
        return

    for ax_ply, ax_las in (('x', 'x'), ('y', 'y'), ('z', 'z')):
        try:
            o = np.array(orig_ply[ax_ply], dtype=np.float64)
            r = np.array(getattr(rt_las, ax_las), dtype=np.float64)
            err = float(np.max(np.abs(o - r)))
            tol = 0.01
            record(test_id, f"{ax_ply} accuracy (PLY→LAS)", err <= tol,
                   f"max_err={err:.6f} m (tol={tol} m)")
        except Exception as e:
            record(test_id, f"{ax_ply} accuracy (PLY→LAS)", False, str(e))

    try:
        with laspy.open(las_path) as f:
            crs = f.header.parse_crs()
        record(test_id, "CRS in output LAS", crs is not None,
               str(crs.to_epsg()) if crs else "None")
    except Exception as e:
        record(test_id, "CRS in output LAS", False, str(e))


def check_crs_method_consistency():
    """Compare lat/lon from T1 (VLR), T2 (YAML), T3 (proj4) — all should be identical."""
    test_id = "CRS_CONSISTENCY"
    paths = {
        'T1_VLR':   netcdf_path("T1_las_crs_from_vlr"),
        'T2_YAML':  netcdf_path("T2_las_crs_from_yaml"),
        'T3_proj4': netcdf_path("T3_las_crs_from_proj4"),
    }

    lats = {}
    for name, p in paths.items():
        if not os.path.exists(p):
            record(test_id, f"{name} exists", False, "file not found")
            continue
        with nc.Dataset(p) as ds:
            if 'latitude' in ds.variables:
                lats[name] = np.array(ds['latitude'][:])

    if len(lats) < 2:
        record(test_id, "CRS methods comparable", False, "not enough files to compare")
        return

    names = list(lats.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            a, b = names[i], names[j]
            err = float(np.max(np.abs(lats[a] - lats[b])))
            passed = err < 1e-7
            record(test_id, f"lat: {a} vs {b}", passed, f"max_diff={err:.2e} deg")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def generate_report(fwd_ok, rev_ok):
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = [
        "# Round-trip test report",
        "",
        f"**Date:** {now}  ",
        f"**Branch:** integration/round-trip-test  ",
        "",
        "---",
        "",
        "## Test data",
        "",
        f"| File | Points | Format |",
        f"|---|---|---|",
        f"| `DJI_sample_100k.las` | 100,000 | LAS 1.4, DJI Zenmuse L1, UTM 33N, has RGB + GPS time |",
        f"| `VNIR_sample_100k.ply` | 100,000 | PLY binary_little_endian, HySpex VNIR 1800, UTM 33N, has normals/view vectors/pixel coords/epoch |",
        "",
        "---",
        "",
        "## Results summary",
        "",
        "| Test | Description | Conversion | Status |",
        "|---|---|---|---|",
    ]

    descriptions = {
        'T1': "LAS → NC (CRS from VLRs)",
        'T2': "LAS → NC (CRS from YAML)",
        'T3': "LAS → NC (CRS from proj4)",
        'T4': "PLY → NC (CRS from header comment)",
        'T5': "PLY → NC (CRS from YAML)",
        'T6': "NC → LAS round-trip (T1 source)",
        'T7': "NC → PLY cross-format (LAS → PLY)",
        'T8': "NC → PLY round-trip (T4 source)",
        'T9': "NC → LAS cross-format (PLY → LAS)",
        'CRS_CONSISTENCY': "CRS method consistency (T1 vs T2 vs T3)",
    }

    all_test_ids = ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8', 'T9', 'CRS_CONSISTENCY']

    for tid in all_test_ids:
        desc = descriptions.get(tid, tid)
        direction = "forward" if tid in ('T1','T2','T3','T4','T5') else "reverse" if tid.startswith('T') else "check"

        if tid in all_errors:
            status = "❌ CONVERSION FAILED"
        elif tid not in all_results:
            status = "⚠️ NOT RUN"
        else:
            checks = all_results[tid]
            n_fail = sum(1 for v, _ in checks.values() if not v)
            status = "✅ PASS" if n_fail == 0 else f"❌ FAIL ({n_fail} checks failed)"
        lines.append(f"| {tid} | {desc} | {direction} | {status} |")

    lines += ["", "---", "", "## Detailed checks", ""]

    for tid in all_test_ids:
        if tid not in all_results and tid not in all_errors:
            continue
        lines.append(f"### {tid}: {descriptions.get(tid, tid)}")
        lines.append("")
        if tid in all_errors:
            lines.append(f"**Conversion failed:**")
            lines.append("```")
            lines.append(all_errors[tid][:1000])
            lines.append("```")
            lines.append("")
            continue
        lines.append("| Check | Result | Detail |")
        lines.append("|---|---|---|")
        for check, (passed, detail) in all_results[tid].items():
            icon = "✅" if passed else "❌"
            lines.append(f"| {check} | {icon} | {detail} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Known limitations",
        "",
        "| Limitation | Impact |",
        "|---|---|",
        "| Only UTM zone 33N data | Cannot test CRS reprojection for other zones/datums |",
        "| Only 2 sensor types (DJI L1 + HySpex VNIR) | No variety in LAS point formats or GPS time encoding |",
        "| No GPS Week Time file | Cannot test GPS Week Time rejection error |",
        "| No PLY with pre-existing lat/lon columns | Cannot test that code path (known NameError bug) |",
        "| HySpex hyperspectral intensity | 2D intensity not recoverable by design; tested that other variables are unaffected |",
        "| No bad/malformed inputs | No negative testing |",
        "| GPS time off by ~18 s (leap seconds) | Known limitation: forward conversion corrects for leap seconds, reverse does not |",
        "",
    ]

    with open(REPORT_OUT, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"\nReport written to {REPORT_OUT}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Round-trip test suite")
    print("=" * 60)

    # 1. Forward conversions
    print("\n--- Forward conversions ---")
    fwd_ok = forward_conversions()

    # 2. Check NetCDF intermediates
    print("\n--- Checking NetCDF intermediates ---")
    las_expected_vars = ['X', 'Y', 'Z', 'latitude', 'longitude', 'altitude',
                         'red', 'green', 'blue', 'epoch_time', 'scan_angle_rank']
    ply_expected_vars = ['X', 'Y', 'Z', 'latitude', 'longitude',
                         'red', 'green', 'blue', 'nx', 'ny', 'nz', 'vx', 'vy', 'vz', 'px', 'py']

    svalbard_lat = (76.0, 82.0)
    svalbard_lon = (13.0, 22.0)

    for tid in ('T1', 'T2', 'T3'):
        nc_file = netcdf_path(f"T{tid[1:]}_las_crs_from_{'vlr' if tid=='T1' else 'yaml' if tid=='T2' else 'proj4'}")
        if fwd_ok.get(tid):
            check_netcdf_intermediate(
                tid, nc_file, las_expected_vars, svalbard_lat, svalbard_lon
            )
    for tid in ('T4', 'T5'):
        suffix = 'crs_from_comment' if tid == 'T4' else 'crs_from_yaml'
        nc_file = netcdf_path(f"{tid}_ply_{suffix}")
        if fwd_ok.get(tid):
            check_netcdf_intermediate(
                tid, nc_file, ply_expected_vars, svalbard_lat, svalbard_lon
            )

    # 3. CRS consistency
    print("\n--- CRS method consistency ---")
    check_crs_method_consistency()

    # 4. Reverse conversions
    print("\n--- Reverse conversions ---")
    rev_ok = reverse_conversions(fwd_ok)

    # 5. Numerical comparisons
    print("\n--- Numerical comparisons ---")

    if rev_ok.get('T6'):
        check_las_roundtrip('T6', LAS_SRC, out_path("T6_las_roundtrip", "las"))

    if rev_ok.get('T7'):
        # T7 is LAS → NC → PLY (cross-format): compare X/Y/Z of PLY output vs LAS source
        _check_t7_xyz()

    if rev_ok.get('T8'):
        check_ply_roundtrip('T8', PLY_SRC, out_path("T8_ply_roundtrip", "ply"))

    if rev_ok.get('T9'):
        # T9 is PLY → NC → LAS: compare X/Y/Z of LAS output against PLY source
        _check_t9_xyz()

    # 6. Generate report
    generate_report(fwd_ok, rev_ok)

    # Print summary
    total_checks = sum(len(v) for v in all_results.values())
    total_fail   = sum(1 for v in all_results.values() for p, _ in v.values() if not p)
    total_conv_fail = len(all_errors)
    print(f"\n{'='*60}")
    print(f"Summary: {total_checks} checks, {total_fail} failed | {total_conv_fail} conversions failed")
    print(f"Report: {REPORT_OUT}")
