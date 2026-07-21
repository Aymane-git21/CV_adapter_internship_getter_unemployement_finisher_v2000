"""Docgen comparison bench: prompted Typst vs Quarto->Typst vs LaTeX/Tectonic.

Measures, per toolchain, what actually matters for replacing the current
source-mode pipeline: can the production LLM author and edit the format
without breaking compiles, does the output keep all the CV content, and how
fast does the toolchain compile. Run: python -m backend.evals.docgen_compare
"""
