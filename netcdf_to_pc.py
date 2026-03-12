import xarray as xr
import numpy as np
import os
import time
import sys
import argparse
import yaml
import laspy
import copy
import pyproj

def load_config(config_path):
    """Loads variables and settings from a YAML file."""
    if not os.path.exists(config_path):
        print(f"Error: Config file {config_path} not found.")
        sys.exit(1)
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    if config is None:
        print(f"Error: Config file '{config_path}' appears to be empty.")
        sys.exit(1)
    return config

def parse_args():
    """Handles command line arguments."""
    parser = argparse.ArgumentParser(description="Convert CF-NetCDF to PLY or LAS point clouds (Chunked).")
    
    parser.add_argument("input", help="Path to input NetCDF file")
    parser.add_argument("--format", choices=['ply', 'las', 'laz'], default='ply', help="Output format (default: ply)")
    parser.add_argument("--output", help="Path to output file. If omitted, defaults to input filename with new extension.")
    parser.add_argument("--config", default="config/to_pc_config.yaml", help="Path to YAML configuration file.")
    parser.add_argument("--chunk-size", type=int, help="Override config chunk size (number of points per iteration)")
    
    return parser.parse_args()

def get_metadata_safely(ds, config, source_filename):
    """
    Extracts CRS and Bounding Box without loading the entire dataset into RAM.
    Prioritizes WKT (standard for LAS 1.4) over PROJ strings.
    """
    crs_string = None
    
    # 1. Try to get WKT from the 'crs' variable (Standard CF-NetCDF)
    if 'crs' in ds and 'crs_wkt' in ds['crs'].attrs:
        crs_string = ds['crs'].attrs['crs_wkt']
    
    # 2. Fallback to global 'datum' attribute (PROJ string)
    if crs_string is None and 'datum' in ds.attrs:
        crs_string = ds.attrs['datum']

    if crs_string is None:
        crs_string = "unknown_crs"

    print("Calculating Bounding Box (Lazy)...")
    
    nc_map = {v: k for k, v in config['mappings'].items()}
    
    bbox = [0.0] * 6
    if 'x' in nc_map and nc_map['x'] in ds:
        bbox[0] = float(ds[nc_map['x']].min())
        bbox[1] = float(ds[nc_map['x']].max())
    if 'y' in nc_map and nc_map['y'] in ds:
        bbox[2] = float(ds[nc_map['y']].min())
        bbox[3] = float(ds[nc_map['y']].max())
    if 'z' in nc_map and nc_map['z'] in ds:
        bbox[4] = float(ds[nc_map['z']].min())
        bbox[5] = float(ds[nc_map['z']].max())
        
    return {
        'crs': crs_string,
        'source': source_filename,
        'processing_time': time.time(),
        'bbox': bbox
    }

def get_chunk(ds, config, start, end):
    """
    Reads a specific slice [start:end] of the NetCDF variables into memory.
    Returns standard UNIX Timestamps for time fields.
    """
    data = {}
    
    for nc_var, out_var in config['mappings'].items():
        if nc_var in ds:
            values = ds[nc_var][start:end].values
            
            # --- TYPE ENFORCEMENT ---
            
            # 1. Time: Convert datetime to Standard Unix Epoch (Seconds since 1970)
            if out_var == 'epoch':
                if np.issubdtype(values.dtype, np.datetime64):
                    # Convert to Unix Seconds (float64)
                    values = values.astype('datetime64[us]').astype('float64') / 1e6
                
                # Keep float64 for time to ensure precision
                values = values.astype('float64')

            # 2. Coordinates: Force Double Precision
            elif out_var in ['x', 'y', 'z']:
                values = values.astype('float64')

            # 3. Standard Integers -> uint32
            elif np.issubdtype(values.dtype, np.integer):
                 values = values.astype('uint32')
            
            # 4. Standard Floats -> float32
            elif np.issubdtype(values.dtype, np.floating):
                 values = values.astype('float32')

            data[out_var] = values
            
    return data

# --- LAS WRITER ---
def process_and_write_las_chunked(ds, config, output_path, total_points, chunk_size, input_filename):
    """
    Opens LAS file for writing, loops through NetCDF in chunks.
    Converts Unix Time to LAS Adjusted Standard GPS Time.
    Injects CRS into LAS Header using pyproj.
    Skips multidimensional intensity (hyperspectral).
    """
    metadata = get_metadata_safely(ds, config, input_filename)
    las_conf = config['las']
    
    # 1. Setup Base Header
    header = laspy.LasHeader(point_format=las_conf['point_format'], version=las_conf['version'])
    header.scales = np.array(las_conf['scales'])
    header.offsets = np.array([metadata['bbox'][0], metadata['bbox'][2], metadata['bbox'][4]])
    
    if las_conf['version'] == "1.4":
        header.global_encoding.gps_time_type = laspy.header.GpsTimeType.STANDARD

    # 2. Add Coordinate Reference System (CRS)
    if metadata['crs'] != "unknown_crs":
        try:
            crs_object = pyproj.CRS.from_string(metadata['crs'])
            header.add_crs(crs_object)
            print("Successfully added CRS to LAS header.")
        except Exception as e:
            print(f"Warning: Could not parse CRS string for LAS header: {e}")

    # 3. Define Extra Bytes
    standard_fields = ['x', 'y', 'z', 'intensity', 'red', 'green', 'blue', 'epoch', 'scan_angle']
    extra_bytes = []
    
    for nc_var, out_var in config['mappings'].items():
        # Note: We can't easily check for multidimensionality here without loading data,
        # so we assume scalar. The loop below handles the actual skipping if multidim.
        if nc_var in ds and out_var not in standard_fields:
            dtype = ds[nc_var].dtype
            extra_bytes.append(laspy.ExtraBytesParams(name=out_var, type=dtype))

    if extra_bytes:
        header.add_extra_dims(extra_bytes)

    # 4. Create Writer Header (Requires Total Count)
    writer_header = copy.copy(header)
    writer_header.point_count = total_points

    print(f"Starting Chunked LAS Write to {output_path} (Chunk Size: {chunk_size})...")
    
    # Flag to ensure we only warn about hyperspectral data once
    hyperspectral_warning_shown = False

    with laspy.open(output_path, mode="w", header=writer_header) as writer:
        
        for start in range(0, total_points, chunk_size):
            end = min(start + chunk_size, total_points)
            print(f"  Processing points {start} to {end} ({(start/total_points)*100:.1f}%)...")
            
            # A. Extract Chunk
            data = get_chunk(ds, config, start, end)
            chunk_count = len(data['x'])
            
            # Check for multidimensional intensity (Hyperspectral)
            if 'intensity' in data and data['intensity'].ndim > 1:
                if not hyperspectral_warning_shown:
                    print(f"Warning: 'intensity' is multidimensional {data['intensity'].shape}. "
                          "Hyperspectral data detected. Skipping intensity field.")
                    hyperspectral_warning_shown = True
                del data['intensity']

            # B. Prepare Container
            header.point_count = chunk_count
            chunk_las = laspy.LasData(header)
            
            chunk_las.x = data['x']
            chunk_las.y = data['y']
            chunk_las.z = data['z']
            
            # Handle Colors (Upscale 8 -> 16 bit)
            if 'red' in data:
                if data['red'].max() <= 255:
                    chunk_las.red = data['red'].astype('uint16') * 256
                    chunk_las.green = data['green'].astype('uint16') * 256
                    chunk_las.blue = data['blue'].astype('uint16') * 256
                else:
                    chunk_las.red = data['red'].astype('uint16')
                    chunk_las.green = data['green'].astype('uint16')
                    chunk_las.blue = data['blue'].astype('uint16')

            # Handle Time: Convert Unix (1970) to Adjusted GPS (1980 - 1e9)
            if 'epoch' in data:
                chunk_las.gps_time = data['epoch'] - 1315964800.0

            if 'intensity' in data:
                chunk_las.intensity = data['intensity'].astype('uint16')

            # Handle Scan Angle (Safety Clip & Scaling for LAS 1.4)
            if 'scan_angle' in data:
                if header.point_format.id >= 6:
                    val = data['scan_angle'] / 0.006
                    val = np.clip(val, -32768, 32767)
                    chunk_las.scan_angle = val.astype('int16')
                else:
                    chunk_las.scan_angle_rank = data['scan_angle'].astype('int8')

            # Handle Extra Bytes
            for key in data.keys():
                if key not in standard_fields:
                    # Double check we aren't trying to write multidim extra bytes
                    if data[key].ndim > 1:
                        continue 
                    setattr(chunk_las, key, data[key])
            
            # C. Write Raw Points
            writer.write_points(chunk_las.points)
            
            del data
            del chunk_las
            
    print("LAS Chunked Write Complete.")

# --- PLY WRITER ---
def process_and_write_ply_chunked(ds, config, output_path, total_points, chunk_size, input_filename):
    """
    Writes a Binary PLY file in chunks.
    Skips multidimensional intensity (hyperspectral).
    """
    metadata = get_metadata_safely(ds, config, input_filename)
    
    print(f"Starting Chunked PLY Write to {output_path} (Chunk Size: {chunk_size})...")

    # 1. Peek at first chunk to determine Types and Order
    peek_data = get_chunk(ds, config, 0, 1)
    
    # Check for multidimensional intensity in peek
    skip_intensity = False
    if 'intensity' in peek_data and peek_data['intensity'].ndim > 1:
        print(f"Warning: 'intensity' is multidimensional {peek_data['intensity'].shape}. "
              "Hyperspectral data detected. Skipping intensity field in PLY.")
        del peek_data['intensity']
        skip_intensity = True

    # Priority order matching legacy requirements
    priority_order = ['x', 'y', 'z', 'nx', 'ny', 'nz', 'red', 'green', 'blue']
    sorted_keys = sorted(peek_data.keys(), key=lambda k: priority_order.index(k) if k in priority_order else 99)

    # 2. Build Dtype List (Little Endian)
    dtype_list = []
    header_props = []

    for key in sorted_keys:
        # Double check if any other keys are multidimensional and skip them
        if peek_data[key].ndim > 1:
            print(f"Warning: Variable '{key}' is multidimensional. Skipping in PLY.")
            continue

        if key in ['red', 'green', 'blue']:
            # Force color to uint8 (uchar)
            dtype_list.append((key, 'uint8'))
            header_props.append(f"property uchar {key}")
        else:
            # Derive type from data (already forced in get_chunk)
            dt = peek_data[key].dtype
            dt_le = dt.newbyteorder('<')
            dtype_list.append((key, dt_le))
            
            # Map numpy types to PLY names
            if "float64" in dt.name: ply_type = "double"
            elif "float32" in dt.name: ply_type = "float"
            elif "uint32" in dt.name: ply_type = "uint"
            elif "int32" in dt.name: ply_type = "int"
            elif "uint16" in dt.name: ply_type = "ushort"
            elif "int16" in dt.name: ply_type = "short"
            elif "uint8" in dt.name: ply_type = "uchar"
            else: ply_type = "float" # Fallback
            
            header_props.append(f"property {ply_type} {key}")

    # 3. Write Header
    with open(output_path, 'wb') as f:
        f.write(b"ply\n")
        f.write(b"format binary_little_endian 1.0\n")
        f.write(f"element vertex {total_points}\n".encode('utf-8'))
        
        # Write Properties
        for prop in header_props:
            f.write(f"{prop}\n".encode('utf-8'))
            
        # Write Comment
        comment_str = (
            f"comment processing_time_epoch={metadata['processing_time']:.6f}; "
            f"utm_crs={metadata['crs']}; "
            f"source_file={metadata['source']}; "
            f"BBox = [{metadata['bbox'][0]:.4f}, {metadata['bbox'][1]:.4f}, "
            f"{metadata['bbox'][2]:.4f}, {metadata['bbox'][3]:.4f}]\n"
        )
        f.write(comment_str.encode('utf-8'))
        
        f.write(b"end_header\n")

        # 4. Stream Chunks
        for start in range(0, total_points, chunk_size):
            end = min(start + chunk_size, total_points)
            print(f"  Processing points {start} to {end} ({(start/total_points)*100:.1f}%)...")
            
            data = get_chunk(ds, config, start, end)
            chunk_count = len(data['x'])
            
            # Filter hyperspectral intensity if flag is set
            if skip_intensity and 'intensity' in data:
                del data['intensity']

            # Create structured array
            chunk_struct = np.zeros(chunk_count, dtype=dtype_list)
            
            for key in sorted_keys:
                # Ensure key exists (it might have been skipped if multidim)
                if key not in data: continue
                # Skip if current chunk data is unexpectedly multidim
                if data[key].ndim > 1: continue

                val = data[key]
                
                # Downscale colors for PLY
                if key in ['red', 'green', 'blue']:
                    if val.max() > 255:
                        chunk_struct[key] = (val / 65535.0 * 255).astype('uint8')
                    else:
                        chunk_struct[key] = val.astype('uint8')
                else:
                    chunk_struct[key] = val
                
                del data[key]
            
            # Write binary block
            f.write(chunk_struct.tobytes())
            del chunk_struct

    print("PLY Chunked Write Complete.")

def main():
    args = parse_args()
    config = load_config(args.config)
    
    if args.output:
        out_path = args.output
    else:
        base = os.path.splitext(args.input)[0]
        ext = 'laz' if args.format == 'laz' else args.format
        out_path = f"{base}.{ext}"

    print(f"Opening {args.input}...")
    # Use empty chunks to enable Dask/Lazy loading for metadata calculation
    ds = xr.open_dataset(args.input, chunks={})
    count = ds.sizes['point']
    print(f"Total points: {count}")
    
    # Extract filename for metadata
    input_filename = os.path.basename(args.input)

    # --- DETERMINE CHUNK SIZE ---
    # Priority: 1. CLI Argument, 2. Config File, 3. Safety Default (5M)
    final_chunk_size = config.get('processing', {}).get('chunk_size', 5_000_000)
    
    if args.chunk_size:
        final_chunk_size = args.chunk_size
        print(f"Using chunk size: {final_chunk_size} (CLI Override)")
    else:
        print(f"Using chunk size: {final_chunk_size}")

    # Execute Writer
    if args.format in ['las', 'laz']:
        process_and_write_las_chunked(ds, config, out_path, count, final_chunk_size, input_filename)
    elif args.format == 'ply':
        process_and_write_ply_chunked(ds, config, out_path, count, final_chunk_size, input_filename)
    
    ds.close()

if __name__ == "__main__":
    main()