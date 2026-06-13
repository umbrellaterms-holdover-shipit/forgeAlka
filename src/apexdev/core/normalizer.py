"""
Text normalisation utilities for conversation messages.

This module provides functions to prepare message content for
analysis.  Normalisation helps reduce noise and makes it easier to
apply pattern matching and tokenisation.
"""
import re
from typing import List

# Citation patterns: e.g. 【123†L1-L2】
CITATION_RE = re.compile(r"【\d+†[A-Za-z0-9]+(-[A-Za-z0-9]+)?】")

def normalise_text(text: str,
                   remove_citations: bool = True,
                   squeeze_whitespace: bool = True) -> str:
    """Clean and normalise a message string.

    Parameters
    ----------
    text : str
        Raw message text.
    remove_citations : bool, optional
        Remove citation markers of the form ``【...】``.  Defaults to
        ``True``.
    squeeze_whitespace : bool, optional
        Collapse multiple consecutive whitespace characters into a
        single space.  Defaults to ``True``.

    Returns
    -------
    str
        The normalised text.
    """
    if not text:
        return ''
    out = text.replace('\r\n', '\n').replace('\r', '\n')
    if remove_citations:
        out = CITATION_RE.sub('', out)
    if squeeze_whitespace:
        # Replace runs of whitespace with a single space
        out = re.sub(r"\s+", ' ', out)
    return out.strip()

def strip_markdown_fences(text: str) -> str:
    """Remove fenced code block markers from the text.

    Removes leading and trailing triple backtick fences and language
    specifiers.  Only the fence markers themselves are removed;
    indent is not adjusted.

    Parameters
    ----------
    text : str
        A text string that may include fenced code blocks.

    Returns
    -------
    str
        The text with fence markers removed.
    """
    pattern = re.compile(r"^\s*```.*?\n|```\s*$", re.DOTALL | re.MULTILINE)
    return pattern.sub('', text).strip()

def split_lines(text: str) -> List[str]:
    """Split text into lines normalising line endings.

    Parameters
    ----------
    text : str
        The input text.

    Returns
    -------
    list of str
        Lines of text with ``\r`` and ``\r\n`` converted to ``\n``.
    """
    return text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
