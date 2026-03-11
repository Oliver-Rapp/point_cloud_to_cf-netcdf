import csv
import subprocess
import json
import argparse

def run_script(csv_file):
    # Define the known argument names for the command
    known_args = [
        'ply_filepath', 'las_filepath', 'hdr_filepath', 'xcoord', 'ycoord', 'zcoord',
        'crs_config', 'proj4str', 'variable_mapping', 'output_filepath'
    ]

    with open(csv_file, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            # Prepare the list of arguments
            args = []

            # Add known arguments if they are present in the row
            for arg in known_args:
                if row.get(arg):
                    args.append(f'--{arg}={row[arg]}')

            # Remaining columns as global_attributes dictionary
            global_attributes = {k: row[k] for k in row.keys() if k not in known_args}

            # Convert the dictionary to a JSON string to pass as an argument
            global_attributes_json = json.dumps(global_attributes)

            # Add the global_attributes argument
            args.append(f'--user_global_attributes={global_attributes_json}')

            # Run the script with subprocess and pass the arguments
            subprocess.run(['python3', 'pc_to_netcdf.py'] + args)

if __name__ == "__main__":
    # Set up argument parser to take CSV filepath as an argument
    parser = argparse.ArgumentParser(description='Run script for each row in the CSV file.')
    parser.add_argument('csv_filepath', type=str, help='Path to the CSV file.')

    # Parse the arguments
    args = parser.parse_args()

    # Call run_script with the provided CSV file
    run_script(args.csv_filepath)
