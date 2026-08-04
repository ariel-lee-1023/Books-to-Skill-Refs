"""EPUB on the standard library: a zip of XHTML plus an OPF manifest.

No third-party package. Documents are read in *spine order* rather than in zip
order, because zip order is arbitrary and a book whose chapters arrive shuffled
would defeat every downstream assumption about structure.
"""

from __future__ import annotations

import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from ..exceptions import ParseFailure
from .base import ParsedDoc, decode
from .html import html_to_text

CONTAINER = "META-INF/container.xml"
NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
}
XHTML_TYPES = ("application/xhtml+xml", "text/html")


def _opf_path(archive: zipfile.ZipFile) -> str:
    try:
        root = ElementTree.fromstring(archive.read(CONTAINER))
    except (KeyError, ElementTree.ParseError) as exc:
        raise ParseFailure("EPUB has no readable META-INF/container.xml") from exc
    rootfile = root.find(".//container:rootfile", NS)
    if rootfile is None or not rootfile.get("full-path"):
        raise ParseFailure("EPUB container declares no rootfile")
    return rootfile.get("full-path", "")


def _spine_documents(archive: zipfile.ZipFile, opf: str) -> list[str]:
    root = ElementTree.fromstring(archive.read(opf))
    base = posixpath.dirname(opf)

    manifest: dict[str, tuple[str, str]] = {}
    for item in root.iterfind(".//opf:manifest/opf:item", NS):
        item_id, href = item.get("id"), item.get("href")
        if item_id and href:
            manifest[item_id] = (href, item.get("media-type", ""))

    ordered: list[str] = []
    for ref in root.iterfind(".//opf:spine/opf:itemref", NS):
        entry = manifest.get(ref.get("idref", ""))
        if not entry:
            continue
        href, media_type = entry
        if media_type and media_type not in XHTML_TYPES:
            continue
        ordered.append(posixpath.normpath(posixpath.join(base, href)) if base else href)

    if not ordered:  # malformed spine: fall back to every XHTML in the manifest
        ordered = [posixpath.normpath(posixpath.join(base, href)) if base else href
                   for href, media_type in manifest.values()
                   if media_type in XHTML_TYPES]
    return ordered


def parse(path: Path) -> ParsedDoc:
    try:
        with zipfile.ZipFile(path) as archive:
            opf = _opf_path(archive)
            names = set(archive.namelist())
            chunks: list[str] = []
            for href in _spine_documents(archive, opf):
                if href not in names:
                    continue
                chunks.append(html_to_text(decode(archive.read(href))))
    except zipfile.BadZipFile as exc:
        raise ParseFailure(f"{path.name} is not a readable .epub ({exc})") from exc

    if not chunks:
        raise ParseFailure(f"{path.name} contains no readable documents")

    return ParsedDoc(text="\n\n".join(c.strip() for c in chunks if c.strip()))
