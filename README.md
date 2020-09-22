How to use
=======

    git clone https://github.com/droid4control/pymodbus_async.git --branch=pymodbus_v2.4.0
    cd pymodbus_async
    # edit client.py if serial port is not ttyUSB0
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    python3 ./client.py
    deactivate
