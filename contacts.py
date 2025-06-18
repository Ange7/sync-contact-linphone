import requests
from urllib.parse import urljoin
from requests.auth import HTTPBasicAuth
from vobject import readOne

class ContactsImporter:
    def __init__(self, carddav_url, carddav_user, carddav_pass):
        self.carddav_url = carddav_url
        self.carddav_user = carddav_user
        self.carddav_pass = carddav_pass
        self.auth = HTTPBasicAuth(self.carddav_user, self.carddav_pass)

    def get_addressbook_url(self):
        return self.carddav_url if self.carddav_url.endswith('/') else self.carddav_url + '/'

    def delete_all_contacts(self):
        url = self.get_addressbook_url()
        headers = {
            "Depth": "1",
            "Content-Type": "application/xml"
        }
        propfind_body = "<?xml version='1.0'?><d:propfind xmlns:d='DAV:'><d:prop><d:getetag/></d:prop></d:propfind>"

        response = requests.request("PROPFIND", url, headers=headers, data=propfind_body, auth=self.auth)
        if response.status_code not in (200, 207):
            print(f"Erreur PROPFIND: {response.status_code}")
            return

        from xml.etree import ElementTree as ET
        tree = ET.fromstring(response.content)
        ns = {'d': 'DAV:'}
        hrefs = [el.text for el in tree.findall('.//d:response/d:href', ns) if el.text and not el.text.endswith('/')]

        for href in hrefs:
            delete_url = urljoin(url, href)
            try:
                del_resp = requests.delete(delete_url, auth=self.auth)
                if del_resp.status_code not in (200, 204):
                    print(f"Erreur suppression {href} : {del_resp.status_code}")
            except Exception as e:
                print(f"Exception suppression {href} : {e}")

    def import_vcards(self, vcf_path):
        self.delete_all_contacts()
        url = self.get_addressbook_url()
        imported = 0
        skipped = 0
        errors = []

        with open(vcf_path, encoding="utf-8") as f:
            vcard_data = f.read()
        vcards = vcard_data.strip().split("END:VCARD")
        for raw in vcards:
            raw = raw.strip()
            if not raw:
                continue
            try:
                full = raw + "\nEND:VCARD"
                card = readOne(full)
                if not hasattr(card, 'fn'):
                    skipped += 1
                    continue
                headers = {
                    "Content-Type": "text/vcard"
                }
                uid = getattr(card, 'uid', None)
                uid_val = uid.value if uid else f"generated-{imported}"
                put_url = url + uid_val + ".vcf"
                put_resp = requests.put(put_url, data=full.encode("utf-8"), headers=headers, auth=self.auth)
                if put_resp.status_code not in (200, 201, 204):
                    raise Exception(f"HTTP {put_resp.status_code}")
                imported += 1
            except Exception as e:
                errors.append(str(e))

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors
        }
