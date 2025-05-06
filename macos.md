# MacOS development notes

```
# Start postgres (one-shot)
/opt/homebrew/opt/postgresql@14/bin/postgres -D /opt/homebrew/var/postgresql@14
psql -h localhost -p 5432 -d postgres # connect using the default database
    postgres=# create database fantasia;

# Installed python packages
% pip list
Package         Version
--------------- -----------
absl-py         2.2.2
bidict          0.23.1
blinker         1.9.0
click           8.1.8
Flask           3.1.0
immutabledict   4.2.1
itsdangerous    2.2.0
Jinja2          3.1.6
MarkupSafe      3.0.2
networkx        3.4.2
numpy           2.2.4
ortools         9.12.4544
pandas          2.2.3
pip             25.1.1
protobuf        5.29.4
psycopg2        2.9.10
python-dateutil 2.9.0.post0
pytz            2025.2
six             1.17.0
tzdata          2025.2
Werkzeug        3.1.3
```
