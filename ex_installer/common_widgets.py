"""
Module to define widgets used across the application

Every view should include this module and base the layout on WindowLayout

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
from PIL import Image
from queue import Queue
import logging
import platform
import os
import subprocess
import webbrowser

# Import local modules
from . import images
from .serial_monitor import SerialMonitor
from .common_fonts import CommonFonts


class WindowLayout(ctk.CTkFrame):
    """
    Class to define the window layout used throughout the application.

    All views must inherit from this.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Set up logger
        self.log = logging.getLogger(__name__)
        self.log.debug("Start view")

        # Get parent Arduino CLI and Git client instances
        self.acli = parent.acli
        self.git = parent.git

        # Set up fonts
        self.common_fonts = CommonFonts(self)

        # Get application version
        self.app_version = parent.app_version

        # Set parent
        self.parent = parent

        # Product version variables
        self.product_version_name = None
        self.product_major_version = None
        self.product_minor_version = None
        self.product_patch_version = None

        # Variables for process and queue monitoring
        self.process_phase = None
        self.process_status = None
        self.process_topic = None
        self.process_data = None

        # Flag as to whether a process is in progress or not, used to disable/restore input states
        self.process_running = False

        # Set up queue for process monitoring
        self.queue = Queue()

        # Variable for storing widget states while processes run
        self.widget_states = []

        # Define fonts
        self.instruction_font = self.common_fonts.instruction_font
        self.bold_instruction_font = self.common_fonts.bold_instruction_font
        self.italic_instruction_font = self.common_fonts.italic_instruction_font
        self.large_bold_instruction_font = self.common_fonts.large_bold_instruction_font
        self.small_italic_instruction_font = self.common_fonts.small_italic_instruction_font
        self.title_font = self.common_fonts.title_font
        self.heading_font = self.common_fonts.heading_font
        self.button_font = self.common_fonts.button_font
        self.action_button_font = self.common_fonts.action_button_font

        # Define top level frames
        self.title_frame = ctk.CTkFrame(self, width=790, height=80)
        self.main_frame = ctk.CTkFrame(self, width=790, height=450)
        self.status_frame = ctk.CTkFrame(self, width=790, height=50)

        # Configure column/row weights for nice resizing
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1, minsize=450)
        self.grid_rowconfigure(2, weight=1)

        # Layout view
        self.title_frame.grid(column=0, row=0, padx=5, pady=2, sticky="nsew")
        self.main_frame.grid(column=0, row=1, padx=5, pady=2, sticky="nsew")
        self.status_frame.grid(column=0, row=2, padx=5, pady=2, sticky="nsew")

        # Setup frame weights
        self.title_frame.grid_columnconfigure(0, weight=1)
        self.title_frame.grid_columnconfigure(1, weight=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_frame.grid_rowconfigure((0, 1), weight=1)

        # Setup title frame
        self.title_logo_label = ctk.CTkLabel(self.title_frame, text=None)
        self.title_logo_label.grid(column=0, row=0, padx=5, pady=5, sticky="w")
        self.title_label = ctk.CTkLabel(self.title_frame, text=None, font=self.title_font)
        self.title_label.grid(column=1, row=0, padx=5, pady=5, sticky="w")

        # Setup next/back frame
        self.next_back = NextBack(self.main_frame, height=40,
                                  fg_color="#00353D", border_width=0)
        self.next_back.grid(column=0, row=1, sticky="sew")

        # Setup status frame and widgets
        self.status_label = ctk.CTkLabel(self.status_frame, text="Idle",
                                         font=self.instruction_font, wraplength=780)
        self.progress_bar = ctk.CTkProgressBar(self.status_frame, width=780, height=20,
                                               mode="indeterminate", orientation="horizontal")

        # Layout status frame
        self.status_label.grid(column=0, row=0, padx=5, pady=5)
        self.progress_bar.grid(column=0, row=1, padx=5, pady=5)
        self.process_stop()

    def set_title_logo(self, logo):
        """
        Function to update the title logo

        Call and pass a logo as defined in the images module
        """
        self.title_logo = Image.open(logo)
        self.title_image = ctk.CTkImage(light_image=self.title_logo, size=(200, 40))
        self.title_logo_label.configure(image=self.title_image)

    def set_title_text(self, text):
        """
        Function to update the title text
        """
        self.title_label.configure(text=text)

    def monitor_queue(self, queue, event):
        """
        Monitor the provided queue for status updates
        """
        while not queue.empty():
            item = queue.get()
            if item.status == "success" or item.status == "error":
                self.process_status = item.status
                self.process_topic = item.topic
                self.process_data = item.data
                self.event_generate(f"<<{event}>>")
                return
        self.after(100, self.monitor_queue, queue, event)

    def process_start(self, next_phase, activity, event):
        """
        Starts a background process that requires monitoring and a progress bar.

        If this is a new process, we must record and disable the current input states.
        """
        if not self.process_running:
            self.disable_input_states(self)
            self.process_running = True
        self.process_phase = next_phase
        self.status_label.configure(text=activity, text_color="#00353D")
        self.monitor_queue(self.queue, event)
        self.progress_bar.start()

    def process_stop(self):
        """
        Stops the progress bar and resets status text.

        We must restore the previously recorded input states.
        """
        if self.process_running:
            self.restore_input_states()
            self.process_running = False
        self.log.debug("process_stop()")
        self.progress_bar.stop()
        self.status_label.configure(text="Idle", text_color="#00353D")
        self.process_phase = None

    def process_error(self, message):
        """
        Stops the progress bar, sets status text, and makes font red.

        We must restore the previously recorded input states.
        """
        if self.process_running:
            self.restore_input_states()
            self.process_running = False
        self.progress_bar.stop()
        self.status_label.configure(text=message, text_color="red")
        self.process_phase = None
        self.next_back.show_log_button()

    def disable_input_states(self, widget):
        """
        Stores current state of all child input widgets then sets to disabled
        """
        children = widget.winfo_children()
        for child in children:
            if isinstance(child, (ctk.CTkButton, ctk.CTkComboBox, ctk.CTkCheckBox, ctk.CTkEntry,
                                  ctk.CTkRadioButton, ctk.CTkSwitch)):
                widget_state = {
                    "widget": child,
                    "state": child.cget("state")
                }
                self.widget_states.append(widget_state)
                child.configure(state="disabled")
            self.disable_input_states(child)

    def restore_input_states(self):
        """
        Restores the state of all widgets
        """
        for widget in self.widget_states:
            widget["widget"].configure(state=widget["state"])

    @staticmethod
    def get_exception(error):
        """
        Get an exception into text to add to the queue
        """
        template = "An exception of type {0} occurred. Arguments:\n{1!r}"
        message = template.format(type(error).__name__, error.args)
        return message


class NextBack(ctk.CTkFrame):
    """
    Class for defining and managing the next and back buttons
    """
    def __init__(self, parent, *args, **kwargs):
        """
        Create the next/back button frame with buttons
        """
        super().__init__(parent, *args, **kwargs)

        # Set up logger
        self.log = logging.getLogger(__name__)

        self.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        # Set up fonts
        self.common_fonts = CommonFonts(self)

        button_font = self.common_fonts.button_font
        button_options = {"width": 220, "height": 30, "font": button_font}

        self.back_arrow = Image.open(images.BACK_ARROW)
        self.back_arrow_image = ctk.CTkImage(light_image=self.back_arrow, size=(15, 15))
        self.back_button = ctk.CTkButton(self, image=self.back_arrow_image,
                                         text="Back", compound="left",
                                         anchor="w",
                                         **button_options)

        self.next_arrow = Image.open(images.NEXT_ARROW)
        self.next_arrow_image = ctk.CTkImage(light_image=self.next_arrow, size=(15, 15))
        self.next_button = ctk.CTkButton(self, image=self.next_arrow_image,
                                         text="Next", compound="right",
                                         anchor="e",
                                         **button_options)

        self.log_button = ctk.CTkButton(self, text="Show Log", width=100, height=30, font=button_font,
                                        command=self.show_log)

        self.back_button.grid(column=0, row=0, padx=3, pady=3, sticky="w")
        self.log_button.grid(column=2, row=0)
        self.next_button.grid(column=4, row=0, padx=3, pady=3, sticky="e")

        self.monitor_window = None
        self.monitor_button = ctk.CTkButton(self, text="View device monitor", command=self.monitor,
                                            width=150, height=30, font=button_font)
        self.monitor_button.grid(column=2, row=0)

    def set_back_text(self, text):
        """Update back button text"""
        self.back_button.configure(text=text)

    def disable_back(self):
        """Disable back button"""
        self.back_button.configure(state="disabled")

    def enable_back(self):
        """Enable back button"""
        self.back_button.configure(state="normal")

    def hide_back(self):
        """Hide back button"""
        self.back_button.grid_remove()

    def show_back(self):
        """Show back button"""
        self.back_button.grid()

    def set_back_command(self, command):
        self.back_button.configure(command=command)

    def set_next_text(self, text):
        """Update next button text"""
        self.next_button.configure(text=text)

    def disable_next(self):
        """Disable next button"""
        self.next_button.configure(state="disabled")

    def enable_next(self):
        """Enable next button"""
        self.next_button.configure(state="normal")

    def hide_next(self):
        """Hide next button"""
        self.next_button.grid_remove()

    def show_next(self):
        """Show next button"""
        self.next_button.grid()

    def set_next_command(self, command):
        self.next_button.configure(command=command)

    def hide_log_button(self):
        self.log_button.grid_remove()

    def show_log_button(self):
        self.log_button.grid()

    def show_log(self):
        log_file = None
        for handler in self.log.parent.handlers:
            if handler.__class__.__name__ == "FileHandler":
                log_file = handler.baseFilename
        if platform.system() == "Darwin":
            subprocess.call(("open", log_file))
        elif platform.system() == "Windows":
            os.startfile(log_file)
        else:
            subprocess.call(("xdg-open", log_file))

    def hide_monitor_button(self):
        """
        Function to hide the monitor button
        """
        self.monitor_button.grid_remove()

    def show_monitor_button(self):
        """
        Function to show the monitor button
        """
        self.monitor_button.grid()

    def monitor(self):
        """
        Function to open the serial monitor window
        """
        if self.monitor_window is None or not self.monitor_window.winfo_exists():
            self.monitor_window = SerialMonitor(self)
            self.monitor_window.focus()
            self.monitor_window.lift(self)
        else:
            self.monitor_window.focus()


class FormattedTextbox(ctk.CTkTextbox):
    """
    Class for formatting a CustomTkinter textbox

    Allows for bullet points only to start

    Usage example:
    textbox = FormattedTextbox(master, arguments)
    textbox.insert_bullet("insert", "Bullet list item")

    For a number of bullet list items:
    bullet_list = [
    "Item 1",
    "Item 2",
    "Item 3
    ]
    for item in bullet_list:
    -   textbox.insert_bullet("insert", item)
    """
    def __init__(self, *args, **kwargs):
        """
        Initialise the object

        Pass standard Textbox() arguments
        """
        super().__init__(*args, **kwargs)

        # Set up fonts
        self.common_fonts = CommonFonts(self)

        default_font = self.common_fonts.instruction_font
        em = default_font.measure("m")
        lmargin2 = em + default_font.measure("\u2022")
        self.tag_config("bullet", lmargin1=em, lmargin2=lmargin2, spacing1=1, spacing2=1, spacing3=1)

    def insert_bullet(self, index, text):
        """
        Function to insert a bullet point
        """
        self.insert(index, f"\u2022 {text}", "bullet")


class CreateToolTip(object):
    """
    Create a tooltip for a given widget with an optional URL

    To use, simply include this class and call it as such:

    from .common_widgets import CreateToolTip

    self.widget = <CustomTkinter widget creation>
    CreateTooltip(self.widget, "Tool tip contextual help text"[, URL])
    """
    def __init__(self, widget, text='widget info', url=None):
        """
        Instantiate object
        """
        self.wait_time = 500     # milliseconds
        self.hide_time = self.wait_time
        self.wraplength = 300   # pixels
        self.widget = widget
        self.text = text
        self.url = url
        self.widget.bind("<Enter>", self.enter_widget)
        self.widget.bind("<Leave>", self.leave_widget)
        self.widget.bind("<ButtonPress>", self.leave_widget)
        self.id = None
        self.tw = None

        # Set up fonts
        self.common_fonts = CommonFonts(self)

    def enter_widget(self, event=None):
        """
        When hovered/entered widget, schedule it to start
        """
        self.schedule_tooltip()

    def leave_widget(self, event=None):
        """
        When leaving the widget, schedule the hide
        """
        self.unschedule_tooltip()
        if hasattr(self, "toplevel"):
            if self.toplevel is not None:
                self.toplevel.after(self.hide_time, self.hide_tooltip)

    def schedule_tooltip(self):
        """
        Schedule the tip to appear
        """
        self.unschedule_tooltip()
        self.id = self.widget.after(self.wait_time, self.show_tooltip)

    def unschedule_tooltip(self):
        """
        Cancel the schedule
        """
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def show_tooltip(self, event=None):
        """
        Show the tooltip
        """
        tooltip_font = self.common_fonts.bold_instruction_font
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        # creates a toplevel window
        self.toplevel = ctk.CTkToplevel(self.widget)
        # Leaves only the label and removes the app window
        self.toplevel.wm_overrideredirect(True)
        self.toplevel.wm_geometry("+%d+%d" % (x, y))
        self.frame = ctk.CTkFrame(self.toplevel, border_color="#00A3B9", border_width=5, fg_color="#00353D",
                                  corner_radius=0)
        self.toplevel.grid_columnconfigure(0, weight=1)
        self.toplevel.grid_rowconfigure(0, weight=1)
        self.frame.grid(column=0, row=0)
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(0, weight=1)
        self.label = ctk.CTkLabel(self.frame, text=self.text, justify='left', font=tooltip_font,
                                  wraplength=self.wraplength, text_color="white")
        if self.url is not None:
            self.label.bind("<Button-1>", lambda x: self.open_url(self.url))
        self.label.grid(column=0, row=0, sticky="nsew", padx=15, pady=15)

    def hide_tooltip(self):
        """
        Hides the tooltip
        """
        toplevel = self.toplevel
        self.toplevel = None
        if toplevel:
            toplevel.destroy()

    def open_url(self, url):
        """
        Open the provided URL using the webbrowser module
        """
        webbrowser.open_new(url)
