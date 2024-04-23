# pylint: disable=c-extension-no-member, global-statement, fixme

"""
Virtual Reality Exhibition Switchboard

A system for casting vr headsets during exhibitions.
"""

import json
import os
import re
import time
import subprocess
import pythoncom
import win32com.client
import win32gui

from flask import Flask, request, render_template

# TODO: Improve exception reporting for all functions


def load_device_name_map():
    """
    Load the map from device id to name.
    Returns the map as a dict.
    """
    loaded_map = {}
    try:
        with open("devicemap.txt", "r", encoding="utf-8") as file:
            for line in file.readlines():
                split = line.split(" ", 1)
                device = split[0]
                name = split[1].strip("\n")
                loaded_map[device] = name
    except OSError:
        pass
    return loaded_map


device_name_map = load_device_name_map()


def map_device_to_name(device_id):
    """
    If the device name map contains an entry for the given id, then the
    name is returned, otherwise fallback to the id.
    """
    return device_name_map.get(device_id, device_id)


app = Flask(__name__)

SCRCPY_PROC = None
active_tcpip_devices = set()


@app.route("/")
def run():
    """
    The home page of the server. Shows the gui.
    """
    usb_devices = get_usb_devices()["devices"]
    tcpip_devices = get_active_tcpip_devices()["devices"]

    complete_device_name_map = {}
    for device in usb_devices:
        complete_device_name_map[device] = map_device_to_name(device)
    for device in tcpip_devices:
        complete_device_name_map[device] = map_device_to_name(device)

    tcpip_devices.sort(key=map_device_to_name)

    return render_template(
        "index.html",
        usb_devices=usb_devices,
        tcpip_devices=tcpip_devices,
        device_name_map=complete_device_name_map,
    )


@app.route("/get_devices")
def get_devices():
    """
    Get the list of all connected devices.
    """
    devices = adb_get_devices()

    return {"devices": devices}


@app.route("/get_active_tcpip_devices")
def get_active_tcpip_devices():
    """
    Get the list of active tcpip devices.
    """
    return {"devices": list(active_tcpip_devices)}


@app.route("/get_connected_tcpip_devices")
def get_connected_tcpip_devices():
    """
    Get the list of devices connected via tcpip.
    """
    devices = adb_get_devices()
    devices = [s for s in devices if re.match(r"\b\d+(?:\.\d+){3}\b", s)]
    return {"devices": devices}


@app.route("/get_usb_devices")
def get_usb_devices():
    """
    Get the list of devices connected over usb.
    """
    devices = adb_get_devices()
    devices = [s for s in devices if not re.match(r"\b\d+(?:\.\d+){3}\b", s)]

    return {"devices": devices}


@app.route("/activate_tcpip")
def activate_tcpip():
    """
    Activate tcpip for the given device.
    """
    device = request.args.get("device")

    status = adb_check_device_same_network(device)

    if not status:
        return {"status": "fail - device not connected"}

    ip_addr = adb_get_ip(device)
    port_offset = ip_addr.split(".")[-1]
    port = 5555 + int(port_offset)

    command = ["scrcpy\\adb", "-s", device, "tcpip", str(port)]
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as proc:
        _, _ = proc.communicate()

    active_tcpip_devices.add(ip_addr)
    save_tcpip_devices()

    name = map_device_to_name(device)
    device_name_map[ip_addr] = name

    return {"status": "success", "device": device, "addr": ip_addr + ":" + str(port)}


@app.route("/deactivate_tcpip")
def deactivate_tcpip():
    """
    Deactivate tcpip for the given device.
    """
    ip_addr = request.args.get("ip")
    port_offset = ip_addr.split(".")[-1]
    port = 5555 + int(port_offset)

    device = adb_get_device_serialno(f"{ip_addr}:{port}")

    command = ["scrcpy\\adb", "-s", f"{ip_addr}:{port}", "usb"]
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as proc:
        _, _ = proc.communicate()

    if ip_addr in active_tcpip_devices:
        active_tcpip_devices.remove(ip_addr)

    return {"status": "success", "device": device}


@app.route("/connect_tcpip")
def connect_tcpip():
    """
    Connect the specified device over tcpip.
    """
    ip_addr = request.args.get("ip")
    port_offset = ip_addr.split(".")[-1]
    port = 5555 + int(port_offset)

    command = ["scrcpy\\adb", "connect", f"{ip_addr}:{port}"]
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as proc:
        _, _ = proc.communicate()

    return {"status": "success"}


@app.route("/disconnect_tcpip")
def disconnect_tcpip():
    """
    Disconnect the specified device from tcpip.
    """
    ip_addr = request.args.get("ip")
    port_offset = ip_addr.split(".")[-1]
    port = 5555 + int(port_offset)

    command = ["scrcpy\\adb", "disconnect", f"{ip_addr}:{port}"]
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as proc:
        _, _ = proc.communicate()

    return {"status": "success"}


@app.route("/reconnect_tcpip_devices")
def reconnect_tcpip_devices():
    """
    Reconnect to devices that were previously connected via tcpip.
    """
    load_tcpip_devices()
    rescan_tcpip_devices()

    return ""


@app.route("/run_app")
def run_app():
    """
    Run an app on the specified device
    """
    ip_addr = request.args.get("ip")
    port_offset = ip_addr.split(".")[-1]
    port = 5555 + int(port_offset)
    device = f"{ip_addr}:{port}"
    app_name = request.args.get("app")

    adb_run_app(device, app_name)

    return {"status": "success"}


@app.route("/stop_app")
def stop_app():
    """
    Close an app on the specified device
    """
    ip_addr = request.args.get("ip")
    port_offset = ip_addr.split(".")[-1]
    port = 5555 + int(port_offset)
    device = f"{ip_addr}:{port}"
    app_name = request.args.get("app")

    adb_stop_app(device, app_name)

    return {"status": "success"}


@app.route("/run_scrcpy")
def run_scrcpy():
    # pylint: disable=too-many-locals
    """
    Run scrcpy to screen cast the specified device.
    """
    global SCRCPY_PROC

    # Sets scrcpy's parameters
    bit_rate = request.args.get("bit_rate", default="8M")
    max_fps = request.args.get("max_fps", default="60")
    full_screen = request.args.get("full_screen", default="false")
    with_audio = request.args.get("with_audio", default="false")

    ip_addr = request.args.get("ip")
    port_offset = ip_addr.split(".")[-1]
    port = 5555 + int(port_offset)
    device = f"{ip_addr}:{port}"

    env = os.environ.copy()

    command = ["scrcpy\\scrcpy", "--always-on-top", f"--tcpip={ip_addr}:{port}"]
    command.append(f"--window-title={device}")

    if bit_rate is not None:
        command.append(f"--video-bit-rate={bit_rate}")
    if max_fps is not None:
        command.append(f"--max-fps={str(max_fps)}")
    if full_screen == "true":
        command.append("-f")
    if with_audio == "false":
        command.append("--no-audio")

    model = adb_get_device_model(device)
    print(model)
    print("Quest 2" in model)
    if "Quest 2" in model:
        print("Quest 2 detected")
        adb_disable_proximity_sensor(device)
        command.append("--crop=1600:900:2017:510")

    # Runs scrcpy
    with subprocess.Popen(command, env=env, shell=False) as new_proc:
        # Runs a loop checking for a window with the device's name to determine
        # success or failure
        end = 10.0
        cur = 0.0

        while cur < end:
            time.sleep(0.5)
            cur += 0.5

            if device in win32_get_window_titles():
                # Required since API calls run in a separate thread. Initializes
                # a shell instance
                # pylint: disable=no-member
                pythoncom.CoInitialize()
                shell = win32com.client.Dispatch("WScript.Shell")
                hwnd = win32gui.FindWindow(None, device)

                # Strange workaround to get SetForegroundWindow to work without
                # returning exceptions. Equivalent to holding the ALT key
                shell.SendKeys("%")
                win32gui.SetForegroundWindow(hwnd)

                # Replaces the previous scrcpy
                if SCRCPY_PROC is not None:
                    SCRCPY_PROC.kill()

                SCRCPY_PROC = new_proc

                return {"status": "success"}

    return {"status": "fail -- unable to connect to device"}


@app.route("/exit_scrcpy")
def exit_scrcpy():
    """
    Kill the scrcpy process.
    """
    if SCRCPY_PROC is None:
        return {"status": "fail - scrpy_proc is None"}

    SCRCPY_PROC.kill()

    return {"status": "success"}


@app.route("/get_scrcpy_status")
def get_scrcpy_status():
    """
    Check the status of the scrcpy process.
    """
    if SCRCPY_PROC is None:
        return {"status": "process not started"}

    status = SCRCPY_PROC.poll()

    if status is None:
        return {"status": "process running"}
    return {"status": "process terminated"}


def adb_get_devices():
    """
    Get a list of devices from adb.
    """
    command = ["scrcpy\\adb", "devices"]
    with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
        stdout, _ = proc.communicate()
        stdout = stdout.decode()

    devices = stdout.split("\n")
    devices = [s for s in devices if "\tdevice" in s]

    devices = [s.split("\t")[0] for s in devices]

    return devices


def adb_get_device_model(device):
    """
    Get the model of the device.
    """
    device_port = device.split(":")[0]
    port_offset = device_port.split(".")[-1]
    port = 5555 + int(port_offset)

    command = ["scrcpy\\adb", "connect", f"{device}:{port}"]
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE) as _:
        pass

    time.sleep(0.3)

    command = ["scrcpy\\adb", "-s", device, "shell", "getprop", "ro.product.model"]
    with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
        stdout, _ = proc.communicate()
        stdout = stdout.decode()

    return stdout


def adb_get_ip(device):
    """
    Get the ip address of the device.
    """
    command = ["scrcpy\\adb", "-s", device, "shell", "ifconfig", "wlan0"]
    with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
        stdout, _ = proc.communicate()
        stdout = stdout.decode()

    address = re.findall(r"inet addr:\b\d+(?:\.\d+){3}\b", stdout)
    if len(address) > 0:
        address = address[0]
        address = address[10:]
    else:
        address = None

    return address


def adb_get_device_serialno(device):
    """
    Get the serial number of the device.
    """
    command = ["scrcpy\\adb", "-s", device, "shell", "getprop", "ro.serialno"]
    with subprocess.Popen(command, stdout=subprocess.PIPE) as proc:
        stdout, _ = proc.communicate()
        stdout = stdout.decode()
    return stdout


def adb_check_device_same_network(device):
    """
    Check if the given device is accessable on the network.
    """
    ip_addr = adb_get_ip(device)
    print(ip_addr)

    if ip_addr is None:
        return False

    resp = os.system("ping -n 1 " + ip_addr)

    return resp == 0


def adb_disable_proximity_sensor(device):
    """
    Disable the proximity sensor on the given device.
    """
    adb_get_ip(device)
    command = [
        "scrcpy\\adb",
        "-s",
        device,
        "shell",
        "am",
        "broadcast",
        "-a",
        "com.oculus.vrpowermanager.prox_close",
    ]
    with subprocess.Popen(command) as _:
        pass


def adb_enable_proximity_sensor(device):
    """
    Enable the proximity sensor on the given device.
    """
    adb_get_ip(device)
    command = [
        "scrcpy\\adb",
        "-s",
        device,
        "shell",
        "am",
        "broadcast",
        "-a",
        "com.oculus.vrpowermanager.automation_disable",
    ]
    with subprocess.Popen(command) as _:
        pass


def adb_run_app(device, app_name):
    """
    Run an app on the given device.
    """
    adb_get_ip(device)
    command = [
        "scrcpy\\adb",
        "-s",
        device,
        "shell",
        "monkey",
        "-p",
        app_name,
        "1",
    ]
    with subprocess.Popen(command) as _:
        pass


def adb_stop_app(device, app_name):
    """
    Stop an app on the given device.
    """
    adb_get_ip(device)
    command = [
        "scrcpy\\adb",
        "-s",
        device,
        "shell",
        "am",
        "force-stop",
        app_name,
    ]
    with subprocess.Popen(command) as _:
        pass


def win32_get_window_titles():
    """
    Get the titles of currently open windows.
    """
    retval = []
    win32gui.EnumWindows(
        lambda hwnd, _: retval.append(win32gui.GetWindowText(hwnd)), None
    )

    return retval


def clear_tcpip_devices():
    """
    Clear the `active_tcpip_devices` list (including on file).
    """
    active_tcpip_devices.clear()
    save_tcpip_devices()


def save_tcpip_devices():
    """
    Save the `active_tcpip_devices` list to file.
    """
    with open("tcpip_devices.json", "w", encoding="utf-8") as file:
        json.dump(list(active_tcpip_devices), file)


def load_tcpip_devices():
    """
    Populate `active_tcpip_devices` from the list previously saved to file.
    """
    global active_tcpip_devices
    if os.path.exists("tcpip_devices.json"):
        with open("tcpip_devices.json", "r", encoding="utf-8") as file:
            active_tcpip_devices = set(json.load(file))


def rescan_tcpip_devices():
    """
    Scan for tcpip devices to populate the `active_tcpip_devices` set.
    """
    global active_tcpip_devices

    for ip_addr in active_tcpip_devices:
        offset = ip_addr.split(".")[-1]
        port = 5555 + int(offset)

        command = ["scrcpy\\adb", "connect", f"{ip_addr}:{port}"]
        with subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
        ) as _:
            pass

    time.sleep(5)
    devices = adb_get_devices()
    devices = [s.split(":")[0] for s in devices if re.match(r"\b\d+(?:\.\d+){3}\b", s)]

    active_tcpip_devices = set(devices)
    save_tcpip_devices()


def create_app():
    """
    Load and create the flask app.
    """
    load_tcpip_devices()
    return app
