#!/usr/bin/env python3
"""Exercise failures that a superficially green documentation job would miss."""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


docs = load_module("check-docs")
examples = load_module("validate-examples")


class DocumentationTests(unittest.TestCase):
    def test_reference_links_images_and_duplicate_headings(self):
        links, anchors = docs.markdown_info(
            "# A **title**\n# A title\n[x][ref]\n![diagram](image.svg)\n\n[ref]: other.md#section\n"
        )
        self.assertEqual(set(links), {"other.md#section", "image.svg"})
        self.assertEqual(anchors, {"a-title", "a-title-1"})

    def test_code_examples_are_not_links(self):
        links, _ = docs.markdown_info(
            "`[code](missing.md)`\n\n```md\n[code](also-missing.md)\n```\n"
        )
        self.assertEqual(links, [])

    def test_missing_local_target_anchor_and_escape_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "README.md"
            path.write_text(
                "[missing](missing.md) [anchor](other.md#absent) [escape](../outside.md)"
            )
            (root / "other.md").write_text("# Existing")
            errors = docs.check_markdown(path, root)
            self.assertEqual(len(errors), 3)

    def test_percent_encoded_file_and_fragment_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "README.md"
            path.write_text(
                "[good](other%20file.md#caf%C3%A9) [external](https://example.invalid/no-network)"
            )
            (root / "other file.md").write_text("# Café")
            self.assertEqual(docs.check_markdown(path, root), [])

    def test_svg_accessibility_and_active_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "diagram.svg"
            valid = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-labelledby="t d"><title id="t">Title</title><desc id="d">Description</desc></svg>'
            path.write_text(valid)
            self.assertEqual(docs.check_svg(path, root), [])
            path.write_text(
                valid.replace(
                    "</svg>",
                    '<script>bad()</script><image href="https://example.invalid/x"/></svg>',
                )
            )
            self.assertEqual(len(docs.check_svg(path, root)), 2)
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            self.assertGreaterEqual(len(docs.check_svg(path, root)), 4)

    def test_svg_style_elements_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "diagram.svg"
            for css in (
                '@import "https://example.invalid/stylesheet.css";',
                'rect {fill: url("https://example.invalid/image.svg");}',
            ):
                with self.subTest(css=css):
                    path.write_text(
                        '<svg xmlns="http://www.w3.org/2000/svg">'
                        f"<style>{css}</style></svg>"
                    )
                    self.assertTrue(
                        any(
                            "style elements" in error
                            for error in docs.check_svg(path, root)
                        )
                    )

    def test_svg_escaped_style_attribute_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "diagram.svg"
            path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg">'
                r'<rect style="fill: u\72l(https://example.invalid/image.svg)"/>'
                "</svg>"
            )
            self.assertTrue(
                any("style attributes" in error for error in docs.check_svg(path, root))
            )


class RuntimeExamplesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose_schema = json.loads(
            (ROOT / ".github/schemas/compose.json").read_text()
        )
        cls.kubernetes_schema = json.loads(
            (ROOT / ".github/schemas/kubernetes.json").read_text()
        )
        cls.compose_source = examples.read_yaml(ROOT / "examples/docker/compose.yaml")[
            0
        ]
        cls.kubernetes_source = examples.read_yaml(
            ROOT / "examples/k3s/cloudflared.yaml"
        )

    def setUp(self):
        self.compose = copy.deepcopy(self.compose_source)
        self.kubernetes = copy.deepcopy(self.kubernetes_source)

    def test_current_examples_pass_and_use_same_image(self):
        self.assertEqual(
            examples.validate_compose(self.compose, self.compose_schema),
            examples.validate_kubernetes(self.kubernetes, self.kubernetes_schema),
        )

    def test_unknown_compose_key_fails_schema(self):
        self.compose["services"]["cloudflared"]["read_ony"] = True
        with self.assertRaises(jsonschema.ValidationError):
            examples.validate_compose(self.compose, self.compose_schema)

    def test_unknown_kubernetes_key_fails_schema(self):
        self.kubernetes[1]["spec"]["template"]["spec"]["containres"] = []
        with self.assertRaises(jsonschema.ValidationError):
            examples.validate_kubernetes(self.kubernetes, self.kubernetes_schema)

    def test_mutable_image_fails(self):
        self.compose["services"]["cloudflared"]["image"] = (
            "cloudflare/cloudflared:latest"
        )
        with self.assertRaisesRegex(ValueError, "pinned"):
            examples.validate_compose(self.compose, self.compose_schema)

    def test_embedded_token_and_secret_fail(self):
        self.compose["services"]["cloudflared"]["command"] = [
            "tunnel",
            "run",
            "--token",
            "synthetic-test-value",
        ]
        with self.assertRaisesRegex(ValueError, "token by file"):
            examples.validate_compose(self.compose, self.compose_schema)
        self.kubernetes.append(
            {"apiVersion": "v1", "kind": "Secret", "data": {"token": "synthetic"}}
        )
        with self.assertRaisesRegex(ValueError, "no embedded Secret"):
            examples.validate_kubernetes(self.kubernetes, self.kubernetes_schema)

    def test_wrong_probe_semantics_fail(self):
        self.kubernetes[1]["spec"]["template"]["spec"]["containers"][0][
            "livenessProbe"
        ]["httpGet"]["path"] = "/ready"
        with self.assertRaisesRegex(ValueError, "edge outage"):
            examples.validate_kubernetes(self.kubernetes, self.kubernetes_schema)

    def test_duplicate_yaml_keys_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.yaml"
            path.write_text("service: first\nservice: second\n")
            with self.assertRaisesRegex(ValueError, "Duplicate YAML key"):
                examples.read_yaml(path)

    def test_external_schema_references_fail_without_network(self):
        with self.assertRaisesRegex(ValueError, "only local references"):
            examples.validate_schema(
                {}, {"$ref": "https://example.invalid/schema.json"}
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
