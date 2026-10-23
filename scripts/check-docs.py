#!/usr/bin/env python3
"""Check repository-local Markdown links and accessible, self-contained SVGs."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt


class HTMLLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value and name in {"href", "src"}:
                self.links.append(value)
            if value and (name == "id" or (tag == "a" and name == "name")):
                self.anchors.add(value)


def markdown_info(text: str) -> tuple[list[str], set[str]]:
    tokens = MarkdownIt("commonmark").parse(text)
    links: list[str] = []
    anchors: set[str] = set()
    html = HTMLLinks()
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            inline = tokens[index + 1]
            title = "".join(
                child.content
                for child in inline.children or []
                if child.type in {"text", "code_inline", "image"}
            )
            slug = "".join(
                char
                for char in title.lower()
                if char in " -_" or unicodedata.category(char)[0] in "LNM"
            )
            slug = slug.replace(" ", "-")
            anchor, suffix = slug, 0
            while anchor in anchors:
                suffix += 1
                anchor = f"{slug}-{suffix}"
            anchors.add(anchor)
        for child in [token, *(token.children or [])]:
            if child.type == "link_open":
                links.append(child.attrGet("href") or "")
            elif child.type == "image":
                links.append(child.attrGet("src") or "")
            elif child.type in {"html_inline", "html_block"}:
                html.feed(child.content)
    return links + html.links, anchors | html.anchors


def check_markdown(path: Path, root: Path) -> list[str]:
    links, _ = markdown_info(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for link in links:
        try:
            parsed = urlsplit(link)
        except ValueError:
            errors.append(f"{path.relative_to(root)}: invalid link {link!r}")
            continue
        if parsed.scheme or parsed.netloc:
            continue  # External availability must not make pull requests flaky.
        target = (
            (
                root / unquote(parsed.path).lstrip("/")
                if parsed.path.startswith("/")
                else path.parent / unquote(parsed.path)
            )
            if parsed.path
            else path
        )
        target = target.resolve()
        if not target.is_relative_to(root):
            errors.append(f"{path.relative_to(root)}: link escapes repository: {link}")
        elif not target.exists():
            errors.append(f"{path.relative_to(root)}: missing local target: {link}")
        elif parsed.fragment and target.suffix.lower() == ".md":
            _, anchors = markdown_info(target.read_text(encoding="utf-8"))
            if unquote(parsed.fragment) not in anchors:
                errors.append(
                    f"{path.relative_to(root)}: missing Markdown anchor: {link}"
                )
    return errors


def check_svg(path: Path, root: Path) -> list[str]:
    label = str(path.relative_to(root))
    source = path.read_text(encoding="utf-8")
    if re.search(r"<!DOCTYPE|<!ENTITY", source, re.IGNORECASE):
        return [f"{label}: SVG must not declare entities or a doctype"]
    try:
        tree = ET.fromstring(source)
    except ET.ParseError as error:
        return [f"{label}: invalid SVG XML: {error}"]
    errors: list[str] = []
    ns = "{http://www.w3.org/2000/svg}"
    if tree.tag != ns + "svg":
        errors.append(f"{label}: root must be an SVG in the SVG namespace")
    try:
        values = [
            float(value)
            for value in tree.attrib.get("viewBox", "").replace(",", " ").split()
        ]
        if len(values) != 4 or values[2] <= 0 or values[3] <= 0:
            raise ValueError
    except ValueError:
        errors.append(f"{label}: missing or invalid viewBox")
    for name in ("title", "desc"):
        node = tree.find(ns + name)
        if node is None or not "".join(node.itertext()).strip():
            errors.append(f"{label}: missing accessible {name}")
    ids = {node.attrib["id"] for node in tree.iter() if "id" in node.attrib}
    if tree.attrib.get("role") != "img" or not tree.attrib.get("aria-labelledby"):
        errors.append(f"{label}: requires role=img and aria-labelledby")
    elif not set(tree.attrib["aria-labelledby"].split()) <= ids:
        errors.append(f"{label}: aria-labelledby references an absent element")
    for node in tree.iter():
        if node.tag.rsplit("}", 1)[-1] in {"script", "foreignObject"}:
            errors.append(f"{label}: active SVG content is not allowed")
        if node.tag.rsplit("}", 1)[-1].lower() == "style":
            errors.append(f"{label}: SVG style elements are not allowed")
        for key, value in node.attrib.items():
            local_name = key.rsplit("}", 1)[-1]
            # Presentation attributes suffice for these diagrams; rejecting CSS
            # avoids imports and escaped URLs that need a complete CSS parser.
            if local_name.lower() == "style":
                errors.append(f"{label}: SVG style attributes are not allowed")
            if local_name.lower().startswith("on"):
                errors.append(f"{label}: event handlers are not allowed")
            if local_name == "href" and not value.startswith("#"):
                errors.append(f"{label}: external SVG resources are not allowed")
            for resource in re.findall(r"url\(\s*['\"]?([^)'\"]+)", value):
                if not resource.startswith("#"):
                    errors.append(f"{label}: external SVG resources are not allowed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    root = args.root.resolve()
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
        )
        .decode()
        .split("\0")
    )
    paths = sorted(
        {
            root / name
            for name in names
            if name and Path(name).suffix.lower() in {".md", ".svg"}
        }
    )
    errors: list[str] = []
    for path in paths:
        if path.is_symlink():
            errors.append(
                f"{path.relative_to(root)}: document symlinks are not supported"
            )
        else:
            errors.extend(
                check_markdown(path, root)
                if path.suffix.lower() == ".md"
                else check_svg(path, root)
            )
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"Validated local links, Markdown anchors and SVG accessibility in {len(paths)} documents."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
