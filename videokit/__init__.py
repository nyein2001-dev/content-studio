"""Shared package for both channels of the studio.

Channel-independent machinery only: frame engine, text engine, motion vocabulary,
vector components, local neural TTS, caption alignment, voice QA, procedural
audio, mixing, muxing and QA helpers.

Anything brand-specific (palette, fonts, geometry, scene scripts, editorial)
lives in the channel's own directory, never here.
"""
__all__ = ["engine", "motion", "text", "components", "tts", "align", "voice_qa", "mux"]
__version__ = "1.0.0"