## Made in Australia
## Parser for Meshtastic filesystem on ESP32
## Requires internet connectivity initially to download protobufs, will run offline after that

# Changelog
# v0.1 - Initial concept

import argparse
from datetime import datetime
from datetime import timezone
import logging
import hashlib
import struct

# Internal modules
from modules.parseLittle import *
from modules.espressifPartitions import *
from modules.protoModule import *
from modules.protoParser import *

# ------------ Settings -------------------------------------------------------------------------

# Name for carved SPIFFS file output
spiffsFile = "spiffsCarved.bin"

__version__ = 0.1
__author__ = "facelessg00n"
__description__ = "Processes BIN files from Meshtastic devices and extracts data"


banner = """
███╗   ███╗███████╗███████╗██╗  ██╗      ███████╗██╗  ██╗████████╗██████╗  █████╗  ██████╗████████╗ ██████╗ ██████╗ 
████╗ ████║██╔════╝██╔════╝██║  ██║      ██╔════╝╚██╗██╔╝╚══██╔══╝██╔══██╗██╔══██╗██╔════╝╚══██╔══╝██╔═══██╗██╔══██╗
██╔████╔██║█████╗  ███████╗███████║█████╗█████╗   ╚███╔╝    ██║   ██████╔╝███████║██║        ██║   ██║   ██║██████╔╝
██║╚██╔╝██║██╔══╝  ╚════██║██╔══██║╚════╝██╔══╝   ██╔██╗    ██║   ██╔══██╗██╔══██║██║        ██║   ██║   ██║██╔══██╗
██║ ╚═╝ ██║███████╗███████║██║  ██║      ███████╗██╔╝ ██╗   ██║   ██║  ██║██║  ██║╚██████╗   ██║   ╚██████╔╝██║  ██║
╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝      ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝                                                                                                                                
"""

logging.basicConfig(
    filename="mesh-parser.log",
    encoding="utf-8",
    filemode="a",
    format="{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
    level=logging.INFO,
)


# TODO rework to handle other partition types


# Search for a partition with a type of 0x82 which is a SPIFFS partition
def locate_spiffs_partition(partition_table):
    for partition in partition_table:
        magic_number, partition_type, partition_subtype, offset, size, label, flags = (
            partition
        )
        # print(f"Found {partition_type,partition_subtype,offset,size,label,flags}")
        logging.info(
            f"Found partition: {partition_type,partition_subtype,offset,size,label,flags}"
        )
        if partition_subtype == 0x82:  # SPIFFS
            print(
                f"Found SPIFFS partition at {offset}, with a size of {size} , {str(label,'utf-8')}"
            )
            logging.info(f"Found SPIFFS partition at {offset}, with a size of {size}")
            return offset, size
    print("SPIFFS partition not found")
    logging.warning("Spiffs Partition not found")
    return None, None


# Read partition table from the input bin file
# Uses a struct to parse the partition table entry
def read_partition_from_bin(file_path):
    # Partition Table is stored at 0x8000 and is 0xC0 long
    table_offset = 0x8000
    table_size = 0xC0
    with open(file_path, "rb") as f:
        f.seek(table_offset)
        table_data = f.read(table_size)

    # (<) Little Endian data
    # (H) 2 Byte magic Number
    # (B) 1 Byte Partition type
    # (B) 1 Byte Partition Subtype
    # (L) 4 Byte Partition offset
    # (L) 4 Byte Partition size
    # (s) 16 Byte Label - String
    # (L) 4 bytes - Optional flags

    partition_entry_format = "<HBBLL16sL"
    partition_entry_size = struct.calcsize(partition_entry_format)

    partition_table = []
    for i in range(0, len(table_data), partition_entry_size):
        entry_data = table_data[i : i + partition_entry_size]
        if len(entry_data) < partition_entry_size:
            break
        partition_entry = struct.unpack(partition_entry_format, entry_data)
        partition_table.append(partition_entry)
    return partition_table


# Carves the SPIFFS partition and saves it to a new file in the event further analysis is required
def carve_spiffs_partition(input_file, spiffs_file_path, offset, size):
    with open(input_file, "rb") as f:
        f.seek(offset)
        spiffs_data = f.read(size)
    with open(spiffs_file_path, "wb") as spiffs_file:
        spiffs_file.write(spiffs_data)
    print(f"SPIFFS partition carved and saved to {spiffs_file_path}")
    logging.info(f"SPIFFS partition carved and saved to {spiffs_file_path}")


# Make sure we have a LittleFS filesystem and return true if found
def check_littleFS(spiffs_file_path):
    try:
        with open(spiffs_file_path, "rb") as f:
            # Offset is 8 bytes
            f.seek(8)
            header = f.read(8)
            if header == b"littlefs":
                print("LittleFS filesystem detected")
                logging.info("LittleFS file system detected")
            return True
    except Exception as e:
        print(e)


# TODO Tidy up ... dont look in here...
if __name__ == "__main__":
    print(banner)
    parser = argparse.ArgumentParser(
        description=__description__,
        epilog=f"Developed by {__author__}, version {__version__}",
    )

    parser.add_argument("-f", "--file", dest="inputFile", help="Input BIN File")
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit

    if args.inputFile:
        logging.info(banner)
        logging.info(f"Meshtastic parser version {__version__}")
        logging.info(f"input file is {args.inputFile}")
        with open(args.inputFile, "rb") as f:
            bytes = f.read()
            file_MD5_hash = hashlib.md5(bytes).hexdigest()
            logging.info(f"Input file MD5 : {file_MD5_hash}")
            print(f"MD5 Sum of file {file_MD5_hash}")

        partition_table = read_partition_from_bin(args.inputFile)
        offset, size = locate_spiffs_partition(partition_table)

        # if offset and size are returned process the file further, will return null if failed
        if offset and size:
            carve_spiffs_partition(args.inputFile, spiffsFile, offset, size)
        if check_littleFS(spiffsFile):
            print("Extracting files")
            parse_littleFS(spiffsFile)
        else:
            print("Failed to find littleFS")

        print("Commence protobuf decode stage")
        logging.info("Decoding protobufs")
        protoUnpacker()
        parseProtos()
