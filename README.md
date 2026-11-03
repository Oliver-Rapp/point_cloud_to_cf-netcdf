# Point cloud to CF-NetCDF

Python program to convert point cloud data (PLY, LAS, or LAZ) to a CF-NetCDF file.

## Setup

Install the required libraries:

```
pip install -r requirements.txt
```

## Running the program

The program can be run in 2 ways:
1. Convert a single point cloud file
2. Convert multiple point cloud files listed in a CSV file

---

## 1. Convert a single point cloud file

### Minimal examples

```bash
# PLY input
python3 pc_to_netcdf.py \
  -ply /data/scan.ply \
  -uga my_attributes.yml \
  -vm config/variable_mapping.yml

# LAS/LAZ input (streaming, memory-efficient)
python3 pc_to_netcdf.py \
  -las /data/flight.las \
  -uga my_attributes.yml \
  -vm config/variable_mapping.yml

# PLY + HySpex hyperspectral
python3 pc_to_netcdf.py \
  -ply /data/scan.ply \
  -hdr /data/scan.hdr \
  -uga my_attributes.yml \
  -vm config/variable_mapping.yml
```

### Required Arguments

**Input file** (mutually exclusive — exactly one required):

- `-ply` / `--ply_filepath` (str)
  - Path to the input PLY file. Loaded fully into RAM.

- `-las` / `--las_filepath` (str)
  - Path to an input LAS or LAZ file. Processed in **streaming mode** — data is read and written in chunks without loading the full file into RAM.

**Metadata and variable config** (both required):

- `-uga` / `--user_global_attributes` (str)
  - Global attributes for the NetCDF file. Accepts:
    1. A path to a YAML or TOML file with global attributes.
    2. An inline JSON string: `'{"title": "My scan", "summary": "..."}'`
  - See `config/global_attributes.yml` for the expected attribute names and format.
  - The geospatial bounds, `date_created`, `history`, `featureType`, and `Conventions` are computed automatically and do not need to be included.
  - For **LAS/LAZ** inputs, `time_coverage_start` and `time_coverage_end` are also derived automatically from the GPS times in the file. You can still provide them to override the derived values.

- `-vm` / `--variable_mapping` (str)
  - Path to the variable mapping YAML file. Almost always `config/variable_mapping.yml`.

### Optional Arguments

- `-hdr` / `--hdr_filepath` (str, default: `None`)
  - Path to a HySpex `.hdr` file. When provided, 2D spectral intensity (point × band) is added to the output. Requires a PLY input.

- `-hyspex_cal` / `--need_to_calibrate_hyspex` (`y`/`n`, default: `n`)
  - `y` applies radiometric calibration using the binary HySpex header; `n` writes raw DN values.

- `-o` / `--output_filepath` (str, default: `None`)
  - Path to the output NetCDF file. If not specified, the output file is saved to an `output/` folder in the current directory, with the same name as the input file but with a `.nc` extension.

### Coordinate Arguments

> **Note:** Use these arguments only when the X, Y, and Z values in the PLY/LAS file **already represent** latitude, longitude, and altitude, and you need to tell the script which axis is which.

If any of the following are provided, **all three must be given**, and their values must be unique.

- `-x` / `--xcoord` — what `X` represents: `latitude`, `longitude`, or `altitude`
- `-y` / `--ycoord` — what `Y` represents: `latitude`, `longitude`, or `altitude`
- `-z` / `--zcoord` — what `Z` represents: `latitude`, `longitude`, or `altitude`

If these are not provided, the script derives lat/lon from X/Y using the CRS (see below).

### CRS Arguments (mutually exclusive)

- `-crs` / `--crs_config` (str, default: `None`)
  - Path to a YAML file containing CF grid-mapping attributes to write to the `crs` variable. See `config/cf_crs.yml` as a template.

- `-proj4` / `--proj4str` (str, default: `None`)
  - A PROJ.4 string, e.g. `"+proj=utm +zone=33 +datum=WGS84"`.

If neither is provided, the script attempts to read the CRS from the PLY header comment (PLY) or the file's VLRs (LAS/LAZ). If no CRS can be determined, lat/lon will not be computed, and the input must already contain `latitude`/`longitude` columns.

---

## 2. Convert multiple point cloud files

Use this option to process multiple files in a single run. The `convert_multiple_files.py` script reads a CSV file and calls `pc_to_netcdf.py` once per row.

### Example usage

```
python3 convert_multiple_files.py /path/to/jobs.csv
```

### Required Argument

- `csv_filepath` (str)
  - Path to the CSV file. Each row represents one conversion job. See `config/config_bulk_conversion.csv` for a template.

### CSV format

The CSV must have a header row. Columns recognised as script arguments:

| Column | Argument |
|---|---|
| `ply_filepath` | `-ply` |
| `las_filepath` | `-las` |
| `hdr_filepath` | `-hdr` |
| `xcoord` | `-x` |
| `ycoord` | `-y` |
| `zcoord` | `-z` |
| `crs_config` | `-crs` |
| `proj4str` | `-proj4` |
| `variable_mapping` | `-vm` |
| `output_filepath` | `-o` |

All other columns are treated as global attribute key/value pairs and passed inline to `-uga`.

---

## 3. Convert a CF-NetCDF file back to a point cloud

Script: `netcdf_to_pc.py`

Converts a CF-NetCDF file produced by `pc_to_netcdf.py` back to PLY, LAS or LAZ. Points are processed in chunks, so large files do not need to fit in RAM. LAS/LAZ output follows the LAS 1.4 specification.

### Example usage

```bash
# NetCDF -> PLY (default)
python3 netcdf_to_pc.py /path/to/input.nc

# NetCDF -> LAZ, smaller chunks for low-memory machines
python3 netcdf_to_pc.py /path/to/input.nc --format laz --chunk-size 1000000
```

### Arguments

- `input` (str, required)
  - Path to the input NetCDF file.

- `--format` (`ply`, `las` or `laz`, default: `ply`)
  - Output format.

- `--output` (str, default: `None`)
  - Path to the output file. If omitted, the output is written next to the input with the new extension.

- `--config` (str, default: `config/to_pc_config.yaml`)
  - YAML file with the variable mappings, LAS settings and GPS leap seconds.

- `--chunk-size` (int, default: from config, usually `5000000`)
  - Number of points processed per iteration. Lower it if you run out of RAM.

### Technical notes

**Time encoding**
- **PLY:** time is written as Unix epoch seconds.
- **LAS/LAZ:** time is written as Adjusted Standard GPS Time (GPS time minus 1×10⁹), as LAS 1.4 requires. The conversion needs the GPS–UTC leap-second offset, set by `gps_leap_seconds` in `config/to_pc_config.yaml` (18 since 2017-01-01). The script stops with an error if it is missing. With the correct value, LAS → NetCDF → LAS preserves GPS time exactly.

**Georeferencing**
The CRS is taken from the OGC WKT string in the NetCDF `crs` variable, falling back to a PROJ string. It is written into the LAS VLRs.

**Variable mapping**
`config/to_pc_config.yaml` maps NetCDF variable names to output dimensions. Several NetCDF names can map to one output dimension (for example `epoch_time`, `gps_time` and `time` all map to `epoch`); the first one found is used.

### Limitations
- 2D hyperspectral intensity (point × band, from HySpex input) is skipped, so spectral data cannot be recovered yet.
- LAS files that use GPS week time (global encoding bit 0 = 0) are not supported.

### Tests
`tests/compare_round_trip.py` runs forward and reverse conversions on sample PLY and LAS files and compares the results. The latest results are in `tests/test_report.md`.
