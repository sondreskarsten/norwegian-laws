"""Focused mutation checks on exact retained source documents, not invented laws."""
import copy
import json
import re
import unittest
from pathlib import Path
from lovdata_loader import source_body_gate as gate
from xml.etree import ElementTree as ET
from lovdata_loader.source_body import capture_source_body
import hashlib


FIXTURES = Path(__file__).parent / "fixtures/source_body"
MEMBERS = {r["name"]: r for r in json.loads((FIXTURES / "list-source-members.json").read_text(encoding="utf-8"))}

def captured(raw):
    """Independent fixture serializer; no producer runtime dependency."""
    root = ET.fromstring(raw); head = root.find("head"); body = root.find("body")
    def node(e):
        children = [e.text] if e.text else []
        for c in e:
            children.append(node(c))
            if c.tail: children.append(c.tail)
        return {"tag": e.tag, "attributes": dict(e.attrib), "children": children}
    tree = node(body.find('main[@class="documentBody"]'))
    context = {"html_lang": root.get("lang"), "html_attributes": dict(root.attrib), "head_attributes": dict(head.attrib),
               "body_attributes": dict(body.attrib), "source_base": head.find("base").get("href"),
               "refid": ''.join(root.find('.//dd[@class="refid"]').itertext()).strip()}
    return {"contract": gate.CONTRACT, "member_sha256": hashlib.sha256(raw).hexdigest(), "context": context, "root": tree,
            "body_sha256": gate._digest(tree), "semantic_sha256": gate._digest([gate.CONTRACT, context, tree])}

def fixture(name):
    row = MEMBERS[name]; raw = (FIXTURES / row["retained_file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == row["member_sha256"]
    model = captured(raw)
    if "body_sha256" in row:
        assert model["body_sha256"] == row["body_sha256"] and model["semantic_sha256"] == row["semantic_sha256"]
    return raw, model, {"expected_refid": row["refid"], "expected_member_sha256": row["member_sha256"], "source_occurrence_id": row["source_occurrence_id"]}


def rehash(model):
    model["body_sha256"] = gate._digest(model["root"])
    model["semantic_sha256"] = gate._digest([gate.CONTRACT, model["context"], model["root"]])


class SourceListTests(unittest.TestCase):
    def setUp(self):
        self.raw, self.model, self.kwargs = fixture("nested-decimal-alpha")
        self.result = gate.qualify_source_body(self.raw, self.model, **self.kwargs)
        self.assertEqual(self.result["report"]["status"], "passed")

    def rejected_render(self, rendered, *, stylesheet=None, model=None):
        with self.assertRaises(gate.BodyRejected):
            gate.verify_rendered_body(rendered, model or self.model,
                                      stylesheet=self.result["stylesheet"] if stylesheet is None else stylesheet)

    def test_source_bound_full_body_and_nested_lists(self):
        self.assertEqual(capture_source_body(self.raw), self.model)
        gate.verify_rendered_body(self.result["html"], self.model, stylesheet=self.result["stylesheet"])
        self.assertEqual(self.result["report"]["element_counts"]["ol"], 3)
        self.assertEqual(self.result["report"]["element_counts"]["li"], 14)

    def test_marker_value_type_and_start_tampering(self):
        original = self.result["html"]
        mutations = {
            "source-marker": original.replace('data-name="1."', 'data-name="9."', 1),
            "ordinal-value": original.replace('value="1"', 'value="2"', 1),
            "declared-type": original.replace('type="1"', 'type="a"', 1),
            "invented-start": original.replace('<ol ', '<ol start="2" ', 1),
            "remove-marker": original.replace(' data-name="1."', '', 1),
            "replace-boundary": original.replace('<ol class="defaultList" type="a">', '<ul class="defaultList" type="a">', 1).replace('</ol>', '</ul>', 1),
            "remove-boundary": original.replace('</ol>', '', 1),
        }
        for name, rendered in mutations.items():
            with self.subTest(name=name):
                self.assertNotEqual(rendered, original)
                self.rejected_render(rendered)

    def test_well_formed_item_reordering_rejected(self):
        altered = copy.deepcopy(self.model)
        outer = next(n for n, _, _ in gate._walk(altered["root"]) if n["tag"] == "ol")
        outer["children"][0], outer["children"][1] = outer["children"][1], outer["children"][0]
        notes, refs, _ = gate._grammar(altered["root"], altered["context"])
        self.rejected_render(gate._render(altered["root"], altered["context"], notes, refs))

    def test_well_formed_boundary_reparenting_rejected(self):
        altered = copy.deepcopy(self.model)
        lists = [n for n, _, _ in gate._walk(altered["root"]) if n["tag"] == "ol"]
        lists[2]["children"].append(lists[1]["children"].pop())
        notes, refs, _ = gate._grammar(altered["root"], altered["context"])
        self.rejected_render(gate._render(altered["root"], altered["context"], notes, refs))

    def test_css_marker_replacement_is_rejected(self):
        changed = self.result["stylesheet"].replace('content:attr(data-name)', 'content:counter(list-item)')
        self.assertNotEqual(changed, self.result["stylesheet"])
        self.rejected_render(self.result["html"], stylesheet=changed)

    def test_rehashed_model_cannot_change_source_marker(self):
        altered = copy.deepcopy(self.model)
        next(n for n, _, _ in gate._walk(altered["root"]) if n["tag"] == "li")["attributes"]["data-name"] = "9."
        rehash(altered)
        result = gate.qualify_source_body(self.raw, altered, **self.kwargs)
        self.assertEqual(result["report"]["reasons"][0]["code"], "source_model_mismatch")
        self.assertIsNone(result["html"])

    def test_unsupported_start_and_unknown_marker_fail_closed(self):
        for attr, value in (("start", "3"), ("reversed", "reversed"), ("type", "greek")):
            with self.subTest(attr=attr):
                altered = copy.deepcopy(self.model)
                next(n for n, _, _ in gate._walk(altered["root"]) if n["tag"] == "ol")["attributes"][attr] = value
                with self.assertRaises(gate.BodyRejected):
                    gate._grammar(altered["root"], altered["context"])
        for attrs in ({"value": "1"}, {"data-name": "1.", "value": "-1"}, {"data-name": "1.", "value": "01"}, {"data-name": "§1", "value": "1"}):
            with self.subTest(attrs=attrs):
                altered = copy.deepcopy(self.model)
                next(n for n, _, _ in gate._walk(altered["root"]) if n["tag"] == "li")["attributes"] = attrs
                with self.assertRaises(gate.BodyRejected):
                    gate._grammar(altered["root"], altered["context"])

    def test_hyphen_fields_are_source_bound(self):
        raw, model, kwargs = fixture("two-hyphens")
        result = gate.qualify_source_body(raw, model, **kwargs)
        self.assertEqual(result["report"]["status"], "passed")
        for before, after in (('data-name="-"', 'data-name="•"'), ('data-li-identifier="-"', 'data-li-identifier="*"')):
            with self.subTest(before=before):
                self.rejected_render(result["html"].replace(before, after, 1), stylesheet=result["stylesheet"], model=model)
        altered = copy.deepcopy(model)
        next(n for n, _, _ in gate._walk(altered["root"]) if n["tag"] == "li")["attributes"]["data-li-identifier"] = "*"
        with self.assertRaises(gate.BodyRejected):
            gate._grammar(altered["root"], altered["context"])

    def test_unnamed_disc_and_nonunit_initial_value(self):
        for name in ("unnamed-disc", "nonunit-start"):
            raw, model, kwargs = fixture(name)
            result = gate.qualify_source_body(raw, model, **kwargs)
            self.assertEqual(result["report"]["status"], "passed")
            gate.verify_rendered_body(result["html"], model, stylesheet=result["stylesheet"])
            if name == "nonunit-start":
                self.assertIn('data-name="14." value="14"', result["html"])
                self.assertNotIn('start=', result["html"])
            else:
                self.assertIn('<ul class="defaultList">', result["html"])
                self.assertIn('list-style-type:disc', result["stylesheet"])

    def test_original_v2_payload_hashes_remain_exact(self):
        for name, row in MEMBERS.items():
            if "expected_v2" not in row: continue
            with self.subTest(name=name):
                raw, model, kwargs = fixture(name)
                result = gate.qualify_source_body(raw, model, **kwargs)
                self.assertEqual(result["report"]["status"], "passed")
                self.assertEqual(hashlib.sha256(result["html"].encode()).hexdigest(), row["expected_v2"]["html_sha256"])
                self.assertEqual(hashlib.sha256(result["stylesheet"].encode()).hexdigest(), row["expected_v2"]["stylesheet_sha256"])

    def test_main_identity_absence_does_not_hide_wrong_header_or_unsupported_content(self):
        raw, model, kwargs = fixture("absent-main-identity")
        self.assertNotIn("data-lovdata-URL", model["root"]["attributes"])
        gate.verify_source_body(raw, model, **kwargs)
        result = gate.qualify_source_body(raw, model, **kwargs)
        self.assertEqual(result["report"]["reasons"][0]["code"], "unsupported_form")
        self.assertIsNone(result["html"])
        with self.assertRaises(gate.BodyRejected):
            gate.verify_source_body(raw, model, **{**kwargs, "expected_refid": "forskrift/1905-11-15-1"})

    def test_ins_identity_still_requires_exact_header_match(self):
        raw, model, kwargs = fixture("ins-main-identity")
        self.assertEqual(gate.qualify_source_body(raw, model, **kwargs)["report"]["status"], "passed")
        for location in ("INS/forskrift/1905-11-15-2", "UNKNOWN/" + kwargs["expected_refid"], ""):
            with self.subTest(location=location):
                altered = copy.deepcopy(model)
                altered["root"]["attributes"]["data-lovdata-URL"] = location
                with self.assertRaises(gate.BodyRejected):
                    gate._grammar(altered["root"], altered["context"])

    def test_unrelated_rejections_do_not_emit_readable_body(self):
        for name in ("rejected-default-paragraph", "rejected-link-context"):
            with self.subTest(name=name):
                raw, model, kwargs = fixture(name)
                result = gate.qualify_source_body(raw, model, **kwargs)
                self.assertEqual(result["report"]["status"], "rejected")
                self.assertIsNone(result["html"])
                self.assertIsNone(result["stylesheet"])

    def test_actual_heading_text_and_class_cannot_change(self):
        raw, model, kwargs = fixture("heading-baseline")
        result = gate.qualify_source_body(raw, model, **kwargs)
        self.assertEqual(result["report"]["status"], "passed")
        self.assertEqual(result["report"]["element_counts"]["section"], 4)
        self.assertEqual(result["html"].count('<h3 class="legalArticleHeader">'), 7)
        for before, after in (('class="legalArticleTitle"', 'class="legalArticleValue"'), ('Grunnlaget for allmenngjøring', 'Endret overskrift')):
            with self.subTest(before=before):
                self.assertIn(before, result["html"])
                self.rejected_render(result["html"].replace(before, after, 1), stylesheet=result["stylesheet"], model=model)


if __name__ == "__main__":
    unittest.main(verbosity=2)
