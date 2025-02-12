# Compile protobufs and parse data
# Outputs data in JSON and HTML formats
# HTML functionality needs some rework


import base64
import importlib.util
from google.protobuf import text_format
from google.protobuf.message import DecodeError
from google.protobuf.json_format import MessageToJson
import json
import html
import logging
import os
import sys
import shutil

from modules.loggerConfig import *

# ------------ Settings -------------------------------------------------------------------------

base_directory = os.getcwd()

# Define reports folder and check it exists
reports_folder = os.path.join(base_directory, "Reports")
os.makedirs(reports_folder, exist_ok=True)

# ------------ Functions -------------------------------------------------------------------------

# Copy the stylesheet into the reports folder so they are displayed correctly
def move_stylesheet_to_reports():
    source_path = os.path.join("modules", "styles.css")
    destination_path = os.path.join("Reports", "styles.css")
    try:
        shutil.copy(source_path, destination_path)
        print(f"Stylesheet moved to: {destination_path}")
    except FileNotFoundError:
        print("Error: 'styles.css' not found in the 'modules' folder.")


move_stylesheet_to_reports()

# Load protobuf modules to they can be used to decode data
def load_all_protobuf_modules(folder_path):
    protobuf_modules = {}

    if folder_path not in sys.path:
        sys.path.append(folder_path)

    # Check folders due to the way the protos are packaged
    for root, dirs, files in os.walk(folder_path):
        depth = root[len(folder_path) :].count(os.sep)
        # Go 2 folders deep
        if depth < 2:
            for filename in files:
                if filename.endswith("_pb2.py"):  # Identify compiled Protobuf modules
                    module_name = os.path.splitext(filename)[0]
                    module_path = os.path.join(root, filename)
                    spec = importlib.util.spec_from_file_location(
                        module_name, module_path
                    )
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    protobuf_modules[module_name] = module

    return protobuf_modules


def convert_protobuf_to_json(proto_message):
    return MessageToJson(proto_message, preserving_proto_field_name=True)


# Decodes data from the nanopb.proto files, they must be read in as bytes
def decode_nanopb_file(proto_file_path, protobuf_module, message_class_name):
    message_class = getattr(protobuf_module, message_class_name, None)
    if not message_class:
        raise AttributeError(
            f"Message class '{message_class_name}' not found in the module."
        )
    with open(proto_file_path, "rb") as f:
        file_content = f.read()
    message = message_class()
    message.ParseFromString(file_content)  # nanopb uses ParseFromString for binary data
    return message

# ------      Helper functions for data conversion 
def base64_to_ascii(base64_string):
    try:
        decoded_bytes = base64.b64decode(base64_string)
        return decoded_bytes.decode(
            "ascii", errors="ignore"
        )  # Convert to ASCII ignoring errors
    except Exception as e:
        return f"Error decoding base64: {str(e)}"


def base64_to_plaintext(base64_string):
    try:
        decoded_bytes = base64.b64decode(base64_string)
        return decoded_bytes.decode("ascii", errors="ignore")  # Convert to ASCII
    except Exception as e:
        return f"Error decoding base64 to plaintext: {str(e)}"

# -------- Report Generation ---------------------------------------------------------

# Generates an HTML report for module data, handling additional modules dynamically.
def generate_modules_html(json_data):

    html_output = """
    <html>
    <head>
        <link rel="stylesheet" type="text/css" href="styles.css">
    </head>
    <body>
        <h1>Module Configuration Report</h1>
    """

    def recursive_html(data, parent_key=None):
        nonlocal html_output
        if isinstance(data, dict):
            # Create a new table for this level
            html_output += f'<table class="device-table"><thead><tr><th colspan="2">{parent_key if parent_key else "Details"}</th></tr></thead><tbody>'
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    # For nested objects or lists, recursively call recursive_html
                    html_output += f'<tr><td>{key}</td><td><button class="collapsible">Expand</button><div class="content">'
                    recursive_html(value, key)  # Recursively process nested data
                    html_output += "</div></td></tr>"
                else:
                    # Add the key-value pair directly
                    html_output += f"<tr><td>{key}</td><td>{value}</td></tr>"
            html_output += "</tbody></table>"
        elif isinstance(data, list):
            # Create a new table for the list
            html_output += f'<table class="device-table"><thead><tr><th colspan="2">List</th></tr></thead><tbody>'
            for item in data:
                html_output += f"<tr><td>List Item</td><td>"
                recursive_html(item)  # For list items, no key is needed
                html_output += "</td></tr>"
            html_output += "</tbody></table>"
        else:
            # For base data (strings, numbers), just show it
            html_output += f"<tr><td>{parent_key}</td><td>{data}</td></tr>"

    # Start recursive processing
    recursive_html(json_data)

    html_output += """
    </body>
    </html>
    """
    return html_output


def generate_channel_HTML(json_data):
    html_output = """
    <html>
    <head>
        <link rel="stylesheet" type="text/css" href="styles.css">
    </head>
    <body>
        <div class="header">Decoded Channel File Data</div>
        <table>
            <tr>
                <th>Field</th>
                <th>Value</th>
            </tr>"""

    for channel in json_data.get("channels", []):
        html_output += "<tr><td colspan='2' class='channel'>Channel</td></tr>"
        for field, value in channel.items():
            # Handle PSK fields
            if field == "settings":
                html_output += (
                    "<tr><td colspan='2' class='subheader'>Settings</td></tr>"
                )
                for setting_field, setting_value in value.items():
                    # Ese value directly due to possibility of escape characters
                    setting_value = html.escape(str(setting_value))
                    html_output += (
                        f"<tr><td>{setting_field}</td><td>{setting_value}</td></tr>"
                    )
            else:
                if field == "psk" and isinstance(value, str):
                    # Use value directly due to possibility of escape characters
                    value = html.escape(value)
                html_output += f"<tr><td>{field}</td><td>{value}</td></tr>"

    # Add the remaining fields in the JSON data (e.g., version)
    for field, value in json_data.items():
        if field != "channels":  # Avoid duplicating the channels section
            html_output += f"<tr><td>{field}</td><td>{value}</td></tr>"
    html_output += "</table></body></html>"
    return html_output


def generate_dbData_tables_html(json_data):

    html_output = """
    <html>
    <head>
        <link rel="stylesheet" type="text/css" href="styles.css">
    </head>
    <body>
        <h1>Decoded Data from db.pro</h1>
    """

    def recursive_html(data, parent_key=None):
        nonlocal html_output
        if isinstance(data, dict):
            # Create a new table for this level
            html_output += f'<table class="device-table"><thead><tr><th colspan="2">{parent_key}</th></tr></thead><tbody>'
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    # For nested objects or lists, recursively call recursive_html
                    html_output += f'<tr><td>{key}</td><td><button class="collapsible">Expand</button><div class="content">'
                    recursive_html(value, key)  # Recursively process nested data
                    html_output += "</div></td></tr>"
                else:
                    # For base64 fields like 'macaddr', convert from base64
                    if key == "macaddr" and isinstance(value, str):
                        value = base64_to_plaintext(
                            value
                        )  # Convert base64 to plaintext
                    html_output += f"<tr><td>{key}</td><td>{value}</td></tr>"
            html_output += "</tbody></table>"
        elif isinstance(data, list):
            # Create a new table for the list
            html_output += f'<table class="device-table"><thead><tr><th colspan="2">List</th></tr></thead><tbody>'
            for item in data:
                html_output += f"<tr><td>List Item</td><td>"
                recursive_html(item)  # For list items, no key is needed
                html_output += "</td></tr>"
            html_output += "</tbody></table>"
        else:
            # For base data (strings, numbers), just show it
            html_output += f"<tr><td>{parent_key}</td><td>{data}</td></tr>"

    # Start recursive processing
    recursive_html(json_data)

    html_output += """
    </body>
    </html>
    """
    return html_output


def generate_device_config_html(json_data):
    html_output = """
    <html>
    <head>
        <link rel="stylesheet" type="text/css" href="styles.css">
    </head>
    <body>
        <h1>Device Configuration Report</h1>
    """

    def recursive_html(data, parent_key=None):
        nonlocal html_output
        if isinstance(data, dict):
            # Create a new table for this level
            html_output += f'<table class="device-table"><thead><tr><th colspan="2">{parent_key if parent_key else "Details"}</th></tr></thead><tbody>'
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    # For nested objects or lists, recursively call recursive_html
                    html_output += f'<tr><td>{key}</td><td><button class="collapsible">Expand</button><div class="content">'
                    recursive_html(value, key)  # Recursively process nested data
                    html_output += "</div></td></tr>"
                else:
                    # Add the key-value pair directly
                    html_output += f"<tr><td>{key}</td><td>{value}</td></tr>"
            html_output += "</tbody></table>"
        elif isinstance(data, list):
            # Create a new table for the list
            html_output += f'<table class="device-table"><thead><tr><th colspan="2">List</th></tr></thead><tbody>'
            for item in data:
                html_output += f"<tr><td>List Item</td><td>"
                recursive_html(item)  # For list items, no key is needed
                html_output += "</td></tr>"
            html_output += "</tbody></table>"
        else:
            # For base data (strings, numbers), just show it
            html_output += f"<tr><td>{parent_key}</td><td>{data}</td></tr>"

    # Start recursive processing
    recursive_html(json_data)

    html_output += """
    </body>
    </html>
    """
    return html_output


def write_html_to_file(html_content, output_filename):
    # Define the full path for the HTML file inside the 'Reports' folder
    output_filepath = os.path.join("Reports", output_filename)

    with open(output_filepath, "w") as file:
        file.write(html_content)
    print(f"HTML output written to {output_filepath}")
    logging.info(f"HTML output written to {output_filepath}")


def parseProtos():
    compiledProtos = "./compiled_protos"  # Directory where compiled files are saved

    db_proto_file_path = "./Extracts/db.proto"

    dbProtoJSON = "dbPROTO.json"
    dbProtoHTML = "dbHTML.html"

    channel_proto_file_path = "./Extracts/channels.proto"
    channelProtoJSON = "channelPROTO.json"
    channelProtoHTML = "channelPROTO.html"

    config_proto_file_path = "./Extracts/config.proto"
    configProtoJSON = "configPROTO.json"
    configProtoHTML = "configPROTO.html"

    module_proto_file_path = "./Extracts/module.proto"
    moduleProtoJSON = "modulePROTO.json"
    moduleProtoHTML = "modulePROTO.html"

    try:
        # Load all compiled Protobuf modules
        protobuf_modules = load_all_protobuf_modules(compiledProtos)
        print("Loaded the following Protobuf modules:")
        logging.info("Loaded the following Protobuf modules:")
        for module_name, module in protobuf_modules.items():
            print(f"- {module_name}: {module}")
            logging.info(f"- {module_name}: {module}")

        # Decode a specific Protobuf file using a class from the loaded module
        if "deviceonly_pb2" in protobuf_modules:
            deviceonly_pb2 = protobuf_modules["deviceonly_pb2"]
            # Decode the 'ChannelFile' message class from the binary file

            ## Parse db.proto file and output to HTML
            decoded_message = decode_nanopb_file(
                db_proto_file_path, deviceonly_pb2, "DeviceState"
            )
            # print(f"Decoded 'ChannelFile' message: {decoded_message}")
            if decoded_message:
                json_output = convert_protobuf_to_json(decoded_message)
                # Write the JSON to the 'Reports' folder
                with open(os.path.join("Reports", dbProtoJSON), "w") as json_file:
                    json_file.write(json_output)
                json_data = json.loads(json_output)
                html_output = generate_dbData_tables_html(json_data)
                write_html_to_file(html_output, dbProtoHTML)

            # Parse channel.proto file and output to HTML
            decoded_message = decode_nanopb_file(
                channel_proto_file_path, deviceonly_pb2, "ChannelFile"
            )
            # print(f"Decoded 'ChannelFile' message: {decoded_message}")
            if decoded_message:
                # Convert the Protobuf message to JSON
                json_output = convert_protobuf_to_json(decoded_message)

                # Write the JSON to the 'Reports' folder
                with open(os.path.join("Reports", channelProtoJSON), "w") as json_file:
                    json_file.write(json_output)

                # Convert the JSON to HTML
                json_data = json.loads(json_output)
                html_output = generate_channel_HTML(json_data)

                # Write the HTML to the 'Reports' folder
                write_html_to_file(html_output, channelProtoHTML)

            # Parse the local config data
            localonly_pb2 = protobuf_modules["localonly_pb2"]
            decoded_message = decode_nanopb_file(
                config_proto_file_path, localonly_pb2, "LocalConfig"
            )

            if decoded_message:
                # Convert the Protobuf message to JSON
                json_output = convert_protobuf_to_json(decoded_message)

                # Write the JSON to a file
                with open(os.path.join("Reports", configProtoJSON), "w") as json_file:
                    json_file.write(json_output)

                # Convert the JSON to HTML
                json_data = json.loads(json_output)
                html_output = generate_device_config_html(json_data)
                # print(f"HTML output:\n{html_output}")

                # Write the HTML to a file
                write_html_to_file(html_output, configProtoHTML)

            # Parse the module config data which will show installed modules
            module_config_pb2 = protobuf_modules["module_config_pb2"]

            decoded_message = decode_nanopb_file(
                module_proto_file_path, module_config_pb2, "ModuleConfig"
            )
            # print(f"Decoded 'Module' message: {decoded_message}")
            if decoded_message:
                # Convert the Protobuf message to JSON
                json_output = convert_protobuf_to_json(decoded_message)
                # print(f"JSON output:\n{json_output}")

                # Write the JSON to a file
                with open(os.path.join("Reports", moduleProtoJSON), "w") as json_file:
                    json_file.write(json_output)

                # Convert the JSON to HTML
                json_data = json.loads(json_output)
                html_output = generate_device_config_html(json_data)

                # Write the HTML to a file
                write_html_to_file(html_output, moduleProtoHTML)
        else:
            print("Failed to decode the file with any available message classes. Check for internet connectivity and ensure protobufs have been downloaded")
            print("If this error persists, delete the Protobufs folder and start again, this will force a new download")
            logging.warning("Failed to decode the file with any available message classes. Check for internet connectivity and make sure protobufs have been downloaded")

    except Exception as e:
        print(f"Error: {e}")
