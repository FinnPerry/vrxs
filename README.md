# Virtual Reality Exhibition Switchboard (VRXS)

VRXS is a system for managing wireless casting and app starting/stopping for one
or multiple VR headsets.

# Setup

1. Run `pipenv install` on this folder.
1. Ensure that port 8080 is on the firewall's whitelist.
1. Ensure that all headsets and the  host pc are connected to the same network.
1. Ensure that Developer Mode is enabled on the headset
   (see https://developer.oculus.com/documentation/native/android/mobile-device-setup/).

# Optional Setup

1. Assign fixed ip addresses for both the host pc and the headsets.
   - This is technically not required for the system to run but is recomended to
     prevent things breaking due to the devices getting assigned random
     new addresses.
1. Create `devicemap.txt`. This file maps headset ids to human readable names
   to make the device list in the web ui.
   - To obtain the headset ids, plug in the headset via usb then copy it's id
     from the usb devices section of the web ui. Then add a line to the device
     map file with the following format: `<DEVICE_ID> <NAME>`.
   - The server must be restarted for changes to take effect.

# Running

Start up the server with `run.bat`,
then access the web ui via `http://<IP_ADDRESS>:8080`.

See the instructions at the bottom of the web ui for how to
connect and manage headsets.

# Technical Info

If you are a developer, see [here](TechnicalInfo.md) for technical info.
