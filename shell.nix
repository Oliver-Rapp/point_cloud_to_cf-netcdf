{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    # System Tools
    pkgs.git

    # Python Environment
    pkgs.python3
    pkgs.python3Packages.pip
    pkgs.python3Packages.virtualenv

    # --- HARMONIZED DEPENDENCIES ---
    pkgs.python3Packages.netcdf4
    pkgs.python3Packages.pyyaml
    pkgs.python3Packages.pandas
    pkgs.python3Packages.flask
    pkgs.python3Packages.plyfile
    pkgs.python3Packages.xarray
    pkgs.python3Packages.dask
    pkgs.python3Packages.laspy
    pkgs.python3Packages.lazrs
    pkgs.python3Packages.numpy
    pkgs.python3Packages.pyproj  
    
    # Editor
    pkgs.vscodium
  ];

  shellHook = ''
    if [ ! -d ".venv" ]; then
      echo "Creating new virtual environment..."
      python -m venv .venv --system-site-packages
    fi
    source .venv/bin/activate
  '';
}
