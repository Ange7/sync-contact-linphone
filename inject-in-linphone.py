import sqlite3
import vobject
import os
import re
from datetime import datetime

# === CONFIGURATION ===
VCF_PATH = "contacts.vcf"
DB_PATH = os.path.expanduser("~/.local/share/linphone/friends.db")
SIP_DOMAIN = "sbc6.fr.sip.ovh"
LOG_FILE = f"log_friends_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

def clean_phone_number(raw):
    number = re.sub(r"[^\d+]", "", raw)
    if number.startswith("+"):
        return number
    elif number.startswith("06") or number.startswith("07"):
        return "+33" + number[1:]
    return None

def log_message(message):
    print(message)
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(message + "\n")

def build_manual_vcard(fn, sip_uri, email=None, role=None):
    vcard_lines = [
        "BEGIN:VCARD",
        "VERSION:4.0",
        f"IMPP:{sip_uri}",
        f"FN:{fn}",
    ]
    if email:
        vcard_lines.append(f"EMAIL:{email}")
    if role:
        vcard_lines.append(f"ROLE:{role}")
    vcard_lines.append("END:VCARD")
    return "\n".join(vcard_lines)

def parse_vcf(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        vcf_data = f.read()

    contacts = []
    lines = vcf_data.splitlines()
    buffer = []
    inside_vcard = False

    for line in lines:
        if line.startswith("BEGIN:VCARD"):
            buffer = [line]
            inside_vcard = True
        elif line.startswith("END:VCARD"):
            buffer.append(line)
            vcard_block = "\n".join(buffer)
            try:
                for vcard in vobject.readComponents(vcard_block):
                    tel_field = getattr(vcard, 'tel', None)
                    fn_field = getattr(vcard, 'fn', None)
                    email_field = getattr(vcard, 'email', None)
                    org_field = getattr(vcard, 'org', None)

                    if tel_field:
                        number = clean_phone_number(tel_field.value)
                        if number:
                            sip_uri = f"sip:{number}@{SIP_DOMAIN}"
                            fn = fn_field.value if fn_field else number
                            email = email_field.value if email_field else None
                            org = org_field.value[0] if org_field else None
                            clean_vcard = build_manual_vcard(fn, sip_uri, email, org)
                            contacts.append((sip_uri, clean_vcard))
                            log_message(f"✅ Contact prêt : {fn} -> {sip_uri}")
                        else:
                            log_message(f"❌ Numéro invalide : {tel_field.value}")
                    else:
                        log_message("❌ Contact sans numéro.")
            except Exception as e:
                log_message(f"❌ Erreur parsing vCard : {str(e)}")
            inside_vcard = False
        elif inside_vcard:
            buffer.append(line)

    return contacts

def replace_contacts(db_path, contacts):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("DELETE FROM friends;")
    conn.commit()
    log_message("🧹 Tous les contacts existants ont été supprimés.")

    count = 0
    for sip_uri, vcard in contacts:
        try:
            cur.execute("""
                INSERT INTO friends (
                    friend_list_id, sip_uri, subscribe_policy, send_subscribe,
                    ref_key, vCard, vCard_etag, vCard_url, presence_received
                ) VALUES (1, ?, 0, 1, NULL, ?, NULL, NULL, 1)
            """, (sip_uri, vcard))
            count += 1
        except Exception as e:
            log_message(f"❌ Erreur DB pour {sip_uri} : {str(e)}")

    conn.commit()
    conn.close()
    log_message(f"\n✅ {count} contacts injectés dans Linphone.")

if __name__ == "__main__":
    print(f"📋 Import Linphone - Log : {LOG_FILE}\n")

    if not os.path.exists(DB_PATH):
        print("❌ Base SQLite introuvable :", DB_PATH)
    elif not os.path.exists(VCF_PATH):
        print("❌ Fichier VCF introuvable :", VCF_PATH)
    else:
        contacts = parse_vcf(VCF_PATH)
        if not contacts:
            log_message("❌ Aucun contact importable trouvé.")
        else:
            replace_contacts(DB_PATH, contacts)
