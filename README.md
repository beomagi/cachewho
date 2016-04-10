# cachewho
A JSON/cmdline interactive key value store using multithreading to enhance performance. Basic functionality: put one key/value tuple, put many, get one, get many etc.


Run cachewho.py without arguments to start the server

Default is serving at 127.0.0.1:8084

Run ./cachewho.py help or point your browser to http://127.0.0.1:8084/help/ for the usage info:
````
Version: sqrt(pi)
Usage:

To interact with the cachewho server, use cachewho.py or curl
Examples below show both methods for interacting with cachewho


e.g. put one and get one (put, get and jget functions)
    Use cachewho directly
    >>>>> ./cachewho.py put 'key-f' 89
    >>>>> ./cachewho.py get 'key-f'
    89
    >>>>> ./cachewho.py jget 'key-f'
    {"key":"key-f","val":"89","age":"9.901"}


    >>>>> ./cachewho.py json '{"cmd":"put","key":"yourdata","val":"stuff"}'
    >>>>> ./cachewho.py json '{"cmd":"get","key":"yourdata"}'
    stuff
    >>>>> ./cachewho.py json '{"cmd":"jget","key":"yourdata"}'
    {"key":"yourdata","val":"stuff","age":"12.443"}

    >>>>> curl -X POST -d '{"cmd": "put","key":"moredata","val":"morestuff"}' 127.0.0.1:8084
    >>>>> curl -X POST -d '{"cmd": "get","key":"moredata"}' 127.0.0.1:8084
    morestuff
    >>>>> curl -X POST -d '{"cmd": "jget","key":"moredata"}' 127.0.0.1:8084
    {"key":"moredata","val":"morestuff","age":"256.613"}


e.g. Put many to add multiple key,value pairs at once (mput)
    >>>>> curl -X POST -d '{"cmd": "mput","items": [{"key1": 3}, {"key2": 5}]}' 127.0.0.1:8084
    >>>>> ./cachewho.py json '{"cmd": "mput","items": [{"keybee": "buzz"}, {"beeboo": "belly"}]}'


e.g. Get many on a defined list of keys (mget)
    >>>> curl -X POST -d '{"cmd": "mget","items": ["key1","key2","keyx"]}' 127.0.0.1:8084
    [
    {"key":"key1","val":"3","age":"10213.538"},
    {"key":"key2","val":"5","age":"10213.538"},
    {"key":"keyx","val":"Charles Xavier","age":"9890.759"}
    ]

    >>>>> ./cachewho.py json '{"cmd": "mget","items": ["key1","key2","keyx"]}'
    [
    {"key":"key1","val":"3","age":"10259.559"},
    {"key":"key2","val":"5","age":"10259.559"},
    {"key":"keyx","val":"Charles Xavier","age":"9936.78"}
    ]

e.g. Get list of keys defined by substring (getlike)
    >>>>> curl -X POST -d '{"cmd": "getlike","key": "bee"}' http://127.0.0.1:8084
    [
    {"key:":"keybee","val:":"buzz","age:":"4062.554"},
    {"key:":"beeboo","val:":"belly","age:":"4062.554"}
    ]

    >>>>> ./cachewho.py json '{"cmd": "getlike","key": "bee"}'
    [
    {"key:":"keybee","val:":"buzz","age:":"4304.626"},
    {"key:":"beeboo","val:":"belly","age:":"4304.626"}
    ]


e.g. health check - is the server running? Note, there's a GET method for easy browser access
    >>>>> ./cachewho.py json '{"cmd":"health"}'
    OK
    >>>>> curl 127.0.0.1:8084/health
    OK
    >>>>> curl -X POST -d '{"cmd":"health"}' http://127.0.0.1:8084
    OK

e.g. browser shortcuts:
    http://127.0.0.1:8084/help/     - help page
    http://127.0.0.1:8084/          - lists all items
    http://127.0.0.1:8084/health/   - cachewho health
    http://127.0.0.1:8084/key/thing - gets the lone value of key "thing"
    http://127.0.0.1:8084/save/file - saves the current dictionary to "file"
    http://127.0.0.1:8084/load/file - loads the current dictionary from "file"
    http://127.0.0.1:8084/status/   - shows server statistics

````
