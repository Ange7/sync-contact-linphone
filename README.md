# iCloud to Linphone Contact Sync

This repository provides a simple toolchain to:

- Export your iCloud contacts to a local `contacts.vcf` file
- Optionally synchronize them with a CardDAV server
- Inject those contacts into the Linphone softphone application

This setup allows you to keep your Linphone contacts synchronized with your iCloud account (and optionally your own CardDAV server) without relying on third-party services.

---

## 📦 Requirements

- Python 3.8 or newer
- An iCloud account (supports 2FA)
- Optionally: a CardDAV server (e.g. Nextcloud)
- Linphone desktop app (using `friends.db`)
- Dependencies listed in `requirements.txt`

---

## 🚀 Usage

### 1. Export iCloud Contacts

Launch the graphical interface to connect to your iCloud account and export your contacts:

```bash
python3 launch.py
```

You will be asked to provide:

- Your Apple ID and password
- (Optionally) your CardDAV server URL, username, and password

At the bottom of the interface, you can check:

> 📁 **Export to contacts.vcf only (no sync)**

If checked, the script will:

- Connect to iCloud
- Fetch all your contacts
- Create (or overwrite) a local `contacts.vcf` file in the working directory

If not checked, the same `.vcf` file will also be pushed to your CardDAV server.

---

### 2. Inject Contacts into Linphone

After generating `contacts.vcf`, use the command below to inject contacts into Linphone:

```bash
python3 inject-in-linphone.py
```

This script will:

- Read the `contacts.vcf` file
- Format contacts for Linphone (name, number, company, etc.)
- Clean the existing contacts in `friends.db`
- Insert the new ones with proper vCard structure (v4.0)

You can now open Linphone and see all your iCloud contacts listed.

---

## 🔁 Recommended Workflow

Whenever you want to refresh your Linphone contacts:

1. Run `python3 launch.py` to get the latest from iCloud
2. Run `python3 inject-in-linphone.py` to inject them into Linphone

This keeps your SIP contacts always up to date.

---

## 🔐 Privacy Notice

All credentials are used locally on your device.

- Your iCloud login is only used through the official Apple API via `pyicloud`
- Your contacts are saved to a local `.vcf` file
- Synchronization with CardDAV is optional and under your full control

---

## 🧑‍💻 Author

Developed by Alexandre Russo  
Feel free to modify and adapt this for your own setup.

---

## 📄 License

This project is licensed under the GNU GENERAL PUBLIC License.
