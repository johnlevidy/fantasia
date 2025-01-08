{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python311                   # Python 3.11
    pkgs.python311Packages.flask     # Flask web framework
    pkgs.python311Packages.uvicorn   # ASGI server for running Flask
  ];

  shellHook = ''
    echo "Welcome to your Flask development environment!"
    echo "Python version: $(python --version)"
    echo "Setting up virtual environment and installing dependencies..."
    
    # Create a virtual environment if it does not exist
    if [ ! -d "venv" ]; then
      python -m venv venv
      source venv/bin/activate
      python -m pip install --upgrade pip
      python -m pip install flask uvicorn
    else
      source venv/bin/activate
    fi
    
    echo "Environment setup complete! Activate with 'source venv/bin/activate'."
  '';
}

