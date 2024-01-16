# API

The intended flow is to run through these commands in this specific order for 
each device that needs to be connected

1. `/get_devices`
    - Retrieves a list of devices connected to `adb` both wired and wirelessly
    - This should always be the entrypoint into your program
1. `/activate_tcpip?device=<device>`
    - Activates wireless `adb` on the specified device
    - This allows you to connect to `adb` wirelessly by running `adb connect 
      <ip>:<port>`
    - `scrcpy_utils` takes the last 4 digits of the IP address, adds 5555
      to this, and opens that port on the device to listen for `adb`
      connections
1. `/connect_tcpip?ip=<ip>`
    - This makes a wireless device visible to `/get_devices`
    - This step is implicitly performed when running `/run_scrcpy`
1. `/run_scrcpy?ip=<ip>&bit_rate=<bitrate>`
    - Runs `scrcpy` to cast the targetted device onto the PC running this
      server
    - If the connected device is a Quest 2, this also disables its
      proximity sensor and crops the screen to the correct size
    - The following parameters are provided to allow users to tweak the
      video quality to suit network conditions
    - Parameters:
        - `bit_rate` : Specifies the quality of the stream. Can use numbers
          (e.g. 6000 for 6000kbps) or abbreviations (e.g 6M for 6mbps)
        - `max_fps` : Specifies the max fps of the stream
        - `full_screen` : If `true`, the stream fills the screen
        - `with_audio` : If `false`, audio will not be streamed to the PC.
          In the current patch, the Quest 2 is unable to maintain more than
          one audio stream, so if this is `true`, then all audio gets
          rerouted to the stream computer
1. `/get_scrcpy_status`
    - Returns whether or not a `scrcpy` process currently exists
1. `/exit_scrcpy`
    - If a `scrcpy` session is active, closes it

# Connection status spoofing

This section documents some work-in-progress-but-never-finished research that
was done towards spoofing wifi connection status.

Spoofing is useful because ideally you can setup an exhibition with a
wireless router that connects the headsets to the host pc but isn't
actually connected to the internet, but there was some issue where the
headsets see they have a wifi connection and try to phone home which fails
and the headsets don't like that.

1. Ensure that the casting PC is connected via LAN to `iCinemaPortable-5G`
1. Ensure that the casting PC has the IP address `192.168.8.100`
1. From the `dnschef` folder, run 
   `pipenv run python dnschef.py --nameservers 0.0.0.0#8080 -q`
1. Note that you may have to allow connections to port 53 and 443 through the 
   firewall

Note: This should reroute any queries to the servers that Android uses to check
connection status. Any such queries are rerouted to the local `scrcpy_utils`
server, which returns a 204 No Content response, which is the expected response
if a device is properly connected to the internet
Note: This needs to be implemented to handle both HTTP and HTTPS requests
