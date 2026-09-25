"""Observed legacy reconstructions; labels are not verified legal dates.

Catalog captured from public GitHub refs on 2026-09-25. Orphan v2000 and
future-year refs are deliberately excluded. Pin readers to these commits so
later legacy tag rebuilds do not silently change the selected comparison.
"""

LEGACY_VERSION_REFS = {
    "v2001": "5c8fbd29c7d0ebd23685bd13d9d3af79dc5c3c5e",
    "v2002": "46b02a1967fa3cf728590262511c89c938f0ff7d",
    "v2003": "dc44fe73c3a3c860c95e99dcab8d363704d2d7c0",
    "v2004": "d953213d240550c057329b154be1da6346eeefa3",
    "v2005": "40ccca141661ecd747ce48987ec3e3361b2a8844",
    "v2006": "011dc1833d83a8386cca5e1edc8ff5fba32674cd",
    "v2007": "a38654ef2cac6c5bfe8ecd7c09522022d7cad361",
    "v2008": "3374530ced584b9c5a5073143e3458049ae6a93d",
    "v2009": "119fdadb53f801870c6a88ea5ff66ec307c1b365",
    "v2010": "2acff3bc134462defaacd1433d9cd363b58aa3d7",
    "v2011": "69eefdb106a4b7a379ab0ecd9e6f490ad852526d",
    "v2012": "f447f5c423a997db8e276c313aa74e4b6bd51933",
    "v2013": "68299e105e21cbc29af1f1fe6a08a870490136f2",
    "v2014": "3ad57c417fd877a9b2b10ba8b08375febf4be490",
    "v2015": "f327ae8f6c6e7575fe02cc142554bb26b774c6b8",
    "v2016": "49e5140096f8b552d3525f1d5cf1228ba003a978",
    "v2017": "03d6d0f2fba897f681fdb7a5371d82267b1bc13e",
    "v2018": "1ce74661c39b1f8addc4b7d753f4f2a05f63968c",
    "v2019": "da5aa7d485eb33be2a319426343ddbb86ce71318",
    "v2020": "861fc8232103bb96b4855c936998e5081d823622",
    "v2021": "78f8e6ad8c63185207809fd85585437d34e93ebc",
    "v2022": "efc47b195e7b4b78c5900e4440b425fcd93c733c",
    "v2023": "2a073cc505669f0366f803aa36f8d6f286319f53",
    "v2024": "5375454b5a95be70a3742a3eefb819d75cb1f5be",
    "v2025": "e594d138414d3d561ece67e1626f72210919cafb",
    "v2026": "096496cd477308d5df2a6573a31ef3ab3a021af6"
}


def supported_version_tags(requested=None):
    """Return catalog order, optionally narrowed by requested labels."""
    return [tag for tag in LEGACY_VERSION_REFS if requested is None or tag in requested]
