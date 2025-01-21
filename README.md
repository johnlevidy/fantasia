# fantasia

Little web server which takes a json, csv, or clipboard copy from google sheet project description ( tsv ) and uses graphviz to render a nice DAG view. 

Also computes a few helpful metrics like parallelism ratio and indicates items which have to be started imminently in order to meet completion deadlines ( based on existing estimates ). 


To run the application:

```
nix-shell
python -m backend.app
```

To run tests:

```
python -m pytest
```
