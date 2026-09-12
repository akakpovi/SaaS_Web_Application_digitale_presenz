"""Parsers for external scanner output.

Each parser module converts raw text/JSON output from an external tool into
a list of dicts ready for normalization via ``BaseScanner.normalize()``.

Parsers are pure functions — they have no side effects and can be tested
independently with fixture data.
"""
