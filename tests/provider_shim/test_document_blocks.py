"""Shim v1.4.8: Anthropic `document` blocks (PDFs from Claude Code's Read tool).

A document block used to be an "unsupported content block" 400, and because the
block stays in history one PDF read broke every later turn. These tests pin the
translation (base64 PDF -> input_file, URL PDF -> input_file file_url, text ->
input_text), the never-400 degradation for every other variant (including unsafe
URLs), the SHIM_PDF_MODE=omit wording and its unrecognized-value WARNING. All bytes,
URLs and IDs are fabricated sentinels; no test asserts live backend acceptance.
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import json
import os
import time
import unittest
import uuid
from unittest import mock

from ._loopback_harness import (
    PRODUCTION_SHIM,
    MockResponsesServer,
    RealShim,
    _purge_in_process_reasoning_cache_seam,
    full_response_scenario,
)


_PDF_BYTES = b"%PDF-1.4 fabricated-provider-shim-pdf-SENTINEL_PDF_8Q"
_PDF_B64 = base64.b64encode(_PDF_BYTES).decode("ascii")
_PDF_URL = "https://docs.example.invalid/report.pdf?private=URL_SENTINEL_3K"
_FILE_ID = "file_DOCUMENT_SCOPED_SENTINEL_5M"
_TEXT_SENTINEL = "PLAIN_TEXT_DOCUMENT_SENTINEL_2J"


def _pdf(**extra):
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": _PDF_B64},
        **extra,
    }


def _expected_pdf_part():
    return {
        "type": "input_file",
        "filename": "document.pdf",
        "file_data": "data:application/pdf;base64," + _PDF_B64,
    }


class DocumentTranslationUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _purge_in_process_reasoning_cache_seam()
        name = "provider_shim_document_blocks_%s" % uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, PRODUCTION_SHIM)
        cls.shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.shim)

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.shim._client.aclose())

    def setUp(self):
        self.shim._DOCUMENT_OMIT_LOGGED.clear()

    def _input(self, messages):
        return self.shim._messages_to_input(messages)[0]

    def test_base64_pdf_in_user_content_becomes_input_file(self):
        items = self._input([{"role": "user", "content": [
            {"type": "text", "text": "summarize"}, _pdf(),
        ]}])
        self.assertEqual(items, [{"role": "user", "content": [
            {"type": "input_text", "text": "summarize"}, _expected_pdf_part(),
        ]}])

    def test_title_and_context_precede_the_file(self):
        items = self._input([{"role": "user", "content": [
            _pdf(title="Annual report", context="Uploaded by the user", citations={"enabled": True}),
        ]}])
        self.assertEqual(items[0]["content"], [
            {"type": "input_text",
             "text": "Document title: Annual report\nDocument context: Uploaded by the user"},
            _expected_pdf_part(),
        ])

    def test_pdf_inside_tool_result_uses_item_list_output(self):
        items = self._input([{"role": "user", "content": [{
            "type": "tool_result", "tool_use_id": "call_read_pdf",
            "content": [{"type": "text", "text": "PDF file read"}, _pdf()],
        }]}])
        self.assertEqual(items, [{
            "type": "function_call_output", "call_id": "call_read_pdf",
            "output": [{"type": "input_text", "text": "PDF file read"}, _expected_pdf_part()],
        }])

    def test_url_pdf_becomes_input_file_url(self):
        items = self._input([{"role": "user", "content": [
            {"type": "document", "source": {"type": "url", "url": _PDF_URL}},
        ]}])
        self.assertEqual(items[0]["content"], [{"type": "input_file", "file_url": _PDF_URL}])

    def test_text_documents_become_plain_text(self):
        doc = {"type": "document", "title": "Notes",
               "source": {"type": "text", "media_type": "text/plain", "data": _TEXT_SENTINEL}}
        items = self._input([{"role": "user", "content": [doc]}])
        self.assertEqual(items[0]["content"],
                         [{"type": "input_text", "text": "Document title: Notes\n\n" + _TEXT_SENTINEL}])
        # Text-only tool results keep the historical flat-string output.
        items = self._input([{"role": "user", "content": [{
            "type": "tool_result", "tool_use_id": "call_text_doc",
            "content": [{"type": "text", "text": "a"}, {**doc, "title": None}],
        }]}])
        self.assertEqual(items[0]["output"], "a\n" + _TEXT_SENTINEL)
        content_doc = {"type": "document", "source": {"type": "content", "content": [
            {"type": "text", "text": "one"}, {"type": "text", "text": "two"}]}}
        items = self._input([{"role": "user", "content": [content_doc]}])
        self.assertEqual(items[0]["content"], [{"type": "input_text", "text": "one\ntwo"}])

    def test_unknown_variants_degrade_to_a_note_logged_once_without_content(self):
        variants = [
            ("file", {"type": "document", "source": {"type": "file", "file_id": _FILE_ID}}),
            ("docx", {"type": "document", "source": {
                "type": "base64", "media_type": "application/msword", "data": _PDF_B64}}),
            ("bad-base64", {"type": "document", "source": {
                "type": "base64", "media_type": "application/pdf", "data": "abc==" + _TEXT_SENTINEL}}),
            ("no-source", {"type": "document", "payload": _TEXT_SENTINEL}),
            ("bad-url", {"type": "document", "source": {"type": "url", "url": "file:///" + _TEXT_SENTINEL}}),
        ]
        for name, block in variants:
            with self.subTest(variant=name):
                with self.assertLogs(self.shim.log, level="INFO") as captured:
                    items = self._input([{"role": "user", "content": [block, block]}])
                parts = items[0]["content"]
                self.assertEqual(len(parts), 2)
                for part in parts:
                    self.assertEqual(part["type"], "input_text")
                    self.assertIn("could not be passed to this model and was omitted", part["text"])
                logs = "\n".join(captured.output)
                omit_lines = [line for line in captured.output if "document block omitted" in line]
                self.assertEqual(len(omit_lines), 1, logs)  # once per variant, not per block
                for forbidden in (_PDF_B64, _FILE_ID, _TEXT_SENTINEL):
                    self.assertNotIn(forbidden, logs)
                    self.assertNotIn(forbidden, json.dumps(items))
        # Inside a tool result the note is plain text, so the output stays a string.
        items = self._input([{"role": "user", "content": [{
            "type": "tool_result", "tool_use_id": "call_x", "content": [variants[0][1]]}]}])
        self.assertIsInstance(items[0]["output"], str)
        self.assertIn("was omitted", items[0]["output"])

    def test_pdf_mode_omit_escape_hatch(self):
        with mock.patch.object(self.shim, "SHIM_PDF_MODE", "omit"):
            items = self._input([{"role": "user", "content": [
                _pdf(), {"type": "document", "source": {"type": "url", "url": _PDF_URL}}]}])
        for part in items[0]["content"]:
            self.assertEqual(part["type"], "input_text")
            # Configuration, not failure: the note names the setting.
            self.assertIn("omitted by shim configuration (SHIM_PDF_MODE=omit)", part["text"])
            self.assertNotIn("could not be passed", part["text"])
        self.assertNotIn(_PDF_B64, json.dumps(items))
        self.assertNotIn(_PDF_URL, json.dumps(items))

    def test_unsafe_pdf_urls_degrade_to_the_note(self):
        # Userinfo, a bad port, whitespace or control characters would earn a
        # backend 400 for the whole turn; they degrade to the omitted note instead.
        for url in ("https://user:URL_SENTINEL@docs.example.invalid/a.pdf",
                    "https://docs.example.invalid:99999/a.pdf",
                    "https://docs.example.invalid:port/a.pdf",
                    "https://docs.example.invalid/a b.pdf",
                    "https://docs.example.invalid/a\x01.pdf",
                    "https://docs.example.invalid/a\x7f.pdf",
                    "http:///no-host.pdf"):
            with self.subTest(url=url):
                items = self._input([{"role": "user", "content": [
                    {"type": "document", "source": {"type": "url", "url": url}}]}])
                part = items[0]["content"][0]
                self.assertEqual(part["type"], "input_text")
                self.assertIn("could not be passed to this model and was omitted", part["text"])
                self.assertNotIn(url, json.dumps(items))

    def test_large_base64_pdf_validates_quickly(self):
        # ~5 MB of fabricated base64: validation is one flat character-class scan.
        data = "QUJD" * (5 * 1024 * 1024 // 4)
        block = {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
        started = time.monotonic()
        items = self._input([{"role": "user", "content": [block]}])
        elapsed = time.monotonic() - started
        self.assertEqual(items[0]["content"][0]["type"], "input_file")
        self.assertLess(elapsed, 2.0)
        # Strict padding semantics are unchanged.
        for bad in ("QUJD=", "QUJ===", "QU=D", "QUJD QUJD", "QUJ"):
            with self.subTest(bad=bad):
                bad_block = {"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf", "data": bad}}
                part = self._input([{"role": "user", "content": [bad_block]}])[0]["content"][0]
                self.assertEqual(part["type"], "input_text")
        for good in ("QUJD", "QUI=", "QQ=="):
            with self.subTest(good=good):
                good_block = {"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf", "data": good}}
                part = self._input([{"role": "user", "content": [good_block]}])[0]["content"][0]
                self.assertEqual(part["type"], "input_file")

    def test_unrecognized_pdf_mode_warns_and_uses_file(self):
        name = "provider_shim_pdf_mode_%s" % uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(name, PRODUCTION_SHIM)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, {"SHIM_PDF_MODE": "omitt"}):
            with self.assertLogs("shim", level="WARNING") as captured:
                spec.loader.exec_module(module)
        try:
            self.assertEqual(module.SHIM_PDF_MODE, "file")
            self.assertTrue(any("SHIM_PDF_MODE" in line and "not recognized" in line
                                for line in captured.output), captured.output)
        finally:
            asyncio.run(module._client.aclose())

    def test_request_translation_never_raises_for_documents(self):
        body = {"max_tokens": 64, "messages": [
            {"role": "user", "content": [_pdf()]},
            {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
            {"role": "user", "content": [{"type": "document", "source": {"type": "future"}}]},
        ]}
        payload = self.shim._anthropic_to_responses_request(body, "gpt-fixture", None)[0]
        self.assertEqual(payload["input"][0]["content"], [_expected_pdf_part()])
        self.assertIn("was omitted", payload["input"][2]["content"][0]["text"])


class DocumentTransportTests(unittest.TestCase):
    maxDiff = 8000

    def test_pdf_history_reaches_backend_in_both_lanes(self):
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "read the pdf"}]},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "call_read_pdf", "name": "Read", "input": {"file_path": "x.pdf"}}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call_read_pdf",
                                          "content": [_pdf()]}]},
            {"role": "user", "content": [{"type": "document", "source": {"type": "file", "file_id": _FILE_ID}}]},
        ]
        for mode in ("openai", "chatgpt"):
            for stream in (False, True):
                with self.subTest(mode=mode, stream=stream):
                    with MockResponsesServer(full_response_scenario()) as backend:
                        with RealShim(backend, mode) as shim:
                            result = shim.post_messages(stream=stream, messages=messages)
                            self.assertEqual(result.status, 200, result.text)
                            sent = backend.responses_requests[0].body["input"]
                            outputs = [i for i in sent if i.get("type") == "function_call_output"]
                            self.assertEqual(outputs[0]["output"], [_expected_pdf_part()])
                            self.assertIn("was omitted", json.dumps(sent[-1]))
                            logs = shim.captured_stderr()
                            self.assertIn("document block omitted", logs)
                            self.assertNotIn(_PDF_B64, logs)
                            self.assertNotIn(_FILE_ID, logs)


if __name__ == "__main__":
    unittest.main()
