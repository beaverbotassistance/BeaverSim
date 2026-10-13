"""Readers by data type and by metadata standard. They know nothing about sites or sources.

``RECORDS`` registers every metadata-record format: the function that reads it, the file name a
source client saves it under (next to the data files), and its media type. A new format is one
entry here; the builder and the evidence gatherer use this table only.

A record reader returns ``{package_id, title, licence, rights, creators, dates, bounds, methods,
entities}``, where ``entities`` maps a file name to ``{url, pid, size, checksum: (algorithm, hex) |
None, attributes: [...]}``; optional ``size_exact: False`` when the record rounds sizes.
"""
from data_acquisition.readers import eml, pangaea

RECORDS = {
    "eml": {"read": eml.read, "file": "metadata.xml", "media": "application/xml"},
    "pangaea_tab": {"read": pangaea.read, "file": "metadata.tab", "media": "text/tab-separated-values"},
}
RECORD_FILES = {spec["file"]: name for name, spec in RECORDS.items()}   # file name -> format
