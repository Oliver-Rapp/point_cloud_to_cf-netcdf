#!/usr/bin/env python3
import netCDF4 as nc
import numpy as np
import uuid
import re
import logging
from lib.utils import scale_to_integers

logger = logging.getLogger(__name__)

class NetCDF:

    def __init__(self, output_filepath):
        self.output_filepath = output_filepath
        self.ncfile = nc.Dataset(self.output_filepath, mode='w', format='NETCDF4')

    # def calculate_vertical_bounds(self, altitude_values):
    #     return np.min(altitude_values), np.max(altitude_values)

    def define_grid_mapping(self, cf_crs):
        '''
        Write the CRS variable with the projection
        '''
        crs = self.ncfile.createVariable('crs', 'i4')

        for attr, value in cf_crs.items():
            crs.setncattr(attr, value)

    def write_coordinate_variables(self, pc_df, wavelengths=None):
        """
        Write coordinate variables for point and optionally band dimensions.
        """

        num_points = len(pc_df)

        # Define the 'point' dimension and variable
        self.ncfile.createDimension('point', size=num_points)
        point_var = self.ncfile.createVariable('point', 'f4', ('point',), zlib=True, complevel=1)
        point_var[:] = np.arange(num_points, dtype=np.float32)
        point_var.setncattr('units', '1')
        point_var.setncattr('long_name', 'Arbitrary counter for number of points in the point cloud')
        point_var.setncattr('standard_name', 'number_of_observations')
        point_var.setncattr('coverage_content_type', 'coordinate')
        logger.info('Wrote coordinate variable for each point')

        # Define the 'band' dimension if wavelengths are given
        if wavelengths is not None:
            wavelengths = np.asarray(wavelengths, dtype=np.float32)
            num_bands = len(wavelengths)

            if num_bands == 0:
                logger.warning("Wavelengths array provided but empty — 'band' dimension not created.")
                return

            self.ncfile.createDimension('band', size=num_bands)
            band_var = self.ncfile.createVariable('band', 'f4', ('band',), zlib=True, complevel=1)
            band_var[:] = wavelengths

            band_var.setncattr('units', 'nanometers')
            band_var.setncattr('long_name', 'Spectral band')
            band_var.setncattr('standard_name', 'radiation_wavelength')
            band_var.setncattr('coverage_content_type', 'coordinate')
            logger.info(f'Wrote coordinate variable for each wavelength band ({num_bands} total)')

    def write_1d_data(self, pc_df, variable_mapping, time_units=None):

        # Loop through columns in input data
        for col in pc_df.columns:
            # Loop through variables in mapping configuration file
            for variable in variable_mapping.keys():
                if 'possible_names' in variable_mapping[variable].keys():
                    # Matching input data to variable in config file with metadata
                    if col in variable_mapping[variable]['possible_names']:
                        # Initialising variable
                        netcdf_variable = self.ncfile.createVariable(
                            variable,
                            variable_mapping[variable]['dtype'],
                            ('point',),
                            zlib=True,
                            complevel=1
                            )
                        # Writing data to variable
                        netcdf_variable[:] = pc_df[col]
                        # Writing variable attributes
                        for attribute, value in variable_mapping[variable]['attributes'].items():
                            if isinstance(value, int):
                                cast_value = int(value)
                            elif isinstance(value, float):
                                cast_value = float(value)
                            elif isinstance(value, str):
                                cast_value = str(value)
                            else:
                                cast_value = value

                            netcdf_variable.setncattr(attribute, cast_value)
                        # Override time units with the dynamic per-file reference
                        if variable == 'epoch_time' and time_units is not None:
                            netcdf_variable.setncattr('units', time_units)
                        logger.info(f'Data and metadata written to {variable} variable')

    def write_2d_data(self, wavelength_source, variable_mapping, wavelengths=None):
        """
        Write 2D spectral intensity data (point x band) to NetCDF.

        wavelength_source : generator yielding NumPy arrays
                            OR list of Pandas DataFrames (legacy).
        variable_mapping : dict describing variable attributes.
        wavelengths : optional array of wavelength centres for metadata.
        """
        # Create the intensity variable
        intensity = self.ncfile.createVariable(
            'intensity',
            'i4',
            ('point', 'band'),
            zlib=True,
            complevel=1
        )

        scale_factor = 1e-6
        start_row = 0

        # Decide whether this is a generator or list
        if hasattr(wavelength_source, '__iter__') and not isinstance(wavelength_source, (list, tuple)):
            # --- Streaming mode ---
            logger.info("Writing intensity data in streaming mode.")
            for i, chunk in enumerate(wavelength_source, start=1):
                if not isinstance(chunk, np.ndarray):
                    raise TypeError("Expected NumPy array from streaming reader.")
                n_rows = chunk.shape[0]
                logger.info(f"Writing chunk {i} ({n_rows} rows) to intensity variable.")
                intensity[start_row:start_row + n_rows, :] = scale_to_integers(chunk, scale_factor)
                start_row += n_rows
        else:
            # --- Legacy mode (list of DataFrames) ---
            logger.info("Writing intensity data from DataFrame list.")
            for ii, df in enumerate(wavelength_source):
                logger.info(f"Writing dataframe {ii + 1} of {len(wavelength_source)}")
                arr = df.to_numpy()
                n_rows = arr.shape[0]
                end_row = start_row + n_rows
                intensity[start_row:end_row, :] = scale_to_integers(arr, scale_factor)
                start_row = end_row

        # Assign attributes
        attrs = variable_mapping['intensity']['attributes']
        for attribute, value in attrs.items():
            if isinstance(value, (int, float, str)):
                cast_value = value
            else:
                cast_value = str(value)
            intensity.setncattr(attribute, cast_value)

        intensity.setncattr('scale_factor', scale_factor)

        logger.info('2D intensity data and metadata written to file')

    def assign_global_attributes(self,global_attributes):
        for attribute, value in global_attributes.items():
            if attribute not in self.ncfile.ncattrs() and value not in [np.nan, '', 'None', None, 'nan']:
                # Removing short name in brackets
                if attribute == 'creator_institution':
                    value = re.sub(r"\s*\([^)]*\)", "", value)
                self.ncfile.setncattr(attribute, value)

        # Assigning an id if not already assigned
        if 'id' not in global_attributes:
            file_id = f'no.met.adc:{uuid.uuid4()}'
            self.ncfile.setncattr('id',file_id)

    def close(self):
        # Close the file
        self.ncfile.close()


def create_netcdf(pc_df, wavelength_source, variable_mapping, output_filepath,
                global_attributes, cf_crs, wavelengths=None, time_units=None):
    """
    Create a CF-compliant NetCDF file.

    pc_df : pandas dataframe with coordinate information.
    wavelength_source : generator OR list of data (NumPy arrays or DataFrames).
    variable_mapping : dict of variable names and attributes.
    output_filepath : output file path.
    global_attributes : dict of global attributes.
    cf_crs : dict of CRS variable attributes.
    wavelengths : optional 1D array of wavelength centres (for band coordinate).
    time_units : optional CF units string for the epoch_time variable, e.g.
                 "seconds since 2024-05-01 12:00:00 UTC". Overrides the YAML default.
    """
    netcdf = NetCDF(output_filepath)

    # Write coordinates first
    netcdf.write_coordinate_variables(pc_df, wavelengths=wavelengths)

    if cf_crs:
        netcdf.define_grid_mapping(cf_crs)

    netcdf.write_1d_data(pc_df, variable_mapping, time_units=time_units)

    if wavelength_source is not None:
        netcdf.write_2d_data(wavelength_source, variable_mapping, wavelengths=wavelengths)

    netcdf.assign_global_attributes(global_attributes)
    netcdf.close()

def create_netcdf_stream(metadata, data_generator, variable_mapping, output_filepath, global_attributes, cf_crs, time_units=None):
    """
    Creates NetCDF by streaming data. 
    Only creates variables that actually exist in the input stream.
    """
    import numpy as np
    import netCDF4 as nc

    # Initialize Dataset
    with nc.Dataset(output_filepath, mode='w', format='NETCDF4') as ncfile:
        
        # 1. Dimensions
        num_points = metadata['num_points']
        ncfile.createDimension('point', size=num_points)
        
        # 2. Grab the first chunk to see what data we ACTUALLY have
        try:
            first_chunk = next(data_generator)
        except StopIteration:
            print("Error: Input file appears to be empty.")
            return

        # 3. Create Variables
        nc_vars = {}
        
        # Define mandatory coordinates
        coords = ['latitude', 'longitude', 'altitude', 'X', 'Y', 'Z']
        
        # Combine coordinates with dynamic variables that exist in the first chunk
        # This filters out variables defined in YAML but missing in LAS
        vars_to_create = set(coords)
        for var_name in variable_mapping.keys():
            if var_name in first_chunk:
                vars_to_create.add(var_name)

        for var_name in vars_to_create:
            # Determine properties from mapping or defaults
            if var_name in variable_mapping:
                details = variable_mapping[var_name]
                dtype = details.get('dtype', 'f8')
                attributes = details.get('attributes', {})
            else:
                # Fallback for coords not explicitly in mapping (unlikely given your config)
                dtype = 'f8'
                attributes = {}

            # Create variable
            v = ncfile.createVariable(var_name, dtype, ('point',), zlib=True, complevel=4)
            
            # Apply attributes
            for attr, val in attributes.items():
                v.setncattr(attr, val)
            # Override time units with the dynamic per-file reference
            if var_name == 'epoch_time' and time_units is not None:
                v.setncattr('units', time_units)

            nc_vars[var_name] = v

        # 4. Write CRS
        if cf_crs:
            crs = ncfile.createVariable('crs', 'i4')
            for attr, value in cf_crs.items():
                crs.setncattr(attr, value)
            
        # 5. Write Global Attributes
        for attr, value in global_attributes.items():
            if value not in [None, '']:
                ncfile.setncattr(attr, value)

        # 6. Write the FIRST chunk (which we already pulled)
        print(f"Starting stream write for {num_points} points...")
        current_idx = 0
        
        chunk_len = len(first_chunk['X'])
        end_idx = current_idx + chunk_len
        
        for var_name, nc_var in nc_vars.items():
            if var_name in first_chunk:
                nc_var[current_idx:end_idx] = first_chunk[var_name]
        
        current_idx = end_idx
        print(f"  Processed {current_idx} / {num_points} points...")

        # 7. Write the REST of the stream
        for chunk_idx, data_dict in enumerate(data_generator):
            chunk_len = len(data_dict['X'])
            end_idx = current_idx + chunk_len
            
            for var_name, nc_var in nc_vars.items():
                if var_name in data_dict:
                    nc_var[current_idx:end_idx] = data_dict[var_name]
            
            current_idx = end_idx
            if chunk_idx % 5 == 0:
                print(f"  Processed {current_idx} / {num_points} points...")

    print(f"Finished writing {output_filepath}")