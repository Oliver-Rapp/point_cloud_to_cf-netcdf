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

- `-vm` / `--variable_mapping` (str)
  - Path to the variable mapping YAML file. Almost always `config/variable_mapping.yml`.

### Optional Arguments

- `-hdr` / `--hdr_filepath` (str, default: `None`)
  - Path to a HySpex `.hdr` file. When provided, 2D spectral intensity (point × band) is added to the output. Requires a PLY input.

- `-hyspex_cal` / `--need_to_calibrate_hyspex` (`y`/`n`, default: `n`)
  - `y` applies radiometric calibration using the binary HySpex header; `n` writes raw DN values.

- `-mga` / `--met_global_attributes` (str, default: `config/global_attributes.yml`)
  - Path to the MET/ACDD attribute template. You should rarely need to change this.

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
