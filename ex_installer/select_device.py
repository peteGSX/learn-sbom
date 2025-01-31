"""
Module for the Select Device page view

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

# Import Python modules
import customtkinter as ctk
import logging
import serial.tools.list_ports
import platform

# Import local modules
from .common_widgets import WindowLayout, CreateToolTip
from . import images


class SelectDevice(WindowLayout):
    """
    Class for the Select Device view
    """

    # Define text to use in labels
    instruction_text = ("Ensure your Arduino device is connected to your computer's USB port.\n\n" +
                        "If the device detected matches multiple devices, select the correct one from the pulldown " +
                        "list provided.\n\n" +
                        "If you have a generic or clone device, it likely appears as “Unknown”. In this instance, " +
                        "you will need to select the appropriate device from the pulldown list provided.")

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Set up logger
        self.log = logging.getLogger(__name__)
        self.log.debug("Start view")

        # Set up event handlers
        event_callbacks = {
            "<<List_Devices>>": self.list_devices
        }
        for sequence, callback in event_callbacks.items():
            self.bind_class("bind_events", sequence, callback)
        new_tags = self.bindtags() + ("bind_events",)
        self.bindtags(new_tags)

        # Start with an empty device list
        self.acli.detected_devices = []

        # Set up title
        self.set_title_logo(images.EX_INSTALLER_LOGO)
        self.set_title_text("Select your device")

        # Set up next/back buttons
        self.next_back.set_back_text("Manage Arduino CLI")
        self.next_back.set_back_command(lambda view="manage_arduino_cli": parent.switch_view(view))
        self.next_back.set_next_text("Select product to install")
        self.next_back.set_next_command(lambda view="select_product": parent.switch_view(view))
        self.next_back.hide_monitor_button()

        # Set up and configure container frame
        self.select_device_frame = ctk.CTkFrame(self.main_frame, height=360)
        self.select_device_frame.grid(column=0, row=0, sticky="nsew", ipadx=5, ipady=5)
        self.select_device_frame.grid_columnconfigure(0, weight=1)
        self.select_device_frame.grid_rowconfigure((0, 1, 2), weight=1)

        # Create instruction label
        self.instruction_label = ctk.CTkLabel(self.select_device_frame,
                                              text=self.instruction_text,
                                              font=self.instruction_font,
                                              wraplength=780)

        # Create list device button
        self.list_device_button = ctk.CTkButton(self.select_device_frame, width=200, height=50,
                                                text=None, font=self.action_button_font,
                                                command=lambda event="list_devices": self.list_devices(event))

        # Create device list container frame and variable
        self.device_list_frame = ctk.CTkFrame(self.select_device_frame,
                                              border_width=2,
                                              fg_color="#E5E5E5")
        self.device_list_frame.grid_columnconfigure((0, 1), weight=1)
        self.device_list_frame.grid_rowconfigure(0, weight=1)
        self.selected_device = ctk.IntVar(self, value=-1)

        # Create detected device label and grid
        grid_options = {"padx": 5, "pady": 5}
        self.no_device_label = ctk.CTkLabel(self.select_device_frame, text="Scanning for devices",
                                            font=self.bold_instruction_font)
        self.device_list_label = ctk.CTkLabel(self.device_list_frame, text="Select your device",
                                              font=self.instruction_font)
        self.device_list_label.grid(column=0, row=0, columnspan=2, **grid_options)

        # Tooltips
        no_device_tip = ("The Arduino CLI was unable to detect any valid devices connected to your computer. " +
                         "This could be due to it not being connected properly, a faulty device or USB cable, " +
                         "or not having the correct drivers installed for Windows. Refer to our documentation " +
                         "for help by clicking this window.")
        CreateToolTip(self.no_device_label, no_device_tip, "https://dcc-ex.com/support/index.html")

        # Layout window
        self.instruction_label.grid(column=0, row=0)
        self.no_device_label.grid(column=0, row=1)
        self.device_list_frame.grid(column=0, row=1, ipadx=5, ipady=5)
        self.list_device_button.grid(column=0, row=2)

        self.set_state()
        self.list_devices("list_devices")

    def set_state(self):
        self.next_back.hide_log_button()
        if len(self.acli.detected_devices) == 0:
            self.list_device_button.configure(text="Scan for Devices")
            self.no_device_label.grid()
            self.device_list_frame.grid_remove()
            self.log.debug("No devices detected")
        else:
            self.list_device_button.configure(text="Refresh Device List")
            self.no_device_label.grid_remove()
            self.device_list_frame.grid()
        if not self.acli.selected_device:
            self.next_back.disable_next()
        else:
            self.next_back.enable_next()

    def list_devices(self, event):
        """
        Use the Arduino CLI to list attached devices
        """
        multi_device_tip = ("The Arduino CLI has recognised that there are multiple options that match " +
                            "the device you have plugged in. Please select the correct device from the list " +
                            "provided.")
        unknown_device_tip = ("The Arduino CLI has detected a device but is unable to determine the correct type. " +
                              "This commonly occurs with clone devices using generic USB to serial converters, but " +
                              "will also occur with ESP32 and STM32 Nucleo devices as they do not use genuine " +
                              "Arduino device drivers. We have displayed as much information as possible from the " +
                              "operating system to help you select the correct port your device is attached to.")
        if event == "list_devices":
            self.log.debug("List devices button clicked")
            self.acli.detected_devices.clear()
            self.acli.selected_device = None
            for widget in self.device_list_frame.winfo_children():
                widget.destroy()
            self.process_start("refresh_list", "Scanning for attached devices", "List_Devices")
            self.acli.list_boards(self.acli.cli_file_path(), self.queue)
        elif self.process_phase == "refresh_list":
            if self.process_status == "success":
                # Arduino CLI 1.0.0 adds the list as a value to a dict, need to reset that to just a list
                if len(self.process_data) > 0 and "detected_ports" in self.process_data:
                    if isinstance(self.process_data["detected_ports"], list):
                        self.process_data = self.process_data["detected_ports"]
                # If no boards found, but fake enabled, add a dummy discovered port
                elif len(self.process_data) == 0 and self.parent.fake is True:
                    if platform.system() == "Windows":
                        fake_port = "COM10"
                    else:
                        fake_port = "/dev/ttyUSB10"
                    fake_data = [{'port': {'address': fake_port, 'label': fake_port, 'protocol': 'serial',
                                  'protocol_label': 'Serial Port (USB)'}}]
                    self.process_data = fake_data
                if isinstance(self.process_data, list) and len(self.process_data) > 0:
                    supported_boards = []
                    for board in self.acli.supported_devices:
                        supported_boards.append(board)
                    grid_options = {"padx": 5, "pady": 5}
                    for board in self.process_data:
                        matching_board_list = []
                        port = board["port"]["address"]
                        self.log.debug("Device on %s found: %s", port, board)
                        if "matching_boards" in board:
                            for match in board["matching_boards"]:
                                name = match["name"]
                                fqbn = match["fqbn"]
                                matching_board_list.append({"name": name, "fqbn": fqbn})
                            self.log.debug("Matches: %s", matching_board_list)
                        else:
                            matching_board_list.append({"name": "Unknown", "fqbn": "unknown"})
                            self.log.debug("Device unknown")
                        self.acli.detected_devices.append({"port": port, "matching_boards": matching_board_list})
                        self.log.debug("Found device list")
                        self.log.debug(self.acli.detected_devices)
                    for index, item in enumerate(self.acli.detected_devices):
                        text = None
                        tip = None
                        row = index + 1
                        self.device_list_frame.grid_rowconfigure(row, weight=1)
                        self.log.debug("Process %s at index %s", item, index)
                        if len(self.acli.detected_devices[index]["matching_boards"]) > 1:
                            matched_boards = []
                            for matched_board in self.acli.detected_devices[index]["matching_boards"]:
                                matched_boards.append(matched_board["name"])
                            multi_combo = ctk.CTkComboBox(self.device_list_frame,
                                                          values="Select the correct device", width=250,
                                                          command=lambda name, i=index: self.update_board(name, i))
                            multi_combo.grid(column=1, row=row, sticky="e", **grid_options)
                            multi_combo.configure(values=matched_boards)
                            text = "Multiple matches detected"
                            text += " on " + self.acli.detected_devices[index]["port"]
                            tip = multi_device_tip
                            self.log.debug("Multiple matched devices on %s", self.acli.detected_devices[index]["port"])
                            self.log.debug(self.acli.detected_devices[index]["matching_boards"])
                        elif self.acli.detected_devices[index]["matching_boards"][0]["name"] == "Unknown":
                            unknown_combo = ctk.CTkComboBox(self.device_list_frame,
                                                            values=["Select the correct device"], width=250,
                                                            command=lambda name, i=index: self.update_board(name, i))
                            unknown_combo.grid(column=1, row=row, sticky="e", **grid_options)
                            unknown_combo.configure(values=supported_boards)
                            port_description = self.get_port_description(self.acli.detected_devices[index]["port"])
                            if port_description:
                                text = f"Unknown/clone detected as {port_description}"
                            else:
                                text = ("Unknown or clone device detected on " +
                                        self.acli.detected_devices[index]['port'])
                            tip = unknown_device_tip
                            self.log.debug("Unknown or clone device on %s", self.acli.detected_devices[index]["port"])
                        else:
                            text = self.acli.detected_devices[index]["matching_boards"][0]["name"]
                            text += " on " + self.acli.detected_devices[index]["port"]
                            self.log.debug("%s on %s", self.acli.detected_devices[index]["matching_boards"][0]["name"],
                                           self.acli.detected_devices[index]["port"])
                            self.select_device()
                        radio_button = ctk.CTkRadioButton(self.device_list_frame, text=text,
                                                          variable=self.selected_device, value=index,
                                                          command=self.select_device)
                        if tip is not None:
                            CreateToolTip(radio_button, tip)
                        radio_button.grid(column=0, row=row, sticky="w", **grid_options)
                else:
                    self.no_device_label.configure(text="No devices found")
                self.set_state()
                self.process_stop()
            elif self.process_status == "error":
                self.process_error(self.process_topic)

    def update_board(self, name, index):
        if name != "Select the correct device":
            if name.startswith("DCC-EX"):
                if name in self.acli.dccex_devices:
                    self.acli.dccex_device = self.acli.dccex_devices[name]
                else:
                    self.acli.dccex_device = None
            else:
                self.acli.dccex_device = None
            self.acli.detected_devices[index]["matching_boards"][0]["name"] = name
            self.acli.detected_devices[index]["matching_boards"][0]["fqbn"] = self.acli.supported_devices[name]
            self.selected_device.set(index)
            self.select_device()

    def select_device(self):
        self.acli.selected_device = None
        device = self.selected_device.get()
        if (
            self.acli.detected_devices[device]["matching_boards"][0]["name"] != "Unknown" and
            self.acli.detected_devices[device]["matching_boards"][0]["name"] != "Select the correct device"
        ):
            self.acli.selected_device = device
            self.next_back.enable_next()
            self.log.debug("Selected %s on port %s",
                           self.acli.detected_devices[self.acli.selected_device]["matching_boards"][0]["name"],
                           self.acli.detected_devices[self.acli.selected_device]["port"])
            self.next_back.show_monitor_button()
        else:
            self.next_back.disable_next()
            self.next_back.hide_monitor_button()

    def get_port_description(self, unknown_port):
        """
        Function to obtain USB/serial port descriptions using pyserial for ports the CLI doesn't identify
        """
        description = False
        port_list = serial.tools.list_ports.comports()
        if isinstance(port_list, list):
            for port in port_list:
                if port.device == unknown_port:
                    if port.product is not None:
                        description = f" {port.product} ({port.device})"
                    else:
                        description = port.description
                    break
        return description
