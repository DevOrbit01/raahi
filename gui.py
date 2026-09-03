"""Modern GUI for the Raahi Scraper using CustomTkinter"""
import customtkinter as ctk
from tkinter import messagebox, filedialog
import threading
import os
import platform
import subprocess
import requests
from config import STATES
from scraper_runner import collect_new_items, mark_items_seen, save_items_to_excel
from seen_db import seen_db


class ScraperGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Raahi Property Scraper")
        self.root.geometry("950x750")
        
        # Set theme
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        self.is_scraping = False
        self.output_file = None
        self.output_folder = os.path.join(os.getcwd(), "output")
        self.scraped_items = []
        self.property_check_vars = []
        self.main_thread = threading.current_thread()
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""

        # Keep primary actions outside the scroll area so they are always visible,
        # including on smaller Windows screens or high display scaling.
        control_frame = ctk.CTkFrame(self.root)
        control_frame.pack(pady=(10, 5), padx=20, fill="x")

        self.start_btn = ctk.CTkButton(
            control_frame,
            text="Start Scraping",
            command=self.start_scraping,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=44,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.start_btn.pack(side="left", padx=5, expand=True, fill="x")

        self.download_selected_btn = ctk.CTkButton(
            control_frame,
            text="Download Selected",
            command=self.download_selected,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=44,
            state="disabled"
        )
        self.download_selected_btn.pack(side="left", padx=5, expand=True, fill="x")

        self.open_file_btn = ctk.CTkButton(
            control_frame,
            text="Open Output File",
            command=self.open_output_file,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=44,
            state="disabled"
        )
        self.open_file_btn.pack(side="left", padx=5, expand=True, fill="x")

        clear_db_btn = ctk.CTkButton(
            control_frame,
            text="Clear Database",
            command=self.clear_database,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=44,
            fg_color="red",
            hover_color="darkred"
        )
        clear_db_btn.pack(side="left", padx=5, expand=True, fill="x")
        
        # Main scrollable content frame
        content_frame = ctk.CTkScrollableFrame(self.root)
        content_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        # Site selection
        site_frame = ctk.CTkFrame(content_frame)
        site_frame.pack(pady=10, padx=20, fill="x")
        
        site_label = ctk.CTkLabel(
            site_frame,
            text="Select Sites to Scrape:",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        site_label.pack(pady=(10, 5), anchor="w")
        
        # Sites list
        self.site_vars = {}
        sites = [
            ('BaankNet', 'baanknet'),
            ('BaankNet IBC', 'baanknet_ibc'),
            ('BaankNet Property', 'baanknet_property'),
            ('BankEAuctions', 'bankauctions'),
            ('BankAuction.in', 'bankauction')
        ]
        
        site_checkbox_frame = ctk.CTkFrame(site_frame)
        site_checkbox_frame.pack(pady=5, fill="x")
        
        for i, (display_name, key) in enumerate(sites):
            var = ctk.BooleanVar(value=True)
            self.site_vars[key] = var
            
            checkbox = ctk.CTkCheckBox(
                site_checkbox_frame,
                text=display_name,
                variable=var,
                font=ctk.CTkFont(size=14)
            )
            checkbox.grid(row=i//2, column=i%2, padx=20, pady=5, sticky="w")
        
        # Select/Deselect all sites buttons
        site_button_frame = ctk.CTkFrame(site_frame)
        site_button_frame.pack(pady=5)
        
        select_all_sites_btn = ctk.CTkButton(
            site_button_frame,
            text="Select All Sites",
            command=self.select_all_sites,
            width=120
        )
        select_all_sites_btn.pack(side="left", padx=5)
        
        deselect_all_sites_btn = ctk.CTkButton(
            site_button_frame,
            text="Deselect All Sites",
            command=self.deselect_all_sites,
            width=120
        )
        deselect_all_sites_btn.pack(side="left", padx=5)
        
        # State selection
        state_frame = ctk.CTkFrame(content_frame)
        state_frame.pack(pady=10, padx=20, fill="x")
        
        state_label = ctk.CTkLabel(
            state_frame,
            text="Select States to Scrape:",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        state_label.pack(pady=(10, 5), anchor="w")
        
        # State checkboxes
        self.state_vars = {}
        checkbox_frame = ctk.CTkFrame(state_frame)
        checkbox_frame.pack(pady=5, fill="x")
        
        for i, state in enumerate(STATES):
            var = ctk.BooleanVar(value=True)
            self.state_vars[state] = var
            
            checkbox = ctk.CTkCheckBox(
                checkbox_frame,
                text=state,
                variable=var,
                font=ctk.CTkFont(size=14)
            )
            checkbox.grid(row=i//2, column=i%2, padx=20, pady=5, sticky="w")
        
        # Select/Deselect all buttons
        button_frame = ctk.CTkFrame(state_frame)
        button_frame.pack(pady=5)
        
        select_all_btn = ctk.CTkButton(
            button_frame,
            text="Select All",
            command=self.select_all_states,
            width=120
        )
        select_all_btn.pack(side="left", padx=5)
        
        deselect_all_btn = ctk.CTkButton(
            button_frame,
            text="Deselect All",
            command=self.deselect_all_states,
            width=120
        )
        deselect_all_btn.pack(side="left", padx=5)
        
        # Output folder selection
        output_frame = ctk.CTkFrame(content_frame)
        output_frame.pack(pady=10, padx=20, fill="x")
        
        output_label = ctk.CTkLabel(
            output_frame,
            text="Output Folder:",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        output_label.pack(pady=(10, 5), anchor="w")
        
        folder_select_frame = ctk.CTkFrame(output_frame)
        folder_select_frame.pack(pady=5, fill="x")
        
        self.output_folder_entry = ctk.CTkEntry(
            folder_select_frame,
            placeholder_text="Select output folder...",
            font=ctk.CTkFont(size=12),
            height=35
        )
        self.output_folder_entry.pack(side="left", padx=(10, 5), fill="x", expand=True)
        self.output_folder_entry.insert(0, self.output_folder)
        
        browse_btn = ctk.CTkButton(
            folder_select_frame,
            text="📁 Browse",
            command=self.browse_output_folder,
            width=100,
            height=35
        )
        browse_btn.pack(side="left", padx=(5, 10))
        
        # Progress section
        progress_frame = ctk.CTkFrame(content_frame)
        progress_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        progress_label = ctk.CTkLabel(
            progress_frame,
            text="Progress:",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        progress_label.pack(pady=(10, 5), anchor="w")
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(pady=10, padx=10, fill="x")
        self.progress_bar.set(0)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Ready to start scraping",
            font=ctk.CTkFont(size=13)
        )
        self.status_label.pack(pady=5)
        
        # Log area
        log_label = ctk.CTkLabel(
            progress_frame,
            text="Activity Log:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        log_label.pack(pady=(10, 5), anchor="w")
        
        self.log_text = ctk.CTkTextbox(
            progress_frame,
            height=120,
            font=ctk.CTkFont(size=11)
        )
        self.log_text.pack(pady=5, padx=10, fill="x")
        
        properties_label = ctk.CTkLabel(
            progress_frame,
            text="Properties (select before download):",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        properties_label.pack(pady=(10, 5), anchor="w")
        
        # Property selection buttons
        prop_btn_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        prop_btn_frame.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkButton(
            prop_btn_frame,
            text="Select All",
            command=self.select_all_properties,
            width=80,
            height=24,
            font=ctk.CTkFont(size=11)
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            prop_btn_frame,
            text="Deselect All",
            command=self.deselect_all_properties,
            width=80,
            height=24,
            font=ctk.CTkFont(size=11)
        ).pack(side="left")
        
        self.properties_frame = ctk.CTkScrollableFrame(progress_frame, height=200)
        self.properties_frame.pack(pady=5, padx=10, fill="both", expand=True)

        # Download options
        self.download_images_var = ctk.BooleanVar(value=True)
        download_images_cb = ctk.CTkCheckBox(
            progress_frame,
            text="Download Images with Excel",
            variable=self.download_images_var,
            font=ctk.CTkFont(size=12)
        )
        download_images_cb.pack(pady=10, anchor="w", padx=10)
        
    def select_all_sites(self):
        """Select all sites"""
        for var in self.site_vars.values():
            var.set(True)
    
    def deselect_all_sites(self):
        """Deselect all sites"""
        for var in self.site_vars.values():
            var.set(False)
    
    def select_all_states(self):
        """Select all states"""
        for var in self.state_vars.values():
            var.set(True)
    
    def deselect_all_states(self):
        """Deselect all states"""
        for var in self.state_vars.values():
            var.set(False)

    def select_all_properties(self):
        """Select all scraped properties"""
        for var, _ in self.property_check_vars:
            var.set(True)

    def deselect_all_properties(self):
        """Deselect all scraped properties"""
        for var, _ in self.property_check_vars:
            var.set(False)
    
    def browse_output_folder(self):
        """Browse for output folder"""
        folder = filedialog.askdirectory(
            title="Select Output Folder",
            initialdir=self.output_folder
        )
        if folder:
            self.output_folder = folder
            self.output_folder_entry.delete(0, "end")
            self.output_folder_entry.insert(0, folder)
            self.log(f"📁 Output folder set to: {folder}")
    
    def log(self, message):
        """Add message to log"""
        def do_log():
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.root.update_idletasks()
        self.run_on_ui_thread(do_log)
    
    def update_progress(self, value):
        """Update progress bar"""
        def do_update():
            self.progress_bar.set(value / 100)
            self.root.update_idletasks()
        self.run_on_ui_thread(do_update)
    
    def update_status(self, message):
        """Update status label"""
        def do_update():
            self.status_label.configure(text=message)
            self.log(message)
            self.root.update_idletasks()
        self.run_on_ui_thread(do_update)

    def run_on_ui_thread(self, callback):
        """Run Tkinter work from the main UI thread."""
        if threading.current_thread() is self.main_thread:
            callback()
        else:
            self.root.after(0, callback)
    
    def populate_properties_list(self):
        for widget in self.properties_frame.winfo_children():
            widget.destroy()
        self.property_check_vars = []
        for i, item in enumerate(self.scraped_items):
            listing_id = str(item.get("listingId", ""))
            name = item.get("name", "") or item.get("schemeName", "")
            city = item.get("city", "")
            label_text = f"{listing_id} | {city} | {name}"
            var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(
                self.properties_frame,
                text=label_text,
                variable=var,
                font=ctk.CTkFont(size=11)
            )
            cb.pack(pady=2, padx=5, fill="x")
            self.property_check_vars.append((var, item))
    
    def start_scraping(self):
        """Start the scraping process"""
        if self.is_scraping:
            messagebox.showwarning("Warning", "Scraping is already in progress!")
            return
        
        # Get selected sites
        selected_sites = [
            site for site, var in self.site_vars.items()
            if var.get()
        ]
        
        if not selected_sites:
            messagebox.showwarning("Warning", "Please select at least one site!")
            return
        
        # Get selected states
        selected_states = [
            state for state, var in self.state_vars.items()
            if var.get()
        ]
        
        if not selected_states:
            messagebox.showwarning("Warning", "Please select at least one state!")
            return
        
        # Clear log
        self.log_text.delete("1.0", "end")
        
        # Disable start button
        self.start_btn.configure(state="disabled", text="⏳ Scraping...")
        self.open_file_btn.configure(state="disabled")
        self.download_selected_btn.configure(state="disabled")
        self.is_scraping = True
        self.output_file = None
        
        # Reset progress
        self.progress_bar.set(0)
        self.update_status("Initializing scrapers...")
        
        thread = threading.Thread(
            target=self.run_scraping_thread,
            args=(selected_states, selected_sites),
            daemon=True
        )
        thread.start()
    
    def run_scraping_thread(self, selected_states, selected_sites):
        try:
            self.scraped_items = collect_new_items(
                selected_states=selected_states,
                selected_sites=selected_sites,
                progress_callback=self.update_progress,
                status_callback=self.update_status
            )
            
            self.log(f"Scraped items count: {len(self.scraped_items)}")
            self.update_status("✅ Scraping completed. Select properties and click 'Download Selected'.")
            self.update_progress(100)
            
            self.root.after(0, self.populate_properties_list)
            self.root.after(0, lambda: self.download_selected_btn.configure(state="normal"))
            
        except Exception as e:
            self.update_status(f"❌ Error: {str(e)}")
            self.log(f"Error details: {str(e)}")
            
            self.root.after(0, lambda: messagebox.showerror(
                "Error",
                f"An error occurred during scraping:\n\n{str(e)}"
            ))
        
        finally:
            self.is_scraping = False
            self.root.after(0, lambda: self.start_btn.configure(
                state="normal",
                text="▶ Start Scraping"
            ))
    
    def download_selected(self):
        if not self.scraped_items or not self.property_check_vars:
            messagebox.showwarning("Warning", "No properties available to download.")
            return
        
        selected_items = [item for var, item in self.property_check_vars if var.get()]
        if not selected_items:
            messagebox.showwarning("Warning", "Please select at least one property to download.")
            return
        
        output_folder = self.output_folder_entry.get().strip()
        if not output_folder:
            output_folder = self.output_folder
        
        self.download_selected_btn.configure(state="disabled", text="⏳ Downloading...")
        self.open_file_btn.configure(state="disabled")
        
        thread = threading.Thread(
            target=self.run_download_thread,
            args=(selected_items, output_folder),
            daemon=True
        )
        thread.start()
    
    def run_download_thread(self, selected_items, output_folder):
        try:
            self.update_status("Creating Excel file for selected properties...")
            self.output_file = save_items_to_excel(selected_items, output_folder=output_folder, status_callback=self.update_status)
            
            if self.download_images_var.get():
                self.update_status("Downloading images for selected properties...")
                images_root = os.path.join(output_folder, "images")
                documents_root = os.path.join(output_folder, "documents")
                os.makedirs(images_root, exist_ok=True)
                os.makedirs(documents_root, exist_ok=True)
                
                for item in selected_items:
                    listing_id = str(item.get("listingId", "") or item.get("fingerprint", "unknown"))
                    if not listing_id:
                        listing_id = "unknown"
                    images_value = item.get("images", "") or ""
                    if not images_value:
                        continue
                    urls = [u.strip() for u in images_value.split(",") if u.strip()]
                    if not urls:
                        continue
                    prop_dir = os.path.join(images_root, listing_id)
                    os.makedirs(prop_dir, exist_ok=True)
                    for idx, url in enumerate(urls, start=1):
                        try:
                            resp = requests.get(url, timeout=20)
                            if resp.status_code != 200:
                                continue
                            ext = ".jpg"
                            name_part = url.split("/")[-1]
                            if "." in name_part:
                                ext = "." + name_part.split(".")[-1].split("?")[0]
                            file_name = f"media_{idx}{ext}"
                            file_path = os.path.join(prop_dir, file_name)
                            with open(file_path, "wb") as f:
                                f.write(resp.content)
                        except Exception:
                            continue

                    pdfs_value = item.get("pdfLinks", "") or ""
                    pdf_urls = [u.strip() for u in pdfs_value.split(",") if u.strip()]
                    if not pdf_urls:
                        continue
                    docs_dir = os.path.join(documents_root, listing_id)
                    os.makedirs(docs_dir, exist_ok=True)
                    for idx, url in enumerate(pdf_urls, start=1):
                        try:
                            resp = requests.get(url, timeout=30)
                            if resp.status_code != 200:
                                continue
                            name_part = url.split("/")[-1].split("?")[0]
                            ext = ".pdf" if "." not in name_part else "." + name_part.split(".")[-1]
                            file_name = f"document_{idx}{ext}"
                            file_path = os.path.join(docs_dir, file_name)
                            with open(file_path, "wb") as f:
                                f.write(resp.content)
                        except Exception:
                            continue
                
                msg = f"Download completed.\n\nExcel file: {self.output_file}\nImages folder: {images_root}\nDocuments folder: {documents_root}"
            else:
                self.update_status("Skipping image download as per selection.")
                msg = f"Download completed.\n\nExcel file: {self.output_file}\n(Images were skipped)"
            
            mark_items_seen(selected_items)
            self.update_status("✅ Download completed for selected properties.")
            self.root.after(0, lambda: self.open_file_btn.configure(state="normal"))
            
            self.root.after(0, lambda: messagebox.showinfo(
                "Success",
                msg
            ))
        except Exception as e:
            self.update_status(f"❌ Error during download: {str(e)}")
            self.log(f"Error details: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror(
                "Error",
                f"An error occurred during download:\n\n{str(e)}"
            ))
        finally:
            self.root.after(0, lambda: self.download_selected_btn.configure(
                state="normal",
                text="⬇ Download Selected"
            ))
    
    def open_output_file(self):
        """Open the output Excel file"""
        if self.output_file and os.path.exists(self.output_file):
            try:
                # Open file with default application
                if os.name == 'nt':  # Windows
                    os.startfile(self.output_file)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", self.output_file])
                elif os.name == 'posix':  # Linux
                    subprocess.Popen(["xdg-open", self.output_file])
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file:\n\n{str(e)}")
        else:
            messagebox.showwarning("Warning", "No output file available!")
    
    def clear_database(self):
        """Clear the seen properties database"""
        if messagebox.askyesno(
            "Confirm",
            "Are you sure you want to clear the seen properties database?\n\n"
            "This will allow previously scraped properties to be scraped again."
        ):
            try:
                seen_db.clear()
                messagebox.showinfo("Success", "Database cleared successfully!")
                self.log("🗑️ Seen properties database cleared")
            except Exception as e:
                messagebox.showerror("Error", f"Could not clear database:\n\n{str(e)}")
    
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()


def main():
    """Main entry point"""
    app = ScraperGUI()
    app.run()


if __name__ == "__main__":
    main()
