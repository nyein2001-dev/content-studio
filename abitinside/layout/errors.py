"""Actionable layout failures for a content author."""
from __future__ import annotations


class LayoutError(Exception):
    def __init__(self, scene: str, rule: str, message: str, remedy: str, **measured):
        self.scene = scene
        self.rule = rule
        self.message = message
        self.remedy = remedy
        self.measured = measured
        super().__init__(f"{scene}: {rule}: {message} Fix: {remedy}")
