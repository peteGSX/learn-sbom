"""
Module for Arduino CLI management and interactions

This model can be used to download, install, configure, and update the Arduino CLI

This module uses threads and queues

© 2024, Peter Cole.
© 2023, Peter Cole.
All rights reserved.

This file is part of EX-Installer.

This is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

It is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with CommandStation.  If not, see <https://www.gnu.org/licenses/>.
"""

import platform
import os
import sys
import tempfile
import subprocess
import json
from threading import Thread, Lock
from collections import namedtuple
import logging
from datetime import datetime, timedelta
import shutil

from .file_manager import ThreadedDownloader, ThreadedExtractor


QueueMessage = namedtuple("QueueMessage", ["status", "topic", "data"])


@staticmethod
def get_exception(error):
    """
    Get an exception into text to add to the queue
    """
    template = "An exception of type {0} occurred. Arguments:\n{1!r}"
    message = template.format(type(error).__name__, error.args)
    return message


class ThreadedArduinoCLI(Thread):
    """
    Class to run Arduino CLI commands in a separate thread, returning results to the provided queue

    There is a default timeout of 5 minutes (300 seconds) for any thread being started, after which
    they will be terminated

    Specifying the "time_limit" parameter will override this if necessary
    """

    arduino_cli_lock = Lock()

    def __init__(self, acli_path, params, queue, time_limit=300):
        """
        Initialise the object

        Need to provide:
        - full path the Arduino CLI executable/binary
        - a list of valid parameters
        - the queue instance to update
        """
        super().__init__()

        # Set up logger
        self.log = logging.getLogger(__name__)
        self.log.debug("Start thread")

        self.params = params
        self.process_params = [acli_path]
        self.process_params += self.params
        self.queue = queue
        self.time_limit = timedelta(seconds=time_limit)

    def run(self, *args, **kwargs):
        """
        Override for Thread.run()

        Creates a thread and executes with the provided parameters

        Results are placed in the provided queue object
        """
        start_time = datetime.now()
        self.queue.put(
            QueueMessage("info", "Run Arduino CLI", f"Arduino CLI parameters: {self.params}")
        )
        self.log.debug("Queue info %s", self.params)
        with self.arduino_cli_lock:
            try:
                startupinfo = None
                if platform.system() == "Windows":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                self.process = subprocess.Popen(self.process_params, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                startupinfo=startupinfo)
                self.output, self.error = self.process.communicate()
                self.log.debug(self.process_params)
            except Exception as error:
                self.queue.put(
                    QueueMessage("error", str(error), str(error))
                )
                self.log.error("Caught exception error: %s", str(error))
            if (self.time_limit is not None and ((datetime.now() - start_time) > self.time_limit)):
                self.queue.put(
                    QueueMessage("error", "The Arduino CLI command did not complete within the timeout period",
                                 f"The running Arduino CLI command took longer than {self.time_limit}")
                )
                self.log.error(f"The running Arduino CLI command took longer than {self.time_limit}")
                self.log.error(self.params)
                self.process.terminate()
            else:
                # Returncode 0 = success, anything else is an error
                topic = ""
                data = ""
                if self.error:
                    error = json.loads(self.error.decode())
                    topic = "Error in compile or upload"
                    data = ""
                    if "error" in error:
                        topic = str(error["error"])
                        data = str(error["error"])
                    if "output" in error:
                        if "stdout" in error["output"]:
                            if error["output"]["stdout"] != "":
                                data = str(error["output"]["stdout"] + "\n")
                        if "stderr" in error["output"]:
                            if error["output"]["stderr"] != "":
                                data += str(error["output"]["stderr"])
                    if data == "":
                        data = error
                else:
                    if self.output:
                        details = json.loads(self.output.decode())
                        if "success" in details:
                            if details["success"] is True:
                                topic = "Success"
                                data = details["compiler_out"]
                            else:
                                topic = details["error"]
                                data = details["compiler_err"]
                        else:
                            topic = "Success"
                            if "stdout" in details:
                                data = details["stdout"]
                            else:
                                data = details
                    else:
                        topic = "No output"
                        data = "No output"
                if self.process.returncode == 0:
                    status = "success"
                    self.log.debug(data)
                else:
                    status = "error"
                    self.log.error(data)
                self.log.debug(f"Thread output, status: {status}\ntopic: {topic}\ndata: {data}\nparams: {self.params}")
                self.queue.put(
                    QueueMessage(status, topic, data)
                )


class ArduinoCLI:
    """
    Class for the Arduino CLI model

    This class exposes the various methods to interact with the Arduino CLI including:

    - cli_file_path() - returns the full file path to where the Arduino CLI should reside
    - is_installed() - checks the CLI is installed and executable, returns True/False
    - get_version() - gets the Arduino CLI version, returns to the provided queue
    - get_platforms() - gets the list of installed platforms
    - download_cli() - downloads the appropriate CLI for the operating system, returns the file path
    - install_cli() - extracts the CLI to the specified file path from download file path
    - delete_cli() - deletes the CLI, returns True|False
    - initialise_config() - adds additional URLs to the CLI config
    - update_index() - performs the core update-index and initial board list
    - install_package() - installs the provided packages
    - upgrade_platforms() - performs the core upgrade to ensure all are up to date
    - list_boards() - lists all connected boards, returns list of dictionaries for boards
    - compile_sketch() - compiles the sketch in the provided directory ready for upload
    - upload_sketch() - uploads the sketch in the provided directory to the provided device
    """

    # Dictionary of Arduino CLI archives for the appropriate platform
    # Currently force usage of 0.35.3 due to changes in 1.0.x output that have not been fully tested yet.
    urlbase = "https://github.com/arduino/arduino-cli/releases/download/v0.35.3/arduino-cli_0.35.3_"
    arduino_downloads = {
        "Linux64":   urlbase + "Linux_64bit.tar.gz",
        "Darwin64":  urlbase + "macOS_64bit.tar.gz",
        "Windows32": urlbase + "Windows_32bit.zip",
        "Windows64": urlbase + "Windows_64bit.zip"
    }

    """
    Expose the currently supported version of the Arduino CLI to use.
    """
    arduino_cli_version = "0.35.3"

    """
    Dictionary for the base board/platform support for the Arduino CLI.

    This should really just be Arduino AVR, and must specify the version.

    Note this used to be defined in the manage_arduino_cli module but is now centralised here.

    This format is consistent with extra_platforms, but without the URL.

    base_platforms = {
        "Platform Name": {
            "platform_id": "<packager>:<arch>",
            "version": "<version>"
        }
    }
    """
    base_platforms = {
        "Arduino AVR": {
            "platform_id": "arduino:avr",
            "version": "1.8.6"
        }
    }

    """
    Dictionary for additional board/platform support for the Arduino CLI.

    These must be tied to a specific version to avoid future unknown issues:

    extra_platforms = {
        "Platform Name": {
            "platform_id": "<packager>:<arch>",
            "version": "<version>",
            "url": "<url>"
        }
    }

    - ESP32 locked to 2.0.17 as 3.x causes compile errors for EX-CommandStation
    - STM32 locked to 2.7.1 because 2.8.0 introduces new output that needs logic to deal with
    """
    extra_platforms = {
        "Espressif ESP32": {
            "platform_id": "esp32:esp32",
            "version": "2.0.17",
            "url": "https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json"
        },
        "STMicroelectronics Nucleo/STM32": {
            "platform_id": "STMicroelectronics:stm32",
            "version": "2.7.1",
            "url": "https://github.com/stm32duino/BoardManagerFiles/raw/main/package_stmicroelectronics_index.json"
        }
    }

    """
    Dictionary of required Arduino libraries to be installed.

    These must be tied to a specific version to avoid future unknown issues:

    arduino_libraries = {
        "<library name>": "<version>"
    }

    Note that these were previously an attribute of a product in the product_details module but are now here.
    """
    arduino_libraries = {
        "Ethernet": "2.0.2"
    }

    """
    Dictionary of devices supported with EX-Installer to enable selection when detecting unknown devices.
    """
    supported_devices = {
        "Arduino Mega or Mega 2560": "arduino:avr:mega",
        "Arduino Uno": "arduino:avr:uno",
        "Arduino Nano": "arduino:avr:nano",
        "DCC-EX EX-CSB1": "esp32:esp32:esp32",
        "ESP32 Dev Kit": "esp32:esp32:esp32",
        "STMicroelectronics Nucleo F411RE": "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_F411RE",
        "STMicroelectronics Nucleo F446RE": "STMicroelectronics:stm32:Nucleo_64:pnum=NUCLEO_F446RE"
    }

    """
    Dictionary of DCC-EX specific devices, used to preselect or exclude motor driver definitions.

    While this isn't ideal, it makes it easier with the current implementation to control what users can and
    can't select for motor drivers.

    Future additions must start with "DCC-EX" in order to be used for this purpose.
    """
    dccex_devices = {
        "DCC-EX EX-CSB1": "EXCSB1"
    }

    def __init__(self, selected_device=None):
        """
        Initialise the Arduino CLI instance

        The instance retains the current list of detected devices and the current selected device (if any)
        """
        self.selected_device = selected_device
        self.detected_devices = []
        self.dccex_device = None

        # Set up logger
        self.log = logging.getLogger(__name__)

    def cli_file_path(self):
        """
        Function to get the full path and filename of the Arduino CLI.

        Cross-platform, returns the full file path or False if there is an error.

        For example:
        - Linux - /home/<user>/ex-installer/arduino-cli/arduino-cli
        - Windows - C:\\Users\\<user>\\ex-installer\\arduino-cli\\arduino-cli.exe
        """
        if not platform.system():
            raise ValueError("Unsupported operating system")
            _result = False
            self.log.debug("Unsupported operating system")
        else:
            if platform.system() == "Windows":
                _cli = "arduino-cli.exe"
            else:
                _cli = "arduino-cli"
            if os.path.expanduser("~"):
                _cli_path = os.path.join(
                    os.path.expanduser("~"),
                    "ex-installer",
                    "arduino-cli",
                    _cli
                )
                _result = _cli_path.replace("\\", "\\\\")   # Need to do this for Windows
                self.log.debug(_result)
            else:
                raise ValueError("Could not obtain user home directory")
                _result = False
                self.log.error("Could not obtain user home directory")
        return _result

    def is_installed(self, file_path):
        """
        Function to check if the Arduino CLI in installed in the provided file path

        Also checks to ensure it is executable.

        Returns True or False
        """
        if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
            _result = True
        else:
            _result = False
        self.log.debug(_result)
        return _result

    def get_version(self, file_path, queue):
        """
        Function to retrieve the version of the Arduino CLI

        If obtaining the version is successful it will be in the queue's "data" field
        """
        if self.is_installed(file_path):
            params = ["version", "--format", "jsonmini"]
            acli = ThreadedArduinoCLI(file_path, params, queue)
            acli.start()
        else:
            queue.put(
                QueueMessage("error", "Arduino CLI is not installed", "Arduino CLI is not installed")
            )
            self.log.debug("Arduino CLI not installed")

    def get_platforms(self, file_path, queue):
        """
        Function to retrieve the current platforms installed with the Arduino CLI

        If successful, the list will be in the queue's "data" field
        """
        if self.is_installed(file_path):
            params = ["core", "list", "--format", "jsonmini"]
            acli = ThreadedArduinoCLI(file_path, params, queue)
            acli.start()
        else:
            queue.put(
                QueueMessage("error", "Arduino CLI is not installed", "Arduino CLI is not installed")
            )
            self.log.debug("Arduino CLI not installed")

    def get_libraries(self, file_path, queue):
        """
        Function to retrieve the current libraries installed with the Arduino CLI

        If successful, the list will be in the queue's "data" field
        """
        if self.is_installed(file_path):
            params = ["lib", "list", "--format", "jsonmini"]
            acli = ThreadedArduinoCLI(file_path, params, queue)
            acli.start()
        else:
            queue.put(
                QueueMessage("error", "Arduino CLI is not installed", "Arduino CLI is not installed")
            )
            self.log.debug("Arduino CLI not installed")

    def download_cli(self, queue):
        """
        Download the Arduino CLI

        If successful, the archive's path will be in the queue's "data" field

        If error, the error will be in the queue's "data" field
        """
        if not platform.system():
            self.log.error("Unsupported operating system")
            queue.put(
                QueueMessage("error", "Unsupported operating system", "Unsupported operating system")
            )
        else:
            if sys.maxsize > 2**32:
                _installer = platform.system() + "64"
            else:
                _installer = platform.system() + "32"
            self.log.debug(_installer)
            if _installer in ArduinoCLI.arduino_downloads:
                _target_file = os.path.join(
                    tempfile.gettempdir(),
                    ArduinoCLI.arduino_downloads[_installer].split("/")[-1]
                )
                download = ThreadedDownloader(ArduinoCLI.arduino_downloads[_installer], _target_file, queue)
                download.start()
            else:
                self.log.error("No Arduino CLI available for this operating system")
                queue.put(
                    QueueMessage("error", "No Arduino CLI available for this operating system",
                                 "No Arduino CLI available for this operating system")
                )

    def install_cli(self, download_file, file_path, queue):
        """
        Install the Arduino CLI by extracting to the specified directory
        """
        cli_directory = os.path.dirname(file_path)
        if not os.path.exists(cli_directory):
            try:
                os.makedirs(cli_directory)
            except Exception as error:
                message = get_exception(error)
                self.log.error(message)
                queue.put(
                    QueueMessage("error", "Could not create Arduino CLI directory", message)
                )
                return
        extract = ThreadedExtractor(download_file, cli_directory, queue)
        extract.start()

    def delete_cli(self):
        """
        Deletes all files in the provided directory.

        This is required to remove an unsupported version of the Arduino CLI.
        """
        _result = False
        cli_directory = os.path.dirname(self.cli_file_path())
        if os.path.isdir(cli_directory):
            try:
                shutil.rmtree(cli_directory)
                _result = True
            except Exception as e:
                self.log.error(f"Unable to delete {cli_directory}: {e}")
        return _result

    def initialise_config(self, file_path, queue):
        """
        Initialises the Arduino CLI configuration with the provided additional boards.

        Overwrites existing configuration options.
        """
        params = ["config", "init", "--format", "jsonmini", "--overwrite"]
        if len(self.extra_platforms) > 0:
            platform_list = []
            for extra_platform in self.extra_platforms:
                platform_list.append(self.extra_platforms[extra_platform]["url"])
            _url_list = ",".join(platform_list)
            params += ["--additional-urls", _url_list]
        acli = ThreadedArduinoCLI(file_path, params, queue)
        acli.start()

    def update_index(self, file_path, queue):
        """
        Update the Arduino CLI core index
        """
        params = ["core", "update-index", "--format", "jsonmini"]
        acli = ThreadedArduinoCLI(file_path, params, queue)
        acli.start()

    def install_package(self, file_path, package, queue):
        """
        Install packages for the listed Arduino platforms
        """
        params = ["core", "install", package, "--format", "jsonmini"]
        acli = ThreadedArduinoCLI(file_path, params, queue, 600)
        acli.start()

    def upgrade_platforms(self, file_path, queue):
        """
        Upgrade Arduino CLI platforms
        """
        params = ["core", "upgrade", "--format", "jsonmini"]
        acli = ThreadedArduinoCLI(file_path, params, queue)
        acli.start()

    def install_library(self, file_path, library, queue):
        """
        Install the specified Arduino library
        """
        params = ["lib", "install", library, "--format", "jsonmini"]
        acli = ThreadedArduinoCLI(file_path, params, queue)
        acli.start()

    def list_boards(self, file_path, queue):
        """
        Returns a list of attached boards
        """
        params = ["board", "list", "--format", "jsonmini"]
        acli = ThreadedArduinoCLI(file_path, params, queue, 120)
        acli.start()

    def upload_sketch(self, file_path, fqbn, port, sketch_dir, queue):
        """
        Compiles and uploads the sketch in the specified directory to the provided board/port.
        """
        params = ["upload", "-v", "-t", "-b", fqbn, "-p", port, sketch_dir, "--format", "jsonmini"]
        if fqbn.startswith('esp32:esp32'):
            params = params + ["--board-options", "UploadSpeed=115200"]
        acli = ThreadedArduinoCLI(file_path, params, queue)
        acli.start()

    def compile_sketch(self, file_path, fqbn, sketch_dir, queue):
        """
        Compiles the sketch ready to upload
        """
        params = ["compile", "-b", fqbn, sketch_dir, "--format", "jsonmini"]
        acli = ThreadedArduinoCLI(file_path, params, queue)
        acli.start()
