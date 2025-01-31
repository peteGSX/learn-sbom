"""
Module for selecting the version of the software being installed

Also will allow for selecting a directory containing existing config files

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
import os
import logging
from CTkMessagebox import CTkMessagebox

# Import local modules
from .common_widgets import WindowLayout
from .product_details import product_details as pd
from .file_manager import FileManager as fm


class SelectVersionConfig(WindowLayout):
    """
    Class for selecting the version and config directory
    """

    # Instruction text
    version_text = ("For most users we recommend staying with the latest Production release, however you can " +
                    "install other versions if you know what you're doing, or if a version has been suggested by " +
                    "the DCC-EX team.")

    def __init__(self, parent, *args, **kwargs):
        """
        Initialise view
        """
        super().__init__(parent, *args, **kwargs)

        # Set up logger
        self.log = logging.getLogger(__name__)
        self.log.debug("Start view")

        # Set up event handlers
        event_callbacks = {
            "<<Setup_Local_Repo>>": self.setup_local_repo
        }
        for sequence, callback in event_callbacks.items():
            self.bind_class("bind_events", sequence, callback)
        new_tags = self.bindtags() + ("bind_events",)
        self.bindtags(new_tags)

        # Define variables
        self.product = None
        self.install_dir = None
        self.branch_name = None
        self.repo = None
        self.version_list = None
        self.latest_prod = None
        self.latest_devel = None
        self.product_dir = None

        # Set up next/back buttons
        self.next_back.set_back_text("Select Product")
        self.next_back.set_back_command(lambda view="select_product": parent.switch_view(view))
        self.next_back.set_next_text("Configuration")
        self.next_back.set_next_command(None)
        self.next_back.disable_next()
        self.next_back.hide_log_button()
        self.next_back.hide_monitor_button()

        # Set up and grid container frame
        self.version_frame = ctk.CTkFrame(self.main_frame, height=360)
        self.version_frame.grid(column=0, row=0, sticky="nsew")

        # Set up frame contents
        self.setup_version_frame()

    def set_product(self, product):
        """
        Function to set the product details to manage the repository
        """
        self.product = product
        self.set_title_text(f"Select {pd[self.product]['product_name']} version")
        self.set_title_logo(pd[product]["product_logo"])
        local_repo_dir = pd[self.product]["repo_name"].split("/")[1]
        self.product_dir = fm.get_install_dir(local_repo_dir)
        self.branch_name = pd[self.product]["default_branch"]
        self.setup_local_repo("setup_local_repo")

    def setup_version_frame(self):
        grid_options = {"padx": 5, "pady": 5}

        # Set up version instructions
        self.version_label = ctk.CTkLabel(self.version_frame, text=self.version_text,
                                          wraplength=780, font=self.instruction_font)

        # Set up select version radio frame and radio buttons
        self.version_radio_frame = ctk.CTkFrame(self.version_frame,
                                                border_width=2,
                                                fg_color="#E5E5E5")
        self.version_radio_frame.grid_columnconfigure((0, 1), weight=1)
        self.version_radio_frame.grid_rowconfigure((0, 1, 2, 3, 4, 5), weight=1)

        self.select_version = ctk.IntVar(value=0)
        self.latest_prod_radio = ctk.CTkRadioButton(self.version_radio_frame, variable=self.select_version,
                                                    text="Latest Production - Recommended!",
                                                    font=ctk.CTkFont(weight="bold"), value=0,
                                                    command=self.set_version)
        self.latest_devel_radio = ctk.CTkRadioButton(self.version_radio_frame, variable=self.select_version,
                                                     text="Latest Development", value=1,
                                                     command=self.set_version)
        self.select_version_radio = ctk.CTkRadioButton(self.version_radio_frame, variable=self.select_version,
                                                       text="Select a specific version", value=2,
                                                       command=self.set_version)
        self.select_version_combo = ctk.CTkComboBox(self.version_radio_frame, values=["Select a version"], width=150,
                                                    command=self.set_select_version)

        # Layout radio frame
        self.latest_prod_radio.grid(column=0, row=0, columnspan=2, sticky="w", **grid_options)
        self.latest_devel_radio.grid(column=0, row=1, columnspan=2, sticky="w", **grid_options)
        self.select_version_radio.grid(column=0, row=2, sticky="w", **grid_options)
        self.select_version_combo.grid(column=1, row=2, sticky="e", **grid_options)

        # Set up configuration options
        self.config_radio_frame = ctk.CTkFrame(self.version_frame)
        self.config_option = ctk.IntVar(value=0)
        self.configure_radio = ctk.CTkRadioButton(self.config_radio_frame, variable=self.config_option,
                                                  text="Configure options on the next screen", value=0,
                                                  command=self.set_next_config)
        self.use_config_radio = ctk.CTkRadioButton(self.config_radio_frame, variable=self.config_option,
                                                   text="Use my existing configuration files", value=1,
                                                   command=self.set_next_config)
        self.config_path = ctk.StringVar(value=None)
        self.config_file_entry = ctk.CTkEntry(self.config_radio_frame, textvariable=self.config_path,
                                              width=300)
        self.browse_button = ctk.CTkButton(self.config_radio_frame, text="Browse",
                                           width=80, command=self.browse_configdir)

        # Configure and layout config frame
        self.config_radio_frame.grid_columnconfigure((0, 1), weight=1)
        self.config_radio_frame.grid_rowconfigure((0, 1), weight=1)
        self.configure_radio.grid(column=0, row=0, columnspan=3, sticky="w", **grid_options)
        self.use_config_radio.grid(column=0, row=1, sticky="w", **grid_options)
        self.config_file_entry.grid(column=1, row=1, **grid_options)
        self.browse_button.grid(column=2, row=1, sticky="w", **grid_options)

        # Configure and layout version frame
        self.version_frame.grid_columnconfigure(0, weight=1)
        self.version_frame.grid_rowconfigure((0, 1, 2), weight=1)
        self.version_label.grid(column=0, row=0, **grid_options)
        self.version_radio_frame.grid(column=0, row=1, **grid_options)
        self.config_radio_frame.grid(column=0, row=2, **grid_options)

    def setup_local_repo(self, event):
        """
        Function to setup the local repository

        Process:
        - check if the product directory already exists
        - if so

            - if the product directory is already a cloned repo
            - any locally modified files that would interfere with Git commands (prompt to resolve)
            - delete any existing configuration files
            
        - if not, clone repo
        - get list of versions, latest prod, and latest devel versions
        """
        if event == "setup_local_repo":
            self.log.debug("Setting up local repository")
            self.delete_config_files()
            if os.path.exists(self.product_dir) and os.path.isdir(self.product_dir):
                if self.git.dir_is_git_repo(self.product_dir):
                    self.repo = self.git.get_repo(self.product_dir)
                    if self.repo:
                        changes = self.git.check_local_changes(self.repo)
                        if changes:
                            self.process_error("Local changes have been detected that require resolution")
                            self.log.error("Local repository file changes: %s", changes)
                            self.resolve_local_changes(changes)
                        else:
                            self.setup_local_repo("get_latest")
                    else:
                        self.process_error(f"{self.product_dir} appears to be a Git repository but is not")
                else:
                    if fm.dir_is_empty(self.product_dir):
                        self.setup_local_repo("clone_repo")
                    else:
                        self.process_error(f"{self.product_dir} contains files but is not a repo")
            else:
                self.log.debug("Cloning repository")
                self.setup_local_repo("clone_repo")
        elif event == "clone_repo":
            self.process_start("clone_repo", "Clone repository", "Setup_Local_Repo")
            self.git.clone_repo(pd[self.product]["repo_url"], self.product_dir, self.queue)
        elif self.process_phase == "clone_repo" or event == "get_latest":
            if self.process_status == "success" or event == "get_latest":
                self.repo = self.git.get_repo(self.product_dir)
                branch_ref = self.git.get_branch_ref(self.repo, self.branch_name)
                self.log.debug("Checkout %s", self.branch_name)
                try:
                    self.repo.checkout(refname=branch_ref)
                except Exception as error:
                    message = self.get_exception(error)
                    self.process_error(message)
                    self.log.error(message)
                else:
                    self.process_start("pull_latest", "Get latest software updates", "Setup_Local_Repo")
                    self.git.pull_latest(self.repo, self.branch_name, self.queue)
            elif self.process_status == "error":
                self.process_error(self.process_data)
                self.log.error(self.process_data)
        elif self.process_phase == "pull_latest":
            if self.process_status == "success":
                self.set_versions(self.repo)
                self.process_stop()
                self.set_next_config()
            elif self.process_status == "error":
                self.process_error("Could not pull latest updates from GitHub")
                self.log.error("Could not pull updates from GitHub")

    def set_versions(self, repo):
        """
        Function to obtain versions available in the repo

        Once versions obtained, set appropriately
        """
        self.latest_prod = self.git.get_latest_prod(self.repo)
        if self.latest_prod:
            self.latest_prod_radio.configure(text=f"Latest Production ({self.latest_prod[0]}) - Recommended!")
        else:
            self.latest_prod_radio.grid_remove()
            self.select_version.set(-1)
        self.latest_devel = self.git.get_latest_devel(self.repo)
        if self.latest_devel:
            self.latest_devel_radio.configure(text=f"Latest Development ({self.latest_devel[0]})")
        else:
            self.latest_devel_radio.grid_remove()
        self.version_list = self.git.get_repo_versions(self.repo)
        self.version_list.update({'v9.9.9-Devel devel branch':
                                  {'major': 9, 'minor': 9, 'patch': 9, 'type': 'Devel', 'ref': 'origin/devel'}})
        if self.version_list:
            version_select = list(self.version_list.keys())
            self.select_version_combo.configure(values=version_select)
        self.set_version()

    def set_version(self):
        """
        Function to checkout the selected version according to the radio buttons
        """
        if self.select_version.get() == 0 and self.latest_prod:
            self.repo.checkout(refname=self.latest_prod[1])
            self.log.debug("Latest prod selected: %s", self.latest_prod[1])
            self.set_next_config()
        elif self.select_version.get() == 1 and self.latest_devel:
            self.repo.checkout(refname=self.latest_devel[1])
            self.log.debug("Latest devel selected: %s", self.latest_devel[1])
            self.set_next_config()
        elif self.select_version.get() == 2:
            if self.select_version_combo.get() != "Select a version":
                # self.repo.checkout(refname=self.version_list[self.select_version_combo.get()]["ref"])
                rname = self.version_list[self.select_version_combo.get()]["ref"]
                try:
                    self.repo.checkout(refname=rname)
                except Exception:
                    _, ref = self. repo.resolve_refish(refish=rname)
                    self.repo.checkout(refname=ref)
                self.log.debug("Version selected: %s", self.version_list[self.select_version_combo.get()]["ref"])
                self.set_next_config()
            else:
                self.next_back.disable_next()

    def set_select_version(self, value):
        """
        Function to set select a specific version when setting via combobox
        """
        if self.select_version.get() != 2:
            self.select_version.set(2)
        self.set_version()

    def set_next_config(self):
        """
        Function to select what configuration to do next
        """
        if self.config_option.get() == 0:
            self.master.use_existing = False
            set_version = None
            if self.select_version.get() == 0:
                set_version = self.latest_prod[0]
                self.next_back.enable_next()
            elif self.select_version.get() == 1:
                set_version = self.latest_devel[0]
                self.next_back.enable_next()
            elif self.select_version.get() == 2:
                if self.select_version_combo.get() != "Select a version":
                    set_version = self.select_version_combo.get()
                    self.next_back.enable_next()
            if self.set_version:
                self.next_back.set_next_command(lambda next_product=self.product,
                                                set_version=set_version: self.master.switch_view(next_product,
                                                                                                 None,
                                                                                                 set_version))
            else:
                self.next_back.disable_next()
            self.next_back.set_next_text(f"Configure {pd[self.product]['product_name']}")
        elif self.config_option.get() == 1:
            self.master.use_existing = True
            self.next_back.set_next_command(self.copy_config_files)
            self.next_back.set_next_text("Advanced Config")
            self.validate_config_dir()

    def browse_configdir(self):
        """
        Opens a file browser dialogue to allow user to select a config file to use

        Uses directory of this file to set the config directory

        This is a workaround for "askdirectory()" not showing files, which is confusing for users
        """
        select_file = ctk.filedialog.askopenfilename()
        if select_file:
            directory = os.path.dirname(select_file)
            self.config_path.set(directory)
            self.config_option.set(1)
            self.set_next_config()
            self.log.debug("Get config from %s", directory)

    def validate_config_dir(self):
        """
        Function to validate the selected directory for config files:

        - Is a valid directory
        - Contains at least the specified minimum config files
        """
        if self.config_path.get():
            if os.path.realpath(self.config_path.get()) == os.path.realpath(self.product_dir):
                self.process_error("You cannot use EX-Installer's own generated files as these will be overwritten")
                self.next_back.disable_next()
                self.log.error(f"EX-Installer repository folder location chosen: {self.product_dir}")
            else:
                config_files = fm.get_config_files(self.config_path.get(), pd[self.product]["minimum_config_files"])
                if config_files:
                    self.next_back.enable_next()
                else:
                    file_names = ", ".join(pd[self.product]["minimum_config_files"])
                    self.process_error(("Selected configuration directory is missing the required files: " +
                                       f"{file_names}"))
                    self.next_back.disable_next()
                    self.log.error("Config dir %s missing minimum config files %s", self.config_path.get(),
                                   config_files)
        else:
            self.next_back.disable_next()

    def delete_config_files(self):
        """
        Function to delete config files from product directory
        needed on subsequent passes thru the logic
        """
        file_list = []
        min_list = fm.get_config_files(self.product_dir, pd[self.product]["minimum_config_files"])
        if min_list:
            file_list += min_list
        other_list = None
        if "other_config_files" in pd[self.product]:
            other_list = fm.get_config_files(self.product_dir, pd[self.product]["other_config_files"])
        if other_list:
            file_list += other_list
        self.log.debug("Deleting files: %s", file_list)
        error_list = fm.delete_config_files(self.product_dir, file_list)
        if error_list:
            file_list = ", ".join(error_list)
            self.process_error(f"Failed to delete one or more files: {file_list}")
            self.log.error("Failed to delete: %s", file_list)

    def copy_config_files(self):
        """
        Function to copy config files from selected directory to product directory
        also switches view to advanced_config if copy is successful
        """
        copy_list = fm.get_config_files(self.config_path.get(), pd[self.product]["minimum_config_files"])
        if copy_list:
            extra_list = None
            if "other_config_files" in pd[self.product]:
                extra_list = fm.get_config_files(self.config_path.get(), pd[self.product]["other_config_files"])
            if extra_list:
                copy_list += extra_list
            file_copy = fm.copy_config_files(self.config_path.get(), self.product_dir, copy_list)
            if file_copy:
                file_list = ", ".join(file_copy)
                self.process_error(f"Failed to copy one or more files: {file_list}")
                self.log.error("Failed to copy: %s", file_list)
            else:
                self.master.switch_view("advanced_config", self.product)
        else:
            self.process_error("Selected configuration directory is missing the required files")
            self.log.error("Directory %s is missing required files", self.config_path.get())

    def resolve_local_changes(self, changes):
        """
        Function to prompt the user to resolve locally detected repository changes

        Resolution means perforing a git hard reset, cancel means exiting the app
        """
        message = f"WARNING: The following changes have been detected in {pd[self.product]['product_name']}:\n"
        for change in changes:
            message += change + "\n"
        message += ("\nYou can either override these changes or cancel and resolve these issues manually.\n\n"
                    "(Note that overriding will delete any added files, undo any modifications,"
                    " and restore deleted files)")
        resolver = CTkMessagebox(master=self.parent, title="Local changes detected", icon="warning",
                                 message=message, border_width=3, width=500, cancel_button=None,
                                 option_2="Override", option_1="Cancel", icon_size=(30, 30),
                                 font=self.common_fonts.instruction_font)
        if resolver.get() == "Override":
            self.git.git_hard_reset(self.repo)
            self.setup_local_repo("setup_local_repo")
        else:
            self.parent.switch_view("select_product")
