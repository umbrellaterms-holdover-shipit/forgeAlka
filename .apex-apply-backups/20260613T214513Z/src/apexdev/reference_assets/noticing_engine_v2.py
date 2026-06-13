#!/usr/bin/env python3
"""
Noticing Engine v2.

Config-first, object-oriented harness for preparing Noticing Game packets.

Default execution:
    python noticing_engine.py

The script reads:
    noticing_config.json

It writes:
    noticing_packet.md

No command-line arguments are required or expected. This is intentional.
The code is designed for mobile IDEs, scheduled runners, app wrappers,
and other non-interactive execution environments.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------
# Naming small things is not vanity. It is maintenance.
# ---------------------------------------------------------------------

NEWLINE = "\n"
BLANK_LINE = "\n\n"
SPACE = " "
MARKDOWN_QUOTE_PREFIX = "> "
DEFAULT_CONFIG_PATH = Path("noticing_config.json")
CONFIG_PATH_ENVIRONMENT_VARIABLE = "NOTICING_CONFIG_PATH"


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class SamplingConfig:
    minimum_conversations: int = 4
    maximum_conversations: int = 8
    fragments_per_conversation: int = 4
    candidate_pool_per_conversation: int = 30

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "SamplingConfig":
        return cls(
            minimum_conversations=int(data.get("minimum_conversations", 4)),
            maximum_conversations=int(data.get("maximum_conversations", 8)),
            fragments_per_conversation=int(data.get("fragments_per_conversation", 4)),
            candidate_pool_per_conversation=int(data.get("candidate_pool_per_conversation", 30)),
        )


@dataclasses.dataclass(frozen=True)
class FragmentScoringConfig:
    minimum_accepted_score: float = 1.5
    hot_attractor_penalty: float = 1.4
    maximum_hot_attractor_penalty: float = 5.0

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "FragmentScoringConfig":
        return cls(
            minimum_accepted_score=float(data.get("minimum_accepted_score", 1.5)),
            hot_attractor_penalty=float(data.get("hot_attractor_penalty", 1.4)),
            maximum_hot_attractor_penalty=float(data.get("maximum_hot_attractor_penalty", 5.0)),
        )


@dataclasses.dataclass(frozen=True)
class GenerationConfig:
    target_minimum_words: int = 1500
    target_maximum_words: int = 3500
    avoid_starting_with_hero_quote: bool = True

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "GenerationConfig":
        return cls(
            target_minimum_words=int(data.get("target_minimum_words", 1500)),
            target_maximum_words=int(data.get("target_maximum_words", 3500)),
            avoid_starting_with_hero_quote=bool(data.get("avoid_starting_with_hero_quote", True)),
        )


@dataclasses.dataclass(frozen=True)
class EngineConfig:
    input_json_path: Path
    output_packet_path: Path
    state_path: Path
    seed: Optional[int]
    sampling: SamplingConfig
    fragment_scoring: FragmentScoringConfig
    generation: GenerationConfig

    @classmethod
    def load_default(cls) -> "EngineConfig":
        config_path_text = os.environ.get(CONFIG_PATH_ENVIRONMENT_VARIABLE)
        config_path = Path(config_path_text) if config_path_text else DEFAULT_CONFIG_PATH
        return cls.from_file(config_path)

    @classmethod
    def from_file(cls, path: Path) -> "EngineConfig":
        raw_config = JsonFile.read_object(path)

        seed_value = raw_config.get("seed")
        seed = int(seed_value) if seed_value is not None else None

        return cls(
            input_json_path=Path(raw_config["input_json_path"]),
            output_packet_path=Path(raw_config["output_packet_path"]),
            state_path=Path(raw_config.get("state_path", "noticing_state.json")),
            seed=seed,
            sampling=SamplingConfig.from_json(raw_config.get("sampling", {})),
            fragment_scoring=FragmentScoringConfig.from_json(raw_config.get("fragment_scoring", {})),
            generation=GenerationConfig.from_json(raw_config.get("generation", {})),
        )


@dataclasses.dataclass(frozen=True)
class EngineState:
    side_markers: list[str]
    hot_attractors: list[str]
    corrected_facts: list[str]
    recent_successes: list[str]
    recent_failures: list[str]

    @classmethod
    def from_file(cls, path: Path) -> "EngineState":
        raw_state = JsonFile.read_object(path)

        return cls(
            side_markers=list(raw_state.get("side_markers", [])),
            hot_attractors=list(raw_state.get("hot_attractors", [])),
            corrected_facts=list(raw_state.get("corrected_facts", [])),
            recent_successes=list(raw_state.get("recent_successes", [])),
            recent_failures=list(raw_state.get("recent_failures", [])),
        )


class JsonFile:
    @staticmethod
    def read_object(path: Path) -> dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise RuntimeError(f"Missing required JSON file: {path}") from error

        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Invalid JSON in file: {path}") from error

        if not isinstance(data, dict):
            raise RuntimeError(f"Expected top-level JSON object in file: {path}")

        return data

    @staticmethod
    def read_any(path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise RuntimeError(f"Missing required JSON file: {path}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Invalid JSON in file: {path}") from error


# ---------------------------------------------------------------------
# Rule book
# ---------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class HiddenOperationPattern:
    name: str
    regexes: list[re.Pattern[str]]

    def count_hits(self, text: str) -> int:
        return sum(len(pattern.findall(text)) for pattern in self.regexes)


class HiddenOperationLibrary:
    """
    This is still regex-based. That is intentionally isolated here.

    Later, this can become:
    - a loaded YAML rule file
    - an embedding search
    - a small classifier call
    - a user-corrected FCCES-ish exclusion layer

    The rest of the engine should not care.
    """

    DEFAULT_PATTERNS: dict[str, list[str]] = {
        "absence_signature": [
            r"\bmissing\b",
            r"\babsence\b",
            r"\bnot there\b",
            r"\bdoesn't appear\b",
            r"\bcan't see\b",
            r"\binvisible\b",
            r"\bnegative space\b",
        ],
        "wrong_cost_placement": [
            r"\bcost\b",
            r"\bexpensive\b",
            r"\bcheap\b",
            r"\binvoice\b",
            r"\bpays?\b",
            r"\btoo much work\b",
        ],
        "routing_consequence": [
            r"\broute\b",
            r"\bpath\b",
            r"\bentry\b",
            r"\bthrough\b",
            r"\bgets you\b",
            r"\bleads\b",
        ],
        "bluffable_test": [
            r"\btest\b",
            r"\bcheck\b",
            r"\bdiagnostic\b",
            r"\bprove\b",
            r"\bpressure\b",
            r"\bsurvive\b",
            r"\bfails?\b",
        ],
        "useless_but_real_layer": [
            r"\buseless\b",
            r"\bpointless\b",
            r"\bdoesn't matter\b",
            r"\bstill real\b",
            r"\bnot load-bearing\b",
            r"\bdecorative\b",
        ],
        "local_done_global_continuation": [
            r"\bdone\b",
            r"\bfinished\b",
            r"\bkeep going\b",
            r"\bstill\b",
            r"\bnext\b",
            r"\bcontinues\b",
            r"\bnot over\b",
        ],
        "false_authority_from_proximity": [
            r"\bnear\b",
            r"\bclose\b",
            r"\bassume\b",
            r"\bbecause it looks\b",
            r"\bproximity\b",
            r"\bresembles\b",
        ],
        "container_vs_property": [
            r"\bcontainer\b",
            r"\bwrapper\b",
            r"\bframe\b",
            r"\bproperty\b",
            r"\bdiagnostic\b",
            r"\bcategory\b",
            r"\bhandle\b",
        ],
        "protected_uncertainty": [
            r"\buncertain\b",
            r"\bunknown\b",
            r"\bnot know\b",
            r"\bleave open\b",
            r"\bcan't tell\b",
            r"\bambiguous\b",
        ],
        "surface_as_actuator": [
            r"\bsurface\b",
            r"\bactuator\b",
            r"\binterface\b",
            r"\bhandle\b",
            r"\bbutton\b",
            r"\blever\b",
            r"\bskin\b",
            r"\bcostume\b",
        ],
        "anti_alibi_design": [
            r"\balibi\b",
            r"\bexcuse\b",
            r"\bcan't hide\b",
            r"\bno distance\b",
            r"\bresponsibility\b",
            r"\bowned\b",
            r"\baccountable\b",
        ],
        "compression_with_loss": [
            r"\bcompress\b",
            r"\bsummar",
            r"\bparaphrase\b",
            r"\blossy\b",
            r"\bflatten\b",
            r"\bexport\b",
            r"\bwrite.*down\b",
        ],
    }

    def __init__(self) -> None:
        self.patterns = [
            HiddenOperationPattern(
                name=name,
                regexes=[re.compile(pattern, re.IGNORECASE) for pattern in regexes],
            )
            for name, regexes in self.DEFAULT_PATTERNS.items()
        ]

    def find_hits(self, text: str) -> dict[str, int]:
        hits: dict[str, int] = {}

        for operation_pattern in self.patterns:
            hit_count = operation_pattern.count_hits(text)
            if hit_count > 0:
                hits[operation_pattern.name] = hit_count

        return hits


@dataclasses.dataclass(frozen=True)
class RuleBook:
    state: EngineState
    hidden_operations: HiddenOperationLibrary

    @classmethod
    def from_state(cls, state: EngineState) -> "RuleBook":
        return cls(
            state=state,
            hidden_operations=HiddenOperationLibrary(),
        )

    def side_marker_hits(self, text: str) -> list[str]:
        normalized_text = text.lower()
        return [
            marker
            for marker in self.state.side_markers
            if marker.lower() in normalized_text
        ]

    def hot_attractor_hits(self, text: str) -> list[str]:
        normalized_text = text.lower()
        return [
            attractor
            for attractor in self.state.hot_attractors
            if attractor.lower() in normalized_text
        ]

    def hidden_operation_hits(self, text: str) -> dict[str, int]:
        return self.hidden_operations.find_hits(text)


# ---------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class ConversationMessage:
    conversation_id: str
    conversation_title: str
    index: int
    role: str
    text: str

    @property
    def is_user_authored(self) -> bool:
        normalized_role = self.role.lower()
        return normalized_role in {"user", "human", "customer"} or normalized_role == ""

    @property
    def is_opening_frame(self) -> bool:
        return self.index <= 1

    def candidate_fragments(self) -> list["CandidateTextFragment"]:
        splitter = TextFragmentSplitter(self.text)
        return [
            CandidateTextFragment(
                message=self,
                start_index=start_index,
                text=fragment_text,
            )
            for start_index, fragment_text in splitter.split()
        ]


@dataclasses.dataclass(frozen=True)
class CandidateTextFragment:
    message: ConversationMessage
    start_index: int
    text: str

    @property
    def length(self) -> int:
        return len(self.text)


@dataclasses.dataclass(frozen=True)
class ScoredFragment:
    candidate: CandidateTextFragment
    score: float
    reasons: list[str]
    hot_attractor_hits: list[str]
    hidden_operation_hits: dict[str, int]

    @property
    def id(self) -> str:
        source_text = (
            f"{self.candidate.message.conversation_id}:"
            f"{self.candidate.message.index}:"
            f"{self.candidate.start_index}:"
            f"{self.candidate.text}"
        )
        return hashlib.sha1(source_text.encode("utf-8")).hexdigest()[:12]

    @property
    def text(self) -> str:
        return self.candidate.text

    @property
    def conversation_id(self) -> str:
        return self.candidate.message.conversation_id

    @property
    def conversation_title(self) -> str:
        return self.candidate.message.conversation_title or "(untitled conversation)"

    @property
    def message_index(self) -> int:
        return self.candidate.message.index

    @property
    def is_hot(self) -> bool:
        return bool(self.hot_attractor_hits)

    @property
    def hidden_operation_names(self) -> list[str]:
        return list(self.hidden_operation_hits.keys())

    def markdown_card(self) -> str:
        quote_text = self.text.replace(NEWLINE, NEWLINE + MARKDOWN_QUOTE_PREFIX)

        return (
            f"### Fragment {self.id}{BLANK_LINE}"
            f"Source:{NEWLINE}"
            f"- conversation_id: `{self.conversation_id}`{NEWLINE}"
            f"- title: `{self.conversation_title}`{NEWLINE}"
            f"- message_index: `{self.message_index}`{NEWLINE}"
            f"- score: `{self.score:.2f}`{NEWLINE}"
            f"- reasons: `{', '.join(self.reasons)}`{NEWLINE}"
            f"- hot_hits: `{self._format_hot_hits()}`{NEWLINE}"
            f"- operation_hits: `{json.dumps(self.hidden_operation_hits, sort_keys=True)}`"
            f"{BLANK_LINE}"
            f"Quote:{NEWLINE}"
            f"{MARKDOWN_QUOTE_PREFIX}{quote_text}"
        )

    def _format_hot_hits(self) -> str:
        if not self.hot_attractor_hits:
            return "none"
        return ", ".join(self.hot_attractor_hits)


class TextFragmentSplitter:
    """
    Splits one message into quote-sized fragments.

    This is deliberately not clever. It is a first sieve.
    The scoring layer decides what deserves to live.
    """

    MINIMUM_PARAGRAPH_LENGTH = 80
    MAXIMUM_PARAGRAPH_LENGTH = 900
    LONG_PARAGRAPH_LENGTH = 350

    MINIMUM_SENTENCE_CLUSTER_LENGTH = 120
    MAXIMUM_SENTENCE_CLUSTER_LENGTH = 500
    MAXIMUM_FORCED_CLUSTER_LENGTH = 700

    def __init__(self, text: str) -> None:
        self.text = text

    def split(self) -> list[tuple[int, str]]:
        paragraph_fragments = self._paragraph_fragments()
        sentence_fragments = self._sentence_cluster_fragments()
        return self._deduplicated(paragraph_fragments + sentence_fragments)

    def _paragraph_fragments(self) -> list[tuple[int, str]]:
        fragments: list[tuple[int, str]] = []

        for start_index, paragraph in self._paragraphs_with_offsets():
            if self.MINIMUM_PARAGRAPH_LENGTH <= len(paragraph) <= self.MAXIMUM_PARAGRAPH_LENGTH:
                fragments.append((start_index, paragraph))

        return fragments

    def _sentence_cluster_fragments(self) -> list[tuple[int, str]]:
        fragments: list[tuple[int, str]] = []

        for paragraph_start_index, paragraph in self._paragraphs_with_offsets():
            if len(paragraph) <= self.LONG_PARAGRAPH_LENGTH:
                continue

            fragments.extend(
                self._split_long_paragraph_into_sentence_clusters(
                    paragraph_start_index=paragraph_start_index,
                    paragraph=paragraph,
                )
            )

        return fragments

    def _paragraphs_with_offsets(self) -> list[tuple[int, str]]:
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", self.text)
            if paragraph.strip()
        ]

        cursor = 0
        located_paragraphs: list[tuple[int, str]] = []

        for paragraph in paragraphs:
            start_index = self.text.find(paragraph, cursor)
            if start_index < 0:
                start_index = cursor

            located_paragraphs.append((start_index, paragraph))
            cursor = start_index + len(paragraph)

        return located_paragraphs

    def _split_long_paragraph_into_sentence_clusters(
        self,
        paragraph_start_index: int,
        paragraph: str,
    ) -> list[tuple[int, str]]:
        sentence_like_parts = re.split(r"(?<=[.!?])\s+|\n+", paragraph)

        fragments: list[tuple[int, str]] = []
        cluster_text = ""
        cluster_start_index = paragraph_start_index
        search_cursor = paragraph_start_index

        for sentence_like_part in sentence_like_parts:
            sentence_like_part = sentence_like_part.strip()
            if not sentence_like_part:
                continue

            found_index = self.text.find(sentence_like_part, search_cursor)
            if found_index < 0:
                found_index = search_cursor

            if not cluster_text:
                cluster_start_index = found_index

            cluster_text = self._append_sentence(cluster_text, sentence_like_part)

            if self._is_good_sentence_cluster(cluster_text):
                fragments.append((cluster_start_index, cluster_text))
                cluster_text = ""
            elif len(cluster_text) > self.MAXIMUM_SENTENCE_CLUSTER_LENGTH:
                forced_cluster = cluster_text[:self.MAXIMUM_FORCED_CLUSTER_LENGTH].strip()
                fragments.append((cluster_start_index, forced_cluster))
                cluster_text = ""

            search_cursor = found_index + len(sentence_like_part)

        if self._is_usable_trailing_cluster(cluster_text):
            fragments.append((cluster_start_index, cluster_text))

        return fragments

    @staticmethod
    def _append_sentence(existing_text: str, sentence_like_part: str) -> str:
        if not existing_text:
            return sentence_like_part
        return existing_text + SPACE + sentence_like_part

    def _is_good_sentence_cluster(self, text: str) -> bool:
        return (
            self.MINIMUM_SENTENCE_CLUSTER_LENGTH
            <= len(text)
            <= self.MAXIMUM_SENTENCE_CLUSTER_LENGTH
        )

    def _is_usable_trailing_cluster(self, text: str) -> bool:
        return 100 <= len(text) <= self.MAXIMUM_FORCED_CLUSTER_LENGTH

    @staticmethod
    def _deduplicated(fragments: list[tuple[int, str]]) -> list[tuple[int, str]]:
        seen_normalized_texts: set[str] = set()
        unique_fragments: list[tuple[int, str]] = []

        for start_index, fragment_text in fragments:
            normalized_text = TextFragmentSplitter._normalize_for_deduplication(fragment_text)

            if normalized_text in seen_normalized_texts:
                continue

            seen_normalized_texts.add(normalized_text)
            unique_fragments.append((start_index, fragment_text))

        return unique_fragments

    @staticmethod
    def _normalize_for_deduplication(text: str) -> str:
        return re.sub(r"\s+", SPACE, text.lower()).strip()


# ---------------------------------------------------------------------
# Conversation archive parsing
# ---------------------------------------------------------------------

class ConversationArchive:
    def __init__(self, messages: list[ConversationMessage]) -> None:
        self.messages = messages

    @classmethod
    def from_file(cls, path: Path) -> "ConversationArchive":
        raw_export = JsonFile.read_any(path)
        messages = ConversationExportParser(raw_export).parse()
        return cls(messages)

    def user_messages_after_opening_frames(self) -> list[ConversationMessage]:
        return [
            message
            for message in self.messages
            if message.is_user_authored and not message.is_opening_frame
        ]


class ConversationExportParser:
    """
    Parser for common conversation export shapes.

    This class is a boundary object. If the export format changes,
    edits should happen here rather than infecting the engine.
    """

    def __init__(self, raw_export: Any) -> None:
        self.raw_export = raw_export

    def parse(self) -> list[ConversationMessage]:
        conversations = self._extract_conversations()
        messages: list[ConversationMessage] = []

        for conversation_index, conversation in enumerate(conversations):
            if not isinstance(conversation, dict):
                continue

            messages.extend(
                self._parse_conversation(
                    conversation_index=conversation_index,
                    conversation=conversation,
                )
            )

        return messages

    def _extract_conversations(self) -> list[Any]:
        if isinstance(self.raw_export, list):
            return self.raw_export

        if isinstance(self.raw_export, dict) and "conversations" in self.raw_export:
            conversations = self.raw_export["conversations"]
            if isinstance(conversations, list):
                return conversations

        if isinstance(self.raw_export, dict):
            return [self.raw_export]

        raise RuntimeError("Unsupported conversation JSON root shape.")

    def _parse_conversation(
        self,
        conversation_index: int,
        conversation: dict[str, Any],
    ) -> list[ConversationMessage]:
        if isinstance(conversation.get("mapping"), dict):
            return self._parse_mapping_conversation(conversation_index, conversation)

        if isinstance(conversation.get("messages"), list):
            return self._parse_message_list_conversation(conversation_index, conversation)

        if isinstance(conversation.get("items"), list):
            return self._parse_message_list_conversation(conversation_index, conversation)

        return []

    def _parse_mapping_conversation(
        self,
        conversation_index: int,
        conversation: dict[str, Any],
    ) -> list[ConversationMessage]:
        conversation_id = self._conversation_id(conversation_index, conversation)
        conversation_title = self._conversation_title(conversation)

        sortable_messages: list[tuple[float, str, dict[str, Any]]] = []

        mapping = conversation["mapping"]
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue

            message = node.get("message")
            if not isinstance(message, dict):
                continue

            create_time = message.get("create_time") or 0
            sortable_messages.append((float(create_time), str(node_id), message))

        sortable_messages.sort(key=lambda item: (item[0], item[1]))

        parsed_messages: list[ConversationMessage] = []

        for local_index, (_, _, raw_message) in enumerate(sortable_messages):
            parsed_message = self._parse_raw_message(
                conversation_id=conversation_id,
                conversation_title=conversation_title,
                local_index=local_index,
                raw_message=raw_message,
            )

            if parsed_message is not None:
                parsed_messages.append(parsed_message)

        return parsed_messages

    def _parse_message_list_conversation(
        self,
        conversation_index: int,
        conversation: dict[str, Any],
    ) -> list[ConversationMessage]:
        conversation_id = self._conversation_id(conversation_index, conversation)
        conversation_title = self._conversation_title(conversation)
        raw_messages = conversation.get("messages") or conversation.get("items") or []

        parsed_messages: list[ConversationMessage] = []

        for local_index, raw_message in enumerate(raw_messages):
            if not isinstance(raw_message, dict):
                continue

            parsed_message = self._parse_raw_message(
                conversation_id=conversation_id,
                conversation_title=conversation_title,
                local_index=local_index,
                raw_message=raw_message,
            )

            if parsed_message is not None:
                parsed_messages.append(parsed_message)

        return parsed_messages

    def _parse_raw_message(
        self,
        conversation_id: str,
        conversation_title: str,
        local_index: int,
        raw_message: dict[str, Any],
    ) -> Optional[ConversationMessage]:
        role = self._message_role(raw_message)
        text = TextExtractor.from_message(raw_message).extract_clean_text()

        if not text:
            return None

        return ConversationMessage(
            conversation_id=conversation_id,
            conversation_title=conversation_title,
            index=local_index,
            role=role,
            text=text,
        )

    @staticmethod
    def _conversation_id(conversation_index: int, conversation: dict[str, Any]) -> str:
        return str(
            conversation.get("id")
            or conversation.get("conversation_id")
            or conversation_index
        )

    @staticmethod
    def _conversation_title(conversation: dict[str, Any]) -> str:
        return str(conversation.get("title") or "")

    @staticmethod
    def _message_role(raw_message: dict[str, Any]) -> str:
        author = raw_message.get("author")
        if isinstance(author, dict):
            author_role = author.get("role")
            if author_role:
                return str(author_role)

        for role_key in ("role", "sender"):
            if raw_message.get(role_key):
                return str(raw_message[role_key])

        return ""


class TextExtractor:
    def __init__(self, raw_message: dict[str, Any]) -> None:
        self.raw_message = raw_message

    @classmethod
    def from_message(cls, raw_message: dict[str, Any]) -> "TextExtractor":
        return cls(raw_message)

    def extract_clean_text(self) -> str:
        raw_content = (
            self.raw_message.get("content")
            or self.raw_message.get("text")
            or self.raw_message.get("body")
        )

        text = self._extract_text_from_content(raw_content)
        return self._clean_text(text)

    def _extract_text_from_content(self, content: Any) -> str:
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            extracted_parts = [
                self._extract_text_from_content(item)
                for item in content
            ]
            nonempty_parts = [part for part in extracted_parts if part.strip()]
            return NEWLINE.join(nonempty_parts)

        if isinstance(content, dict):
            if "parts" in content:
                return self._extract_text_from_content(content["parts"])

            for content_key in ("text", "value", "body", "content"):
                if content_key in content:
                    return self._extract_text_from_content(content[content_key])

        return ""

    @staticmethod
    def _clean_text(text: str) -> str:
        text = text.replace("\r\n", NEWLINE).replace("\r", NEWLINE)
        text = re.sub(r"\n{3,}", BLANK_LINE, text)
        return text.strip()


# ---------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------

class FragmentScorer:
    VIVID_LANGUAGE_PATTERN = re.compile(
        r"\bfuck|fucking|bullshit|delicious|stupid|annoying|weird\b",
        re.IGNORECASE,
    )

    CORRECTION_ENERGY_PATTERN = re.compile(
        r"\b(no|not quite|this is wrong|you're missing|the issue is|actually)\b",
        re.IGNORECASE,
    )

    THESIS_MARKERS = [
        "basically",
        "the point is",
        "the core",
        "the thesis",
        "what i'm saying",
        "the whole thing",
        "in conclusion",
        "this means",
    ]

    def __init__(
        self,
        rule_book: RuleBook,
        scoring_config: FragmentScoringConfig,
    ) -> None:
        self.rule_book = rule_book
        self.scoring_config = scoring_config

    def score(self, candidate: CandidateTextFragment) -> ScoredFragment:
        score = 0.0
        reasons: list[str] = []

        length_score, length_reason = self._length_score(candidate)
        score += length_score
        reasons.append(length_reason)

        side_marker_hits = self.rule_book.side_marker_hits(candidate.text)
        if side_marker_hits:
            score += float(len(side_marker_hits))
            reasons.extend(f"side-marker:{hit}" for hit in side_marker_hits)

        if self.CORRECTION_ENERGY_PATTERN.search(candidate.text):
            score += 1.5
            reasons.append("correction-energy")

        if self._has_marked_emphasis(candidate.text):
            score += 0.5
            reasons.append("marked-emphasis")

        if self.VIVID_LANGUAGE_PATTERN.search(candidate.text):
            score += 0.8
            reasons.append("vivid-language")

        hidden_operation_hits = self.rule_book.hidden_operation_hits(candidate.text)
        if hidden_operation_hits:
            operation_score = min(3.0, sum(hidden_operation_hits.values()) * 0.7)
            score += operation_score
            operation_names = ",".join(sorted(hidden_operation_hits))
            reasons.append(f"operation-hits:{operation_names}")

        hot_attractor_hits = self.rule_book.hot_attractor_hits(candidate.text)
        if hot_attractor_hits:
            penalty = self._hot_attractor_penalty(hot_attractor_hits)
            score -= penalty
            reasons.append(f"hot-attractor-penalty:{penalty:.1f}")

        thesis_penalty = self._thesis_penalty(candidate)
        if thesis_penalty:
            score -= thesis_penalty
            reasons.append(f"thesis-penalty:{thesis_penalty:.1f}")

        return ScoredFragment(
            candidate=candidate,
            score=score,
            reasons=reasons,
            hot_attractor_hits=hot_attractor_hits,
            hidden_operation_hits=hidden_operation_hits,
        )

    @staticmethod
    def _length_score(candidate: CandidateTextFragment) -> tuple[float, str]:
        if 120 <= candidate.length <= 450:
            return 3.0, "good-length"

        if 451 <= candidate.length <= 800:
            return 1.5, "usable-long"

        return -2.0, "awkward-length"

    @staticmethod
    def _has_marked_emphasis(text: str) -> bool:
        return "?" in text or "!" in text or "*" in text

    def _hot_attractor_penalty(self, hot_attractor_hits: list[str]) -> float:
        raw_penalty = self.scoring_config.hot_attractor_penalty * len(hot_attractor_hits)
        return min(self.scoring_config.maximum_hot_attractor_penalty, raw_penalty)

    def _thesis_penalty(self, candidate: CandidateTextFragment) -> float:
        penalty = 0.0

        if candidate.message.is_opening_frame:
            penalty += 3.0

        normalized_text = candidate.text.lower()
        for thesis_marker in self.THESIS_MARKERS:
            if thesis_marker in normalized_text:
                penalty += 0.8

        return penalty


class FragmentPool:
    def __init__(self, fragments: list[ScoredFragment]) -> None:
        self.fragments = fragments

    @classmethod
    def build(
        cls,
        archive: ConversationArchive,
        scorer: FragmentScorer,
        minimum_accepted_score: float,
    ) -> "FragmentPool":
        accepted_fragments: list[ScoredFragment] = []

        for message in archive.user_messages_after_opening_frames():
            for candidate in message.candidate_fragments():
                scored_fragment = scorer.score(candidate)

                if scored_fragment.score >= minimum_accepted_score:
                    accepted_fragments.append(scored_fragment)

        if not accepted_fragments:
            raise RuntimeError("No usable fragments found. Check export format or scoring rules.")

        return cls(accepted_fragments)

    def grouped_by_conversation(self) -> dict[str, list[ScoredFragment]]:
        grouped_fragments: dict[str, list[ScoredFragment]] = defaultdict(list)

        for fragment in self.fragments:
            grouped_fragments[fragment.conversation_id].append(fragment)

        return dict(grouped_fragments)


# ---------------------------------------------------------------------
# Sampling and clustering
# ---------------------------------------------------------------------

class FragmentSampler:
    def __init__(
        self,
        sampling_config: SamplingConfig,
        random_source: random.Random,
    ) -> None:
        self.sampling_config = sampling_config
        self.random_source = random_source

    def sample(self, pool: FragmentPool) -> list[ScoredFragment]:
        fragments_by_conversation = pool.grouped_by_conversation()
        conversation_ids = list(fragments_by_conversation.keys())

        self.random_source.shuffle(conversation_ids)

        selected_conversation_ids = self._choose_conversation_ids(conversation_ids)

        sampled_fragments: list[ScoredFragment] = []
        for conversation_id in selected_conversation_ids:
            conversation_fragments = fragments_by_conversation[conversation_id]
            candidates = self._best_conversation_candidates(conversation_fragments)

            sampled_fragments.extend(
                self._weighted_sample_without_replacement(
                    candidates,
                    self.sampling_config.fragments_per_conversation,
                )
            )

        return sampled_fragments

    def _choose_conversation_ids(self, conversation_ids: list[str]) -> list[str]:
        if not conversation_ids:
            return []

        maximum_count = min(
            self.sampling_config.maximum_conversations,
            len(conversation_ids),
        )

        minimum_count = min(
            self.sampling_config.minimum_conversations,
            maximum_count,
        )

        selected_count = self.random_source.randint(minimum_count, maximum_count)
        return conversation_ids[:selected_count]

    def _best_conversation_candidates(
        self,
        fragments: list[ScoredFragment],
    ) -> list[ScoredFragment]:
        sorted_fragments = sorted(
            fragments,
            key=lambda fragment: fragment.score,
            reverse=True,
        )

        return sorted_fragments[: self.sampling_config.candidate_pool_per_conversation]

    def _weighted_sample_without_replacement(
        self,
        fragments: list[ScoredFragment],
        count: int,
    ) -> list[ScoredFragment]:
        remaining_fragments = list(fragments)
        selected_fragments: list[ScoredFragment] = []

        for _ in range(min(count, len(remaining_fragments))):
            selected_index = self._choose_weighted_index(remaining_fragments)
            selected_fragments.append(remaining_fragments.pop(selected_index))

        return selected_fragments

    def _choose_weighted_index(self, fragments: list[ScoredFragment]) -> int:
        weights = [self._sampling_weight(fragment) for fragment in fragments]
        total_weight = sum(weights)

        selection_point = self.random_source.random() * total_weight
        accumulated_weight = 0.0

        for index, weight in enumerate(weights):
            accumulated_weight += weight
            if accumulated_weight >= selection_point:
                return index

        return len(fragments) - 1

    @staticmethod
    def _sampling_weight(fragment: ScoredFragment) -> float:
        raw_weight = math.exp(fragment.score / 3.0)
        return max(0.05, min(20.0, raw_weight))


@dataclasses.dataclass(frozen=True)
class FragmentCluster:
    operation_name: str
    fragments: list[ScoredFragment]

    @property
    def conversation_count(self) -> int:
        return len({fragment.conversation_id for fragment in self.fragments})

    @property
    def average_score(self) -> float:
        if not self.fragments:
            return 0.0
        return sum(fragment.score for fragment in self.fragments) / len(self.fragments)

    @property
    def hot_attractor_count(self) -> int:
        return sum(len(fragment.hot_attractor_hits) for fragment in self.fragments)

    @property
    def viability_score(self) -> float:
        return self.average_score - self.hot_attractor_count

    def strongest_fragments(self, limit: int) -> list[ScoredFragment]:
        return sorted(
            self.fragments,
            key=lambda fragment: fragment.score,
            reverse=True,
        )[:limit]


class FragmentClusterer:
    UNLABELED_OPERATION_NAME = "unlabeled_but_interesting"
    FALLBACK_OPERATION_NAME = "provisional_collision_field"

    def __init__(self, random_source: random.Random) -> None:
        self.random_source = random_source

    def choose_cluster(self, sampled_fragments: list[ScoredFragment]) -> FragmentCluster:
        clusters = self._cluster_by_hidden_operation(sampled_fragments)
        viable_clusters = self._viable_clusters(clusters)

        if not viable_clusters:
            return self._fallback_cluster(sampled_fragments)

        viable_clusters.sort(
            key=lambda cluster: cluster.viability_score,
            reverse=True,
        )

        top_clusters = viable_clusters[:3]
        chosen_cluster = self.random_source.choice(top_clusters)

        return FragmentCluster(
            operation_name=chosen_cluster.operation_name,
            fragments=chosen_cluster.strongest_fragments(limit=8),
        )

    def _cluster_by_hidden_operation(
        self,
        fragments: list[ScoredFragment],
    ) -> list[FragmentCluster]:
        fragments_by_operation: dict[str, list[ScoredFragment]] = defaultdict(list)

        for fragment in fragments:
            if fragment.hidden_operation_names:
                for operation_name in fragment.hidden_operation_names:
                    fragments_by_operation[operation_name].append(fragment)
            else:
                fragments_by_operation[self.UNLABELED_OPERATION_NAME].append(fragment)

        return [
            FragmentCluster(operation_name=operation_name, fragments=operation_fragments)
            for operation_name, operation_fragments in fragments_by_operation.items()
        ]

    @staticmethod
    def _viable_clusters(clusters: list[FragmentCluster]) -> list[FragmentCluster]:
        viable_clusters: list[FragmentCluster] = []

        for cluster in clusters:
            if len(cluster.fragments) < 3:
                continue

            if cluster.conversation_count < 3:
                continue

            viable_clusters.append(cluster)

        return viable_clusters

    def _fallback_cluster(self, fragments: list[ScoredFragment]) -> FragmentCluster:
        strongest_fragments = sorted(
            fragments,
            key=lambda fragment: fragment.score,
            reverse=True,
        )[:6]

        return FragmentCluster(
            operation_name=self.FALLBACK_OPERATION_NAME,
            fragments=strongest_fragments,
        )


class HeroQuoteSelector:
    VIVID_LANGUAGE_PATTERN = re.compile(
        r"\bfuck|fucking|bullshit|delicious|stupid|weird|annoying\b",
        re.IGNORECASE,
    )

    def choose(self, cluster: FragmentCluster) -> Optional[ScoredFragment]:
        if not cluster.fragments:
            return None

        candidates = [
            self._hero_candidate_score(fragment)
            for fragment in cluster.fragments
        ]

        candidates.sort(
            key=lambda candidate: (candidate.vividness_score, candidate.fragment.score),
            reverse=True,
        )

        return candidates[0].fragment

    def _hero_candidate_score(self, fragment: ScoredFragment) -> "HeroCandidateScore":
        vividness_score = 0

        if self.VIVID_LANGUAGE_PATTERN.search(fragment.text):
            vividness_score += 2

        if "?" in fragment.text or "!" in fragment.text:
            vividness_score += 1

        if 120 <= len(fragment.text) <= 500:
            vividness_score += 1

        vividness_score -= len(fragment.hot_attractor_hits)

        return HeroCandidateScore(
            fragment=fragment,
            vividness_score=vividness_score,
        )


@dataclasses.dataclass(frozen=True)
class HeroCandidateScore:
    fragment: ScoredFragment
    vividness_score: int


# ---------------------------------------------------------------------
# Prompt packet construction
# ---------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class PacketSourceSet:
    selected_cluster: FragmentCluster
    sampled_fragments: list[ScoredFragment]
    hero_quote: Optional[ScoredFragment]
    seed: int

    def secondary_fragments(self, limit: int = 8) -> list[ScoredFragment]:
        primary_fragment_ids = {
            fragment.id
            for fragment in self.selected_cluster.fragments
        }

        secondary_candidates = [
            fragment
            for fragment in self.sampled_fragments
            if fragment.id not in primary_fragment_ids
        ]

        return sorted(
            secondary_candidates,
            key=lambda fragment: fragment.score,
            reverse=True,
        )[:limit]


class PromptPacketBuilder:
    def __init__(
        self,
        generation_config: GenerationConfig,
        engine_state: EngineState,
    ) -> None:
        self.generation_config = generation_config
        self.engine_state = engine_state

    def build(self, source_set: PacketSourceSet) -> str:
        return (
            self._header(source_set)
            + BLANK_LINE
            + self._generation_instructions()
            + BLANK_LINE
            + self._corrected_facts_section()
            + BLANK_LINE
            + self._primary_fragments_section(source_set)
            + BLANK_LINE
            + self._secondary_fragments_section(source_set)
        )

    def _header(self, source_set: PacketSourceSet) -> str:
        hero_quote_text = self._hero_quote_text(source_set.hero_quote)

        return (
            f"# Noticing Game Packet{BLANK_LINE}"
            f"Seed: `{source_set.seed}`{BLANK_LINE}"
            f"Candidate hidden operation:{NEWLINE}"
            f"`{source_set.selected_cluster.operation_name}`{BLANK_LINE}"
            f"Hero quote candidate:{NEWLINE}"
            f"{MARKDOWN_QUOTE_PREFIX}{hero_quote_text}"
        )

    def _generation_instructions(self) -> str:
        return (
            "## Generation Instructions"
            f"{BLANK_LINE}"
            "Write a long-form noticing, not a summary."
            f"{BLANK_LINE}"
            "Use the fragments below as a collision field. Do not simply explain "
            "their home conversations. The noticing should be supported by at least "
            "three unrelated fragments. Cluster by hidden operation, not topic."
            f"{BLANK_LINE}"
            f"Target length: {self.generation_config.target_minimum_words} to "
            f"{self.generation_config.target_maximum_words} words."
            f"{BLANK_LINE}"
            "Do not start with the hero quote. Let the pattern begin moving first, "
            "then place the hero quote midstream. After using the quote, leave its "
            "home context quickly and widen back out."
            f"{BLANK_LINE}"
            "Sanity checks before final:"
            f"{NEWLINE}"
            "- Would the noticing still exist if the hero quote were removed?"
            f"{NEWLINE}"
            "- Would the noticing still exist if one sampled conversation were removed?"
            f"{NEWLINE}"
            "- Did the pattern get enough room to breathe?"
            f"{NEWLINE}"
            "- Did you avoid rewalking the original conversation frames?"
            f"{NEWLINE}"
            "- If praising a line, did you show at least three actual operations?"
            f"{BLANK_LINE}"
            "Target shape:"
            f"{NEWLINE}"
            "- indirect opening"
            f"{NEWLINE}"
            "- several fragment tests"
            f"{NEWLINE}"
            "- midstream hero quote"
            f"{NEWLINE}"
            "- complication / false-near readings"
            f"{NEWLINE}"
            "- widened synthesis"
            f"{NEWLINE}"
            "- final compression, but not emotional closure"
        )

    def _corrected_facts_section(self) -> str:
        if not self.engine_state.corrected_facts:
            return "## Corrected Facts" + BLANK_LINE + "None recorded."

        facts = NEWLINE.join(
            f"- {fact}"
            for fact in self.engine_state.corrected_facts
        )

        return "## Corrected Facts" + BLANK_LINE + facts

    @staticmethod
    def _primary_fragments_section(source_set: PacketSourceSet) -> str:
        cards = BLANK_LINE.join(
            fragment.markdown_card()
            for fragment in source_set.selected_cluster.fragments
        )

        return "## Primary Support Fragments" + BLANK_LINE + cards

    @staticmethod
    def _secondary_fragments_section(source_set: PacketSourceSet) -> str:
        secondary_fragments = source_set.secondary_fragments(limit=8)

        if not secondary_fragments:
            return "## Secondary Collision Fragments" + BLANK_LINE + "None selected."

        cards = BLANK_LINE.join(
            fragment.markdown_card()
            for fragment in secondary_fragments
        )

        return "## Secondary Collision Fragments" + BLANK_LINE + cards

    @staticmethod
    def _hero_quote_text(hero_quote: Optional[ScoredFragment]) -> str:
        if hero_quote is None:
            return "None selected."

        return f"{hero_quote.id}: {hero_quote.text}"


# ---------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------

class NoticingEngine:
    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.seed = self._resolved_seed(config.seed)
        self.random_source = random.Random(self.seed)

    def run(self) -> None:
        state = EngineState.from_file(self.config.state_path)
        rule_book = RuleBook.from_state(state)

        archive = ConversationArchive.from_file(self.config.input_json_path)

        scorer = FragmentScorer(
            rule_book=rule_book,
            scoring_config=self.config.fragment_scoring,
        )

        fragment_pool = FragmentPool.build(
            archive=archive,
            scorer=scorer,
            minimum_accepted_score=self.config.fragment_scoring.minimum_accepted_score,
        )

        sampler = FragmentSampler(
            sampling_config=self.config.sampling,
            random_source=self.random_source,
        )

        sampled_fragments = sampler.sample(fragment_pool)

        clusterer = FragmentClusterer(random_source=self.random_source)
        selected_cluster = clusterer.choose_cluster(sampled_fragments)

        hero_quote_selector = HeroQuoteSelector()
        hero_quote = hero_quote_selector.choose(selected_cluster)

        source_set = PacketSourceSet(
            selected_cluster=selected_cluster,
            sampled_fragments=sampled_fragments,
            hero_quote=hero_quote,
            seed=self.seed,
        )

        packet_builder = PromptPacketBuilder(
            generation_config=self.config.generation,
            engine_state=state,
        )

        packet_text = packet_builder.build(source_set)
        self.config.output_packet_path.write_text(packet_text, encoding="utf-8")

    @staticmethod
    def _resolved_seed(configured_seed: Optional[int]) -> int:
        if configured_seed is not None:
            return configured_seed

        return random.SystemRandom().randrange(1, 10_000_000)


def main() -> None:
    config = EngineConfig.load_default()
    engine = NoticingEngine(config)
    engine.run()


if __name__ == "__main__":
    main()
