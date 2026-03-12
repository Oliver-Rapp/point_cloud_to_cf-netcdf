import os
import laspy
from lib.read_data import read_hyspex_stream, ply_to_df, las_to_df, get_cf_crs, list_variables_in_ply, list_variables_in_las
from lib.create_netcdf import create_netcdf
from lib.global_attributes import GlobalAttributes
from lib.variable_mapping import VariableMapping
from lib.read_data import get_las_metadata, read_las_generator, compute_gps_time_reference
from lib.create_netcdf import create_netcdf_stream
from datetime import datetime, timezone 
import argparse
import yaml
import toml
import json
import sys
import logging
import copy

logger = logging.getLogger(__name__)

def generate_py_ranges(min_py, max_py, chunk_size=5000, penultimate_size=3000, min_remainder=1000):
    total_lines = max_py - min_py + 1
    num_full_chunks = total_lines // chunk_size
    remainder = total_lines % chunk_size

    ranges = []

    # Case 1: remainder is 0 or large enough, just do full chunks + remainder chunk
    if remainder == 0 or remainder >= min_remainder:
        for i in range(num_full_chunks):
            start = min_py + i * chunk_size
            end = start + chunk_size - 1
            ranges.append((start, end))
        # Add remainder chunk if any
        if remainder > 0:
            start = min_py + num_full_chunks * chunk_size
            end = max_py
            ranges.append((start, end))
    else:
        # Case 2: remainder < min_remainder
        # Adjust penultimate chunk to penultimate_size
        if num_full_chunks == 0:
            # Not enough lines for even one full chunk, just one range
            ranges.append((min_py, max_py))
        else:
            # Full chunks except last two
            for i in range(num_full_chunks - 1):
                start = min_py + i * chunk_size
                end = start + chunk_size - 1
                ranges.append((start, end))
            # Penultimate chunk with penultimate_size lines
            penultimate_start = min_py + (num_full_chunks - 1) * chunk_size
            penultimate_end = penultimate_start + penultimate_size - 1
            ranges.append((penultimate_start, penultimate_end))
            # Final chunk is the remainder + (chunk_size - penultimate_size)
            final_start = penultimate_end + 1
            final_end = max_py
            ranges.append((final_start, final_end))
    return ranges

def is_valid_json(json_string):
    """Check if the string is a valid JSON."""
    try:
        json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False

def is_valid_yaml(file_path):
    """Check if the file is a valid YAML file."""
    if os.path.isfile(file_path) and (file_path.endswith('.yaml') or file_path.endswith('.yml')):
        try:
            with open(file_path, 'r') as f:
                yaml.safe_load(f)
            return True
        except yaml.YAMLError:
            return False
    return False

def is_valid_toml(file_path):
    """Check if the file is a valid TOML file."""
    if os.path.isfile(file_path) and file_path.endswith('.toml'):
        try:
            with open(file_path, 'r') as f:
                toml.load(f)
            return True
        except toml.TomlDecodeError:
            return False
    return False


def main():
    # Log to console
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    log_info = logging.StreamHandler(sys.stdout)
    log_info.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(log_info)

    logger.info("Parsing arguments")

    parser = argparse.ArgumentParser(description='Convert a point cloud file to a NetCDF file.')

    # Input files
    # Create a mutually exclusive group
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument('-ply', '--ply_filepath', type=str, help='Path to the input ply file.')
    group.add_argument('-las', '--las_filepath', type=str, help='Path to the input las file.')
    parser.add_argument('-hdr', '--hdr_filepath', type=str, default=None, help='Path to the input hdr file.')
    parser.add_argument(
        '-hyspex_cal',
        '--need_to_calibrate_hyspex',
        type=str,
        default='n',
        choices=['y', 'n'],
        help='Does the hyspex data need to be calibrated? Enter y or n.'
    )
    parser.add_argument(
        '-uga',
        '--user_global_attributes',
        type=str,
        required=True,
        help='Global attributes defined by user. Should be either 1) a JSON string with key/value pairs for global attributes, 2) a yaml file including this information 3) A toml file including this information'
        )
    parser.add_argument(
        '-mga',
        '--met_global_attributes',
        type=str,
        help='Global attributes defined by MET, a yaml file',
        default='config/global_attributes.yml'
        )
    parser.add_argument(
        '-vm',
        '--variable_mapping',
        type=str,
        required=True,
        help='Should be filepath to a yaml file including this information'
        )

    # X, Y and Z must all be specified if one is present
    # Allowed values for X, Y, Z
    allowed_xyz_values = ['latitude', 'longitude', 'altitude']
    parser.add_argument(
        '-x',
        '--xcoord',
        choices=allowed_xyz_values,
        type=str,
        help='Use this to state whether X corresponds to "longitude", "latitude" or "altitude"',
        required=False,
        default=None
        )
    parser.add_argument(
        '-y',
        '--ycoord',
        choices=allowed_xyz_values,
        type=str,
        help='Use this to state whether Y corresponds to "longitude", "latitude" or "altitude"',
        required=False,
        default=None
        )
    parser.add_argument(
        '-z',
        '--zcoord',
        choices=allowed_xyz_values,
        type=str,
        help='Use this to state whether Z corresponds to "longitude", "latitude" or "altitude"',
        required=False,
        default=None
        )
    # If X, Y and Z aren't specified, some information on the grid mapping is required
    # This could be in the crs_config file (argument below) or as a comment in the PLY file or lat/lon in file as well as X/Y
    parser.add_argument('-crs', '--crs_config', type=str, default=None, help='Path to the config yaml file contain the attributes to be written to the CRS variable.')
    parser.add_argument('-proj4', '--proj4str', type=str, default=None, help='proj4str use to create the attributes for the CRS variable.')

    # Output filepath
    parser.add_argument('-o', '--output_filepath', type=str, default=None, help='Path to the output NetCDF file. If not provided, defaults to a subfolder "output" in the git repo with the same name as the input CSV file but with .nc extension.')

    args = parser.parse_args()

    if args.crs_config and args.proj4str:
        parser.error("You cannot specify both --crs_config and --proj4str. Please provide only one or neither if the proj4 string is in the comment in the header of the PLY file.")

    # Check conditions for X, Y, Z group
    if args.xcoord or args.ycoord or args.zcoord:
        # If any of X, Y, Z are present, all must be present
        if not (args.xcoord and args.ycoord and args.zcoord):
            parser.error('If any of X, Y, or Z is specified, all must be present.')
        # Check if any of the values are repeated (latitude, longitude, altitude must all be unique)
        xyz_coords = [args.xcoord, args.ycoord, args.zcoord]
        if len(set(xyz_coords)) != 3:
            parser.error('X, Y, and Z must each be unique (latitude, longitude, altitude cannot be repeated).')

    # Check if the global attributes argument is a valid JSON string, YAML file, or TOML file
    if is_valid_json(args.user_global_attributes):
        logger.info("Global attribute provided in JSON string.")
    elif is_valid_yaml(args.user_global_attributes):
        logger.info("Global attribute provided in YAML file.")
    elif is_valid_toml(args.user_global_attributes):
        logger.info("Global attribute provided in TOML file.")
    else:
        logger.error("Global attributes must be provided in a JSON string or TOML or YAML file.")

    cf_crs = None
    crs_errors = []
    crs_warnings = []

    # Load in the grid mapping config file if it exists and not None
    if args.crs_config:
        # Check existence BEFORE the try block to avoid catching SystemExit
        if not os.path.exists(args.crs_config):
            logger.error(f"Error: The grid mapping configuration file '{args.crs_config}' could not be found.")
            sys.exit(1)

        try:
            logger.info(f"Loading grid mapping from config file")
            with open(args.crs_config, "r") as file:
                cf_crs = yaml.safe_load(file)
            logger.info("CF grid mapping configuration file loaded successfully")
        except Exception as e:
            # Fix the unpacking error by providing two lists
            cf_crs = None
            crs_errors = [f'Unable to load CRS from {args.crs_config}: {e}']
            crs_warnings = []
    elif args.proj4str:
        # Check if valid proj4 string and convert that
        logger.info("Trying to calculate a CF grid mapping from the PROJ.4 string")
        cf_crs, crs_errors, crs_warnings = get_cf_crs(proj4str=args.proj4str)
    elif args.ply_filepath:
        logger.info("Trying to calculate a CF grid mapping from the PROJ.4 string in the PLY header comment")
        cf_crs, crs_errors, crs_warnings = get_cf_crs(ply_filepath=args.ply_filepath)
    elif args.las_filepath:
        logger.info("Trying to read CRS from LAS file VLRs")
        try:
            with laspy.open(args.las_filepath) as f:
                crs = f.header.parse_crs()
            if crs is not None:
                cf_crs = crs.to_cf()
                logger.info("CRS read successfully from LAS file")
            else:
                crs_warnings = ["No CRS found in LAS file VLRs. Provide -crs_config or -proj4str if coordinate transformation is needed."]
                logger.warning(crs_warnings[0])
        except Exception as e:
            crs_warnings = [f"Could not parse CRS from LAS file: {e}"]
            logger.warning(crs_warnings[0])

    # Determine the output filepath if not provided as an argument
    if args.output_filepath is None:
        logger.info("Determining output file path for NetCDF file")
        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Create the "output" subfolder within the script directory
        output_dir = os.path.join(script_dir, 'output')
        os.makedirs(output_dir, exist_ok=True)

        # Generate the output filename based on the input filename
        if args.ply_filepath:
            input_filepath = args.ply_filepath
        elif args.las_filepath:
            input_filepath = args.las_filepath
        else:
            logger.error("Error: No input file provided")
            sys.exit(1)

        ply_filename = os.path.basename(input_filepath)
        output_filename = os.path.splitext(ply_filename)[0] + '.nc'
        args.output_filepath = os.path.join(output_dir, output_filename)
        logger.info(f"NetCDF file will be written to {args.output_filepath}")

    # Read in variable attributes from mapping file
    logger.info("Reading in variable attributes")
    variable_mapping = VariableMapping()
    variable_mapping.read_variable_mapping(args.variable_mapping)
    if args.ply_filepath:
        logger.info("Checking what variables are in the PLY file")
        variable_names = list_variables_in_ply(args.ply_filepath)
    elif args.las_filepath:
        logger.info("Checking what variables are in the LAS file")
        variable_names = list_variables_in_las(args.las_filepath)


    # Initialize variable_names if it wasn't set (safety catch)
    if 'variable_names' not in locals():
         logger.error("No input file (PLY or LAS) provided or logic failed.")
         sys.exit(1)

    if args.hdr_filepath:
        variable_names = variable_names + ['intensity']

    vm_errors, vm_warnings = variable_mapping.check(variable_names)
    #vm_errors, vm_warnings = [], [] # Use this line to bypass checking of variables

    # Read the PLY file into a pandas DataFrame
    data_errors = []
    data_warnings = []

    # Projection is extracted from the grid mapping config file if it exists.
    # Otherwise it is extracted from the PLY file
    if args.ply_filepath:
        logger.info(f"Trying to load the data from {args.ply_filepath} and write them to a pandas dataframe")
        pc_df = ply_to_df(args.ply_filepath, cf_crs, variable_mapping.dict, args.xcoord, args.ycoord, args.zcoord)
        logger.info(f"Data from {args.ply_filepath} loaded in successfully")
    elif args.las_filepath:
        logger.info(f"Processing LAS in streaming mode: {args.las_filepath}")
        
        # 1. Load Global Attributes EARLY (normally done later in the script)
        # We need them now because we are going to write and exit immediately.
        logger.info("Reading in global attributes (Early Load)")
        global_attributes = GlobalAttributes()
        global_attributes.read_global_attributes(args.user_global_attributes, args.met_global_attributes)

        # 2. Get Metadata Fast (Header only, no heavy memory usage)
        metadata = get_las_metadata(args.las_filepath, cf_crs)
        
        # 3. Update Global Attributes with bounds from header
        ga = global_attributes.dict
        if metadata['lat_min'] is not None:
            ga['geospatial_lat_min'] = metadata['lat_min']
            ga['geospatial_lat_max'] = metadata['lat_max']
            ga['geospatial_lon_min'] = metadata['lon_min']
            ga['geospatial_lon_max'] = metadata['lon_max']
        ga['geospatial_vertical_min'] = metadata['z_min']
        ga['geospatial_vertical_max'] = metadata['z_max']
        
        # Add creation timestamp
        if 'date_created' not in ga:
            now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            ga['date_created'] = now
            ga['history'] = f"{now}: Converted from LAS to NetCDF via streaming."

        # 3b. Validate global attributes and variable mapping (mirrors PLY path)
        reformatting_errors, reformatting_warnings = global_attributes.reformat_attributes()
        ga_errors, ga_warnings = global_attributes.check()

        all_errors = crs_errors + vm_errors + reformatting_errors + ga_errors
        all_warnings = crs_warnings + vm_warnings + reformatting_warnings + ga_warnings

        if all_warnings:
            logger.warning('\nWarnings\nWe recommend that these are fixed, but you can choose to ignore them:\n')
            for warning in all_warnings:
                logger.warning(warning)
        if all_errors:
            logger.error('\n\nThe following errors were found:\n')
            for error in all_errors:
                logger.error(error)
            logger.error('No NetCDF file has been created. Please correct the errors and try again.\n\n')
            sys.exit(1)

        # 4. Compute GPS time reference (also validates Adjusted GPS Time encoding)
        leap_seconds = variable_mapping.dict.get('epoch_time', {}).get('gps_leap_seconds', 18)
        gps_time_0, time_units = compute_gps_time_reference(args.las_filepath, leap_seconds)
        logger.info(f"GPS time reference: {time_units}")

        # 5. Create the Data Generator (Lazy Reader)
        # chunk_size controls how many points are held in RAM at once.
        # Must match chunk_write_size passed to create_netcdf_stream so that
        # each write aligns with netCDF4's internal storage chunks.
        chunk_size = 250_000
        las_generator = read_las_generator(
            args.las_filepath,
            cf_crs,
            variable_mapping.dict,
            chunk_size=chunk_size,
            gps_time_offset=gps_time_0
        )

        # 6. Stream Write to NetCDF
        create_netcdf_stream(
            metadata,
            las_generator,
            variable_mapping.dict,
            args.output_filepath,
            ga,
            cf_crs,
            time_units=time_units,
            chunk_write_size=chunk_size,
        )
        
        logger.info("LAS Streaming conversion complete.")
        sys.exit(0) # <--- CRITICAL: Stop here so we don't hit the old logic
    else:
        logger.error("Error: No input file provided")
        sys.exit(1)

    if cf_crs is None:
        # Ensure the DataFrame has latitude and longitude columns
        logger.info("The CF CRS attributes could not be computed. Checking if the input data contains latitude and longitude columns")
        required_columns = {'latitude', 'longitude'}
        if not required_columns.issubset(pc_df.columns):
            data_errors.append("CF CRS attributes are not provided and the input file is missing latitude and longitude columns.")
            logger.error("Latitude and longitude columns could not be found/read")

    # Read the global attributes from the specified CSV file
    logger.info("Reading in global attributes")
    global_attributes = GlobalAttributes()
    global_attributes.read_global_attributes(args.user_global_attributes, args.met_global_attributes)

    reformatting_errors, reformatting_warnings = global_attributes.reformat_attributes()
    ga_errors, ga_warnings = global_attributes.check()
    #ga_errors, ga_warnings = [], [] # Use this line to bypass check of global attributes

    errors = data_errors + ga_errors + reformatting_errors + vm_errors + crs_errors
    warnings = data_warnings + ga_warnings + reformatting_warnings + vm_warnings + crs_warnings

    if len(warnings) > 0:
        logger.warning('\nWarnings\nWe recommend that these are fixed, but you can choose to ignore them:\n')
        for warning in warnings:
            logger.warning(warning)
    if len(errors) > 0:
        logger.error('\n\nThe following errors were found:\n')
        for error in errors:
            logger.error(error)
        logger.error('No NetCDF file has been created. Please correct the errors and try again.\n\n')
    else:
        logger.info("Point cloud data and metadata read in a processed without error")

        if args.hdr_filepath:

            # Define chunk size
            chunk_size_lines = 5000
            penultimate_chunk_size = 3000
            min_final_remainder = 1000

            # Get min and max py values
            min_py = pc_df['py'].min()
            max_py = pc_df['py'].max()

            py_ranges = generate_py_ranges(min_py, max_py, chunk_size_lines, penultimate_chunk_size, min_final_remainder)

            logger.info(
                f"Creating {len(py_ranges)} NetCDF files with chunk size {chunk_size_lines} "
                f"and penultimate chunk size {penultimate_chunk_size} if needed, py range {min_py} to {max_py}."
            )

            # Loop over calculated py ranges
            for start_py, end_py in py_ranges:
                # Filter dataframes for this py range
                pc_chunk = pc_df[(pc_df['py'] >= start_py) & (pc_df['py'] <= end_py)]

                if args.need_to_calibrate_hyspex == 'y':
                    calibrate = True
                else:
                    calibrate = False


                logger.info(f"Preparing to stream hyspex lines {start_py} to {end_py} (calibrate={calibrate})")

                # Use the streaming reader — returns (generator, wavelengths)
                chunks_gen, wavelengths = read_hyspex_stream(
                    args.hdr_filepath,
                    start_py,
                    end_py,
                    chunk_size=chunk_size_lines,
                    need_to_calibrate=calibrate,
                    progress_interval=1000
                )

                logger.info(f"Hyspex data stream ready for lines {start_py}..{end_py}")

                # Derive attributes for this chunk
                global_attributes_chunk = copy.deepcopy(global_attributes)
                global_attributes_chunk.derive(pc_chunk)

                # Update output filepath
                if len(py_ranges) > 1:
                    base, ext = os.path.splitext(args.output_filepath)
                    lines = f'_lines_{start_py}_to_{end_py}'
                    output_filepath = f"{base}{lines}{ext}"
                    global_attributes_chunk.dict['title'] = global_attributes_chunk.dict['title'] + lines.replace('_',' ')
                else:
                    output_filepath = args.output_filepath

                create_netcdf(pc_chunk, chunks_gen, variable_mapping.dict, output_filepath, global_attributes_chunk.dict, cf_crs, wavelengths)

        else:
            wavelength_dfs = None
            output_filepath = args.output_filepath

            global_attributes.derive(pc_df)
            logger.info("Trying to create CF-NetCDF file(s)")
            create_netcdf(pc_df, wavelength_dfs, variable_mapping.dict, output_filepath, global_attributes.dict, cf_crs)

            logger.info(f'File created: {output_filepath}')

        logger.info('End of job')

if __name__ == '__main__':
    main()

