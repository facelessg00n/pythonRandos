# This module imports the required protobufs and compiles them for use
# Requires an active internet connection

from git import Repo
from grpc_tools import protoc
import os
from modules.loggerConfig import *

# Get the directory where the script was called from
base_directory = os.getcwd()

# Define paths relative to the script's execution directory
protobuf_url = "https://github.com/meshtastic/protobufs.git"
local_proto_dir = os.path.join(base_directory, "Protobufs")
proto_dir = local_proto_dir
output_dir = os.path.join(base_directory, "compiled_protos")

# Ensure the Protobufs folder exists
# TODO check there is files in the Folder
if not os.path.exists(local_proto_dir):
    print("Creating Protobufs folder...")
    os.mkdir(local_proto_dir)
    print(f"Cloning {protobuf_url}")
    try:
        repo = Repo.clone_from(protobuf_url, local_proto_dir)
    except Exception as e:
        print(
            f"Unable to download Git Repo: {e}. If your machine is offline, you will need to manually download the files."
        )
        logging.warning(
            (
                f"Unable to download Git Repo: {e}. If your machine is offline, you will need to manually download the files."
            )
        )
else:
    print(f"{local_proto_dir} - folder exists... skipping download")


def compile_all_protos(proto_dir, output_dir):
    protobuf_include = os.path.join(os.path.dirname(protoc.__file__), "_proto")
    os.makedirs(output_dir, exist_ok=True)

    # Collect all .proto files up to two levels deep
    proto_files = []
    for root, dirs, files in os.walk(proto_dir):
        # Check the depth of the directory (relative to proto_dir)
        depth = root[len(proto_dir) :].count(os.sep)
        if depth < 2:  # Limit search to 2 levels deep
            proto_files.extend(
                os.path.join(root, f) for f in files if f.endswith(".proto")
            )
    if not proto_files:
        raise FileNotFoundError(f"No .proto files found in directory: {proto_dir}")
        logging.warning(f"No .proto files found in directory: {proto_dir}")

    compiled_modules = []

    for proto_file in proto_files:
        try:
            proto_file_name = os.path.relpath(
                proto_file, proto_dir
            )  # Use relative path for protoc
            # Commands for protoc compiling
            protoc_command = [
                "grpc_tools.protoc",
                f"--proto_path={proto_dir}",  # Include the directory containing the .proto files
                f"--proto_path={protobuf_include}",  # Include built-in Protobuf definitions
                f"--python_out={output_dir}",
                f"--grpc_python_out={output_dir}",
                proto_file_name,  # Relative path to the .proto file
            ]

            print(f"Compiling {proto_file_name}...")
            if protoc.main(protoc_command) != 0:
                raise RuntimeError(f"Failed to compile {proto_file_name}")

            module_name = (
                os.path.splitext(proto_file_name)[0].replace(os.sep, "_") + "_pb2"
            )
            compiled_modules.append(os.path.join(output_dir, module_name + ".py"))
        except Exception as e:
            print(f"Failed to compile {proto_file}: {e}")
            pass

    return compiled_modules


def protoUnpacker():
    try:
        compiled_files = compile_all_protos(proto_dir, output_dir)
        print("Compiled the following files:")
        for compiled_file in compiled_files:
            print(compiled_file)
            logging.info(f"Compiled {file}")
    except Exception as e:
        print(f"Error: {e}")
        pass
