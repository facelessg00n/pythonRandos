# Parses the litte-fs Filesystem and extracts data
# These files will be place into an Extracts folder for further analysis

import argparse
from littlefs import LittleFS
import os
import sys

from modules.loggerConfig import *


# Defaults From walk.py example
def parse_littleFS(imageFile):
    img_filename = imageFile
    img_size = 1 * 1024 * 1024
    block_size = 4096
    read_size = 256
    prog_size = 256
    name_max = 0
    file_max = 0
    attr_max = 0

    block_count = img_size // block_size
    if block_count * block_size != img_size:
        print("image size should be a multiple of block size")
        exit(1)

    fs = LittleFS(
        block_size=block_size,
        block_count=block_count,
        read_size=read_size,
        prog_size=prog_size,
        name_max=name_max,
        file_max=file_max,
        attr_max=attr_max,
    )

    with open(imageFile, "rb") as f:
        data = f.read()
        fs.context.buffer = bytearray(data)
        fs.mount()

    for root, dirs, files in fs.walk("./prefs"):
        print(f"root{root} dirs{dirs} files{files}")
        logging.info(f"Extracting files: root{root} dirs{dirs} files{files}")

    for root, dirs, files in fs.walk("./static"):
        print(f"Static files: root{root} dirs{dirs} files{files}")
        logging.info(
            f"Extracting files: Static files: root{root} dirs{dirs} files{files}"
        )

    if len(files) > 0:
        print(len(files))
    else:
        print("No files located")
        logging.warning("No files located")

    # FIXME Tidy Folder creation
    # Create a folder for extracts
    if not os.path.exists("Extracts"):
        print("Creating folder...")
        os.mkdir("Extracts")
    else:
        print("Extracts folder exists")

    # Create subfolder for Static files
    if not os.path.exists("Extracts/Static"):
        print("Creating folder...")
        os.mkdir("Extracts/Static")
    else:
        print("Static folder exists")

    # Walk and recover files from the prefs directory
    for root, dirs, files in fs.walk("./prefs"):
        # print(files)
        for file in files:
            try:
                dataBytes = fs.open(f"./prefs/{file}", "rb").read()
                fileName = file.split(".")[0]
                with open(f"Extracts/{fileName}.proto", "wb") as file:
                    print(f"Writing {fileName}.proto")
                    file.write(dataBytes)
            except Exception as e:
                print(e)

    # Walk and recover files from the static directory
    for root, dirs, files in fs.walk("./static"):
        # print(files)
        for file in files:
            try:
                dataBytes = fs.open(f"./static/{file}", "rb").read()
                fileName = file.split(".")[0]
                fileExtension = file.split(".")[1]
                with open(f"Extracts/Static/{fileName}.{fileExtension}", "wb") as file:
                    print(f"Writing {fileName}.{fileExtension}")
                    file.write(dataBytes)
            except Exception as e:
                print(e)
