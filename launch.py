#!/usr/bin/env python3
import sys
import os
import json
import threading
import tempfile
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from pathlib import Path
from contacts import ContactsImporter
from pyicloud import PyiCloudService

CONFIG_FILE = Path.home() / ".icloud_carddav_gui_config.json"

def escape(text):
    return text.replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def generate_vcard(contact):
    lines = ["BEGIN:VCARD", "VERSION:3.0"]
    full_name = (
        contact.get("fullName")
        or f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
        or contact.get("companyName")
        or (contact.get("emails", [{}])[0].get("field") if contact.get("emails") else None)
        or f"Inconnu {contact.get('contactId', '')}"
    )
    lines.append(f"FN:{escape(full_name)}")
    first = contact.get("firstName", "")
    last = contact.get("lastName", "")
    lines.append(f"N:{escape(last)};{escape(first)};;;")
    for phone in contact.get("phones", []):
        tel = phone.get("field", "").replace(" ", "").replace("-", "")
        label = phone.get("label", "VOICE").upper()
        lines.append(f"TEL;TYPE={label}:{tel}")
    for email in contact.get("emails", []):
        addr = email.get("field", "").strip()
        if addr:
            lines.append(f"EMAIL;TYPE=INTERNET:{addr}")
    if contact.get("companyName"):
        lines.append(f"ORG:{escape(contact['companyName'])}")
    for address in contact.get("addresses", []):
        parts = [
            escape(address.get("street", "")),
            escape(address.get("city", "")),
            escape(address.get("state", "")),
            escape(address.get("postalCode", "")),
            escape(address.get("country", ""))
        ]
        label = address.get("label", "HOME").upper()
        adr = f";;{parts[0]};{parts[1]};{parts[2]};{parts[3]};{parts[4]}"
        lines.append(f"ADR;TYPE={label}:{adr}")
    if contact.get("birthdays"):
        for birthday in contact["birthdays"]:
            year = birthday.get("year", "")
            month = str(birthday.get("month", "")).zfill(2)
            day = str(birthday.get("day", "")).zfill(2)
            if month and day:
                date = f"{year}-{month}-{day}" if year else f"--{month}-{day}"
                lines.append(f"BDAY:{date}")
    for url in contact.get("urls", []):
        field = url.get("field", "")
        if field:
            lines.append(f"URL:{field}")
    if contact.get("note"):
        lines.append(f"NOTE:{escape(contact['note'])}")
    if contact.get("contactId"):
        lines.append(f"UID:{contact['contactId']}")
    lines.append("END:VCARD")
    return "\n".join(lines)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("iCloud ➜ CardDAV")
        self.root.geometry("600x520")
        self.root.resizable(True, True)

        self.fields = {
            "apple_id": tk.StringVar(),
            "apple_pw": tk.StringVar(),
            "carddav_url": tk.StringVar(),
            "carddav_user": tk.StringVar(),
            "carddav_pass": tk.StringVar(),
            "remember": tk.BooleanVar(),
            "export_only": tk.BooleanVar()
        }

        self.load_config()
        self.build_ui()

    def load_config(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                self.fields["apple_id"].set(data.get("apple_id", ""))
                self.fields["carddav_url"].set(data.get("carddav_url", ""))
                self.fields["carddav_user"].set(data.get("carddav_user", ""))
                self.fields["remember"].set(True)

    def save_config(self):
        if self.fields["remember"].get():
            with open(CONFIG_FILE, "w") as f:
                json.dump({
                    "apple_id": self.fields["apple_id"].get(),
                    "carddav_url": self.fields["carddav_url"].get(),
                    "carddav_user": self.fields["carddav_user"].get()
                }, f)

    def build_ui(self):
        frm = ttk.Frame(self.root, padding=20)
        frm.grid()
        ttk.Label(frm, text="Identifiant Apple").grid(column=0, row=0, sticky="e")
        ttk.Entry(frm, textvariable=self.fields["apple_id"]).grid(column=1, row=0)
        ttk.Label(frm, text="Mot de passe Apple").grid(column=0, row=1, sticky="e")
        ttk.Entry(frm, textvariable=self.fields["apple_pw"], show="*").grid(column=1, row=1)
        ttk.Label(frm, text="URL CardDAV").grid(column=0, row=2, sticky="e")
        ttk.Entry(frm, textvariable=self.fields["carddav_url"]).grid(column=1, row=2)
        ttk.Label(frm, text="Utilisateur CardDAV").grid(column=0, row=3, sticky="e")
        ttk.Entry(frm, textvariable=self.fields["carddav_user"]).grid(column=1, row=3)
        ttk.Label(frm, text="Mot de passe CardDAV").grid(column=0, row=4, sticky="e")
        ttk.Entry(frm, textvariable=self.fields["carddav_pass"], show="*").grid(column=1, row=4)
        ttk.Checkbutton(frm, text="Se souvenir", variable=self.fields["remember"]).grid(column=1, row=5, sticky="w")
        ttk.Checkbutton(frm, text="📁 Exporter vers contacts.vcf uniquement (pas de synchro)",
                        variable=self.fields["export_only"]).grid(column=1, row=6, sticky="w")

        self.progress = ttk.Progressbar(frm, mode="determinate", maximum=100)
        self.progress.grid(column=0, row=7, columnspan=2, pady=10, sticky="ew")
        self.log = tk.Text(frm, height=10, wrap="word")
        self.log.grid(column=0, row=9, columnspan=2, sticky="nsew")
        frm.grid_rowconfigure(9, weight=1)
        frm.grid_columnconfigure(1, weight=1)
        ttk.Button(frm, text="Lancer", command=self.run).grid(column=0, row=8, columnspan=2)

    def run(self):
        self.save_config()
        self.log.delete(1.0, tk.END)
        threading.Thread(target=self.sync).start()

    def sync(self):
        try:
            self.log.insert(tk.END, "🔐 Connexion à iCloud...\n")
            self.progress["value"] = 0
            api = PyiCloudService(self.fields["apple_id"].get(), self.fields["apple_pw"].get())

            if api.requires_2fa:
                code_holder = {}

                def prompt_code():
                    code = simpledialog.askstring("2FA", "Code de vérification Apple (2FA)", parent=self.root)
                    code_holder["code"] = code

                self.root.after(0, prompt_code)
                while "code" not in code_holder:
                    self.root.update()
                api.validate_2fa_code(code_holder["code"])

            self.log.insert(tk.END, "📥 Récupération des contacts...\n")
            contacts = api.contacts.all()
            total = len(contacts)
            self.progress["maximum"] = total

            export_path = Path("contacts.vcf")
            if export_path.exists():
                export_path.unlink()

            with open(export_path, "w", encoding="utf-8") as f:
                for i, contact in enumerate(contacts):
                    try:
                        vcard = generate_vcard(contact)
                        f.write(vcard + "\n")
                        full_name = (
                            contact.get("fullName")
                            or f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
                            or contact.get("companyName")
                            or "Inconnu"
                        )
                        self.log.insert(tk.END, f"✔️ {i+1}/{total} {full_name}\n")
                        self.log.see(tk.END)
                    except Exception as e:
                        self.log.insert(tk.END, f"❌ Erreur sur contact {i+1}: {str(e)}\n")
                        self.log.see(tk.END)
                    self.progress["value"] = i + 1

            if self.fields["export_only"].get():
                self.log.insert(tk.END, f"✅ Export terminé : {export_path.resolve()}\n")
                self.log.see(tk.END)
                self.root.after(0, lambda: messagebox.showinfo("Export terminé", f"Fichier : {export_path.resolve()}"))
                return

            self.log.insert(tk.END, "📤 Import des contacts vers CardDAV...\n")
            importer = ContactsImporter(
                carddav_url=self.fields["carddav_url"].get(),
                carddav_user=self.fields["carddav_user"].get(),
                carddav_pass=self.fields["carddav_pass"].get()
            )
            result = importer.import_vcards(str(export_path))
            self.log.insert(tk.END, f"✅ {result.get('imported', 0)} contacts importés.\n")
            self.log.insert(tk.END, f"⚠️ {result.get('skipped', 0)} ignorés.\n")
            self.log.insert(tk.END, f"❌ {len(result.get('errors', []))} erreurs.\n")
            self.log.see(tk.END)
            self.root.after(0, lambda: messagebox.showinfo(
                "Résultat",
                f"{result.get('imported', 0)} contacts importés.\n"
                f"{result.get('skipped', 0)} ignorés.\n"
                f"Erreurs : {len(result.get('errors', []))}"
            ))
        except Exception as e:
            self.log.insert(tk.END, f"❌ Erreur générale : {str(e)}\n")
            self.log.see(tk.END)
            self.root.after(0, lambda: messagebox.showerror("Erreur", str(e)))

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
