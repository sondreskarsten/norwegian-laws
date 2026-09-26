"""Focused source-fidelity checks for three digest-bound public examples."""
from __future__ import annotations

import copy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import unittest

from lovdata_loader.source_body import capture_source_body, canonical_bytes, SourceBodyError
from lovdata_loader.source_body_gate import (
    BodyRejected, CONTRACT, SOURCE_BODY_CSS, qualify_source_body, verify_rendered_body, verify_source_body,
)

FIXTURES = Path(__file__).parent / "fixtures" / "source_body"
MEMBERS = json.loads((FIXTURES / "source-members.json").read_text(encoding="utf-8"))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def rehash(model):
    model["body_sha256"] = digest(canonical_bytes(model["root"]))
    model["semantic_sha256"] = digest(canonical_bytes([CONTRACT, model["context"], model["root"]]))


def nodes(root):
    yield root
    for child in root["children"]:
        if isinstance(child, dict):
            yield from nodes(child)


def qualify(raw, row, model=None):
    return qualify_source_body(raw, model if model is not None else capture_source_body(raw),
                               expected_member_sha256=digest(raw), expected_refid=row["refid"],
                               source_occurrence_id=row["source_occurrence_id"])


class SourceBodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {row["refid"]: (row, (FIXTURES / row["retained_file"]).read_bytes()) for row in MEMBERS}

    def reject(self, result, code):
        self.assertEqual(result["report"]["status"], "rejected")
        self.assertEqual(result["report"]["reasons"][0]["code"], code)
        self.assertIsNone(result["html"])
        self.assertIsNone(result["stylesheet"])

    def test_three_real_bound_sources_and_deterministic_artifacts(self):
        for refid, (row, raw) in self.cases.items():
            with self.subTest(refid=refid):
                self.assertEqual(digest(raw), row["member_sha256"])
                model = capture_source_body(raw)
                result = qualify(raw, row, model)
                self.assertEqual(result["report"]["status"], "passed", result)
                self.assertEqual(model, capture_source_body(raw))
                self.assertEqual(result, qualify(raw, row, json.loads(canonical_bytes(model))))
                verify_rendered_body(result["html"], model, stylesheet=result["stylesheet"])
                self.assertEqual(result["report"]["legal_state"], "not_assessed")
                self.assertEqual(result["report"]["document_completeness"], "not_assessed")
                self.assertIn('lang="' + model["context"]["html_lang"] + '"', result["html"])

    def test_rehashed_model_cannot_change_link_tail_or_order(self):
        row, raw = self.cases["lov/1687-04-15"]
        for change in ("link", "text", "order"):
            with self.subTest(change=change):
                model = capture_source_body(raw)
                if change == "link":
                    next(n for n in nodes(model["root"]) if n["tag"] == "a")["attributes"]["href"] += "-changed"
                elif change == "text":
                    paragraph = next(n for n in nodes(model["root"]) if n["attributes"].get("class") == "legalP")
                    paragraph["children"][0] += " changed"
                else:
                    model["root"]["children"][1:3] = reversed(model["root"]["children"][1:3])
                rehash(model)
                self.reject(qualify(raw, row, model), "source_model_mismatch")

    def test_catalog_binding_is_required(self):
        row, raw = self.cases["lov/1687-04-15"]
        result = qualify_source_body(raw, capture_source_body(raw), expected_member_sha256="0" * 64,
                                     expected_refid=row["refid"], source_occurrence_id=row["source_occurrence_id"])
        self.reject(result, "source_binding_mismatch")
        wrong = dict(row, refid="lov/1751-10-02")
        self.reject(qualify(raw, wrong), "source_binding_mismatch")

    def test_body_identity_and_base_context_cannot_be_rebound(self):
        row, raw = self.cases["lov/1687-04-15"]
        self.reject(qualify(raw.replace(b'https://lovdata.no/', b'https://example.org/'), row), "unsupported_context")
        self.reject(qualify(raw.replace(b'NL/lov/1687-04-15" id="dokument"', b'NL/lov/1751-10-02" id="dokument"'), row), "source_context_mismatch")

    def test_unsupported_source_forms_are_retained_but_not_rendered(self):
        row, raw = self.cases["lov/1687-04-15"]
        for insertion, reason in [(b'<ol class="defaultList" type="1"><li value="1">item</li></ol>', "unsupported_nesting"),
                                  (b'<img src="/asset.png" alt="diagram" />', "unsupported_form"),
                                  (b'<article class="futureLegalArticle">future text</article>', "unsupported_form")]:
            changed = raw.replace(b'</main>', insertion + b'</main>')
            model = capture_source_body(changed)
            self.assertEqual(len(model["root"]["children"]), len(capture_source_body(raw)["root"]["children"]) + 1)
            self.reject(qualify(changed, row, model), reason)
            proof = verify_source_body(changed, model, expected_member_sha256=digest(changed),
                expected_refid=row["refid"], source_occurrence_id=row["source_occurrence_id"])
            self.assertEqual((proof["status"], proof["rendering"]), ("verified", "not_assessed"))

    def test_inherited_context_is_retained_verified_and_not_silently_rendered(self):
        row, raw = self.cases["lov/1687-04-15"]
        for original, replacement, name in [(b'<body>', b'<body lang="nn" dir="rtl">', "body_attributes"),
                                            (b'<head>', b'<head data-extra="x">', "head_attributes"),
                                            (b'<html ', b'<html eu="" ', "html_attributes")]:
            with self.subTest(name=name):
                changed = raw.replace(original, replacement, 1)
                self.assertNotEqual(changed, raw)
                model = capture_source_body(changed)
                proof = verify_source_body(changed, model, expected_member_sha256=digest(changed),
                    expected_refid=row["refid"], source_occurrence_id=row["source_occurrence_id"])
                self.assertEqual(proof["status"], "verified")
                self.reject(qualify(changed, row, model), "unsupported_context")
                model["context"][name] = capture_source_body(raw)["context"][name]
                rehash(model)
                with self.assertRaises(BodyRejected) as rejected:
                    verify_source_body(changed, model, expected_member_sha256=digest(changed),
                        expected_refid=row["refid"], source_occurrence_id=row["source_occurrence_id"])
                self.assertEqual(rejected.exception.code, "source_context_mismatch")

    def test_unknown_attributes_and_values_fail_closed(self):
        row, raw = self.cases["lov/1687-04-15"]
        changed = raw.replace(b'<main ', b'<main onclick="alert(1)" ', 1)
        self.reject(qualify(changed, row), "unsupported_attribute")
        row, raw = self.cases["forskrift/1969-06-27-4"]
        changed = raw.replace(b'data-text-align="center"', b'data-text-align="justify"', 1)
        self.reject(qualify(changed, row), "unsupported_attribute_value")
        self.reject(qualify(raw.replace(b'<td ', b'<td data-unknown-rowspan="2" ', 1), row), "unsupported_attribute")

    def test_footnotes_use_unique_counters_not_repeated_visible_labels(self):
        row, raw = self.cases["forskrift/1969-06-27-4"]
        result = qualify(raw, row)
        self.assertEqual(result["report"]["status"], "passed")
        for key in ["1", "2"]:
            self.assertIn(f'id="source-body-note-{key}"', result["html"])
            self.assertIn(f'href="#source-body-note-{key}"', result["html"])
            self.assertIn(f'href="#source-body-ref-{key}-1"', result["html"])

    def test_missing_note_and_generated_id_collision_reject(self):
        row, raw = self.cases["forskrift/1969-06-27-4"]
        changed = raw.replace(b'data-unique-footnote-counter="1"', b'data-unique-footnote-counter="99"', 1)
        self.reject(qualify(changed, row), "missing_footnote_target")
        changed = raw.replace(b'id="paragraf-1-ledd-1"', b'id="source-body-note-1"', 1)
        self.assertNotEqual(raw, changed)
        self.reject(qualify(changed, row), "generated_id_collision")

    def test_table_topology_and_rendered_span_mutation_reject(self):
        row, raw = self.cases["forskrift/1969-06-27-4"]
        self.reject(qualify(raw.replace(b'colspan="4"', b'colspan="3"', 1), row), "invalid_table_topology")
        clamped_span = re.sub(b'<table>.*?</table>', b'<table><tbody><tr><td colspan="1001">cell</td></tr></tbody></table>', raw, count=1)
        self.reject(qualify(clamped_span, row), "invalid_table_topology")
        model = capture_source_body(raw)
        result = qualify(raw, row, model)
        with self.assertRaises(BodyRejected):
            verify_rendered_body(result["html"].replace('colspan="4"', 'colspan="3"', 1), model, stylesheet=SOURCE_BODY_CSS)

    def test_rendered_navigation_extra_markup_and_missing_css_reject(self):
        row, raw = self.cases["forskrift/1969-06-27-4"]
        model = capture_source_body(raw)
        result = qualify(raw, row, model)
        for mutated in [result["html"].replace('href="#source-body-note-1"', 'href="#source-body-note-2"', 1),
                        result["html"] + '<script>alert(1)</script>',
                        result["html"].replace('data-source-body-derived="backref"', 'data-source-body-derived="unknown"', 1)]:
            with self.assertRaises(BodyRejected):
                verify_rendered_body(mutated, model, stylesheet=SOURCE_BODY_CSS)
        with self.assertRaises(BodyRejected):
            verify_rendered_body(result["html"], model, stylesheet="")
        with self.assertRaises(BodyRejected):
            verify_rendered_body(result["html"].replace('lang="no"', 'lang="en"', 1), model, stylesheet=SOURCE_BODY_CSS)

    def test_unsafe_links_and_nested_anchors_reject(self):
        row, raw = self.cases["lov/1687-04-15"]
        self.reject(qualify(raw.replace(b'href="lov/2023-06-16-40"', b'href="javascript:alert(1)"'), row), "unsupported_link_target")
        changed = raw.replace(b'>16 juni 2023 nr. 40</a>', b'><i><a href="lov/2023-06-16-40">nested</a></i></a>')
        self.assertNotEqual(changed, raw)
        self.reject(qualify(changed, row), "unsupported_nesting")

    def test_malformed_entities_and_depth_limits_fail_before_rendering(self):
        row, raw = self.cases["lov/1687-04-15"]
        for changed in [raw.replace(b'</main>', b'</article></main>'),
                        raw.replace(b'<!DOCTYPE html>', b'<!DOCTYPE html [<!ENTITY x "value">]>'),
                        raw.replace(b'</main>', b'<article>' * 130 + b'</article>' * 130 + b'</main>')]:
            with self.assertRaises(SourceBodyError):
                capture_source_body(changed)
        model = capture_source_body(raw)
        model["root"]["children"].append({"tag": "article", "attributes": {}, "children": ["same"]})
        self.reject(qualify(raw, row, model), "model_binding_mismatch")

    def test_independent_consumer_also_rejects_entity_declarations(self):
        row, raw = self.cases["lov/1687-04-15"]
        model = capture_source_body(raw)
        changed = raw.replace(b'<!DOCTYPE html>', b'<!DOCTYPE html [<!ENTITY x "value">]>')
        model["member_sha256"] = digest(changed)
        self.reject(qualify(changed, row, model), "unsupported_node_kind")


if __name__ == "__main__":
    unittest.main()
