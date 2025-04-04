{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python311                   # Python 3.11
    pkgs.python311Packages.pytest
    pkgs.python311Packages.flask     # Flask web framework
    pkgs.python311Packages.uvicorn   # ASGI server for running Flask
    pkgs.graphviz
    pkgs.python311Packages.bidict
    pkgs.python311Packages.numpy
    pkgs.python311Packages.networkx
    pkgs.python311Packages.graphviz  # Python bindings for Graphviz
    pkgs.python311Packages.pandas
    pkgs.python311Packages.ortools
    pkgs.python311Packages.protobuf
  ];

  shellHook = ''
    echo "Welcome to your Flask development environment!"
    echo "Python version: $(python --version)"
    echo "Flask version: $(python -c 'import flask; print(flask.__version__)')"
    echo "Graphviz version: $(dot -V 2>&1)"
  '';
}
