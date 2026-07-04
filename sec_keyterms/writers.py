"""Serialize extraction records to JSON and XML."""
from __future__ import annotations

import json
import pathlib
import xml.etree.ElementTree as ET
from xml.dom import minidom


def write_json(records: list[dict], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def write_xml(records: list[dict], path: pathlib.Path) -> None:
    root = ET.Element("filings", attrib={"count": str(len(records))})
    for rec in records:
        filing = ET.SubElement(root, "filing")
        meta = ET.SubElement(filing, "metadata")
        for key in ("accession_number", "form_type", "date_filed", "cik",
                    "company_name_edgar", "document_url", "extraction_status"):
            el = ET.SubElement(meta, key)
            el.text = str(rec.get(key, "") or "")
        terms = ET.SubElement(filing, "key_terms")
        for key, val in rec.get("key_terms", {}).items():
            el = ET.SubElement(terms, key)
            el.text = "" if val is None else str(val)
        if rec.get("missing_fields"):
            missing = ET.SubElement(filing, "missing_fields")
            for f in rec["missing_fields"]:
                ET.SubElement(missing, "field").text = f

    pretty = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty, encoding="utf-8")
