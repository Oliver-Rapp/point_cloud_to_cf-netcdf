import yaml


# Required attrbutes
required_attributes = [
    'units',
    'long_name',
    'standard_name',
    'coverage_content_type'
]

no_standard_name_required = [
    'px',
    'py',
    'scan_angle_rank',
    'scan_angle',
    'intensity'
]

class VariableMapping:

    def __init__(self):
        self.data = None

    def read_variable_mapping(self, filepath):
        """Read variable mapping from yaml file"""
        with open(filepath, 'r') as file:
            self.dict = yaml.safe_load(file)

    def check_variable_names(self, variable_names):
        # Check that all variable names are listed in the possible names field of a variable in the mapping file
        # Flatten all possible_names into a set of lowercase names for faster, case-insensitive lookup
        all_possible_names = {
            name.lower() for details in self.dict.values() for name in details["possible_names"]
        }
        # Normalise variable_names to lowercase and check for unrecognised names
        warnings = [
            f"({name} is not recognised as a possible name for any variable in the variable mapping file. The variable shall be ignored.)"
            for name in variable_names if name.lower() not in all_possible_names
        ]
        return warnings

    def check(self, variable_names):
        '''
        Check the values that the user has provided for the variable attributes
        '''
        # List of errors that will be appended to throughout this function.
        # If there are any errors, no CF-NetCDF file will be created
        errors = []

        # List of warnings that will be appended to throughout this function
        # Warnings will be flagged to the user but this alone will not stop a CF-NetCDF file from being created

        # 1. Check that all variable names are listed in the possible names field of a variable in the mapping file
        warnings = self.check_variable_names(variable_names)

        # 2. Check that all variables in mapping file have all the required variable attributes
        for variable in self.dict.keys():
            # If statements used to find variable matched to
            if 'possible_names' in self.dict[variable].keys():
                # Check that at least one possible name is found in the input data
                if any(name.lower() in (v.lower() for v in variable_names) for name in self.dict[variable]['possible_names']):
                    # Check only variables that are in the PLY or HYSPEX file
                    for required_attribute in required_attributes:
                        if 'attributes' in self.dict[variable].keys():
                            if required_attribute not in self.dict[variable]['attributes'].keys():
                                if variable not in no_standard_name_required and required_attribute == 'standard_name':
                                    errors.append(f'"{required_attribute}" is a required variable attribute. Please provide a value for {variable}')
                        else:
                            errors.append(f'No "attributes" key found for the {variable} variable')

                    if 'dtype' not in self.dict[variable].keys():
                        errors.append(f'A dtype must be provided for the {variable} variable. Select from f4, f8, i4, i8, S1')
                    else:
                        if self.dict[variable]['dtype'] not in ['f4','f8','i4','i8','S1']:
                            errors.append(f'Invalid dtype for the {variable} variable. Select from f4, f8, i4, i8, S1')
                        else:
                            pass
                else:
                    if variable not in ['latitude', 'longitude', 'altitude']: # Variables derived later, not required in input data
                        warnings.append(f"The variable '{variable}' in the mapping file has not been found in the input data. Skipping")
            else:
                warnings.append(f"The variable '{variable}' in the mapping file has no 'possible_names' key so can't be mapped nor written to the CF-NetCDF file. Skipping.")

        return errors, warnings
