from __future__ import annotations
import argparse, json
from pathlib import Path
from dataclasses import asdict

from .core.loader import load_conversations
from .code_inspection.snippet_extractor import extract_snippets
from .indexes.inverted import InvertedIndex
from .indexes.spines import build_spines
from .indexes.quote_anchors import extract_quote_anchors
from .indexes.correction_acceptance import detect_turn_signals, detect_artifact_requests
from .noticing.config import NoticingConfig
from .noticing.engine import generate_packet
from .noticing.packets import render_packet_markdown
from .analytics.role_metrics import role_counts, role_token_counts
from .analytics.semantic_payload import corpus_payload
from .analytics.output_trends import conversation_output_trend
from .analytics.charts import write_trend_svg
from .documents.markdown_tools import markdown_word_count, heading_outline
from .documents.pdf_tools import markdown_to_pdf
from .documents.conversion import convert_file, render_available_conversions
from .system_tools import dependency_report, render_dependency_report, install_system_tools
from .documents.tex_tools import summarize_tex_atlas
from .llm.openrouter import OpenRouterClient, build_messages, chat_text_from_response, stream_delta_text, messages_to_responses_input, text_from_response_api, text_from_message_api, response_stream_delta_text, message_stream_delta_text, recommended_wire_format_for_model
from .llm.costs import estimate_request_costs, write_cost_report
from .llm.model_catalog import load_models_snapshot, rows_from_snapshot, compact_model_options
from .llm.rates import write_example_rates, write_seed_rates, seed_rates_info
from .config import read_secret, secret_path, secret_status, write_secret
from .media.audio_chatter import load_fragments, generate_schedule, write_schedule_json, render_tts_script, write_placeholder_wav
from .noticing.benchmark import EvidencePack, run_pack, render_benchmark_report

from .preprocessing.pipeline import preprocess_file
from .preprocessing.code_windows import extract_code_windows
from .search.adapters import conversation_documents, chunk_documents
from .search.index import build_search_index
from .conversations.sentence_preprocessor import preprocess_sentences, to_tsv
from .conversations.splitter import split_many
from .repo_overlay import apply_source



def cmd_extract(args):
    rows = []
    for conv in load_conversations(args.input):
        for msg in conv.messages:
            for snip in extract_snippets(msg.content):
                rows.append({"conversation_id": conv.id, "message_id": msg.id, "kind": snip.kind, "language": snip.language, "text": snip.text})
    Path(args.out).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_index(args):
    conversations = load_conversations(args.input)
    index = InvertedIndex().build(conversations)
    data = {
        "terms": sorted(index.postings.keys()),
        "spines": [{"conversation_id": s.conversation_id, "title": s.title, "message_ids": s.message_ids} for s in build_spines(conversations)],
        "quote_anchors": [asdict(a) for a in extract_quote_anchors(conversations)],
        "turn_signals": [asdict(s) for s in detect_turn_signals(conversations)],
        "artifact_requests": [asdict(a) for a in detect_artifact_requests(conversations)],
    }
    Path(args.out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_noticing_packet(args):
    conversations = load_conversations(args.input)
    packet = generate_packet(conversations, NoticingConfig(max_fragments=args.max_fragments, random_seed=args.seed))
    Path(args.out).write_text(render_packet_markdown(packet), encoding="utf-8")


def cmd_analytics(args):
    conversations = load_conversations(args.input)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    summary = {"role_counts": role_counts(conversations), "role_token_counts": role_token_counts(conversations), "semantic_payload": corpus_payload(conversations)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if conversations:
        trend = conversation_output_trend(conversations[0])
        (out / "trend.json").write_text(json.dumps([asdict(t) for t in trend], indent=2), encoding="utf-8")
        write_trend_svg([t.rolling_assistant for t in trend], out / "assistant_trend.svg")


def cmd_doc_export(args):
    text = Path(args.input).read_text(encoding="utf-8")
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    (out / "word_count.json").write_text(json.dumps({"words": markdown_word_count(text), "outline": heading_outline(text)}, indent=2), encoding="utf-8")
    if args.pdf:
        markdown_to_pdf(text, out / "document.pdf")


def cmd_convert(args):
    if args.list:
        print(render_available_conversions())
        return
    if not args.input or not args.output:
        raise SystemExit("apex convert requires input and output paths unless --list is used")
    result = convert_file(args.input, args.output, from_format=args.from_format, to_format=args.to_format, prefer_pandoc=not args.no_pandoc)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"converted {result.input_format} -> {result.output_format}: {result.output_path} [{result.method}]")
        for warning in result.warnings:
            print(f"warning: {warning}")


def cmd_deps_doctor(args):
    statuses = dependency_report(args.tool or ["ffmpeg", "pandoc"])
    text = render_dependency_report(statuses)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


def cmd_deps_install(args):
    tools = args.tool or ["ffmpeg", "pandoc"]
    log = install_system_tools(tools, assume_yes=args.yes, dry_run=args.dry_run, only_missing=not args.force)
    if args.json:
        print(json.dumps(log, indent=2))
    elif not log:
        print("all requested tools already present")
    else:
        for row in log:
            cmd = " ".join(row["command"])
            if row.get("dry_run"):
                print(f"would run: {cmd}")
            else:
                print(f"ran: {cmd} -> {row.get('returncode')}")



def _openrouter_extra(args):
    return json.loads(args.extra) if getattr(args, "extra", None) else {}


def _write_and_print(text: str, out: str | None = None):
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
    print(text)


def _client_from_args(args) -> OpenRouterClient:
    return OpenRouterClient(api_key=args.api_key, api_key_file=getattr(args, "api_key_file", None), base_url=args.base_url, http_referer=args.http_referer, title=args.title, timeout_s=args.timeout)


def _run_chat_api(args, *, dry_run_label: bool = False):
    messages = build_messages(prompt=args.prompt, system=args.system, messages_file=args.messages)
    extra = _openrouter_extra(args)
    payload = {"model": args.model, "messages": messages}
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    if args.max_tokens is not None:
        payload["max_tokens"] = args.max_tokens
    if extra:
        payload.update(extra)
    if args.dry_run:
        if dry_run_label:
            payload = {"wire_format": "chat-completions", "endpoint": "/chat/completions", "payload": payload}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    client = _client_from_args(args)
    if args.stream:
        chunks = client.chat_completion(model=args.model, messages=messages, temperature=args.temperature, max_tokens=args.max_tokens, stream=True, extra=extra)
        collected = []
        for chunk in chunks:
            delta = stream_delta_text(chunk)
            if delta:
                print(delta, end="", flush=True)
                collected.append(delta)
        print()
        if args.out:
            Path(args.out).write_text("".join(collected), encoding="utf-8")
        return
    response = client.chat_completion(model=args.model, messages=messages, temperature=args.temperature, max_tokens=args.max_tokens, extra=extra)
    text = json.dumps(response, indent=2, ensure_ascii=False) if args.json else chat_text_from_response(response)
    _write_and_print(text, args.out)


def _run_responses_api(args, *, dry_run_label: bool = False):
    messages = build_messages(prompt=args.prompt, system=args.system, messages_file=args.messages)
    input_payload, instructions = messages_to_responses_input(messages)
    extra = _openrouter_extra(args)
    payload = {"model": args.model, "input": input_payload}
    if instructions:
        payload["instructions"] = instructions
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    max_output = getattr(args, "max_output_tokens", None) or getattr(args, "max_tokens", None)
    if max_output is not None:
        payload["max_output_tokens"] = max_output
    if extra:
        payload.update(extra)
    if args.dry_run:
        if dry_run_label:
            payload = {"wire_format": "openai-responses", "endpoint": "/responses", "payload": payload}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    client = _client_from_args(args)
    if args.stream:
        chunks = client.create_response(model=args.model, input=input_payload, instructions=instructions, temperature=args.temperature, max_output_tokens=max_output, stream=True, extra=extra)
        collected = []
        for chunk in chunks:
            delta = response_stream_delta_text(chunk)
            if delta:
                print(delta, end="", flush=True)
                collected.append(delta)
        print()
        if args.out:
            Path(args.out).write_text("".join(collected), encoding="utf-8")
        return
    response = client.create_response(model=args.model, input=input_payload, instructions=instructions, temperature=args.temperature, max_output_tokens=max_output, extra=extra)
    text = json.dumps(response, indent=2, ensure_ascii=False) if args.json else text_from_response_api(response)
    _write_and_print(text, args.out)


def _run_messages_api(args, *, dry_run_label: bool = False):
    messages = build_messages(prompt=args.prompt, system=None, messages_file=args.messages)
    extra = _openrouter_extra(args)
    payload = {"model": args.model, "messages": messages}
    if args.system:
        payload["system"] = args.system
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    if args.max_tokens is not None:
        payload["max_tokens"] = args.max_tokens
    if extra:
        payload.update(extra)
    if args.dry_run:
        if dry_run_label:
            payload = {"wire_format": "anthropic-messages", "endpoint": "/messages", "payload": payload}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    client = _client_from_args(args)
    if args.stream:
        chunks = client.create_message(model=args.model, messages=messages, system=args.system, temperature=args.temperature, max_tokens=args.max_tokens, stream=True, extra=extra)
        collected = []
        for chunk in chunks:
            delta = message_stream_delta_text(chunk)
            if delta:
                print(delta, end="", flush=True)
                collected.append(delta)
        print()
        if args.out:
            Path(args.out).write_text("".join(collected), encoding="utf-8")
        return
    response = client.create_message(model=args.model, messages=messages, system=args.system, temperature=args.temperature, max_tokens=args.max_tokens, extra=extra)
    text = json.dumps(response, indent=2, ensure_ascii=False) if args.json else text_from_message_api(response)
    _write_and_print(text, args.out)


def cmd_llm(args):
    wire_format = args.wire_format
    if wire_format == "auto":
        wire_format = recommended_wire_format_for_model(args.model)
    if wire_format == "openai-responses":
        _run_responses_api(args, dry_run_label=True)
    elif wire_format == "anthropic-messages":
        _run_messages_api(args, dry_run_label=True)
    elif wire_format == "chat-completions":
        _run_chat_api(args, dry_run_label=True)
    else:
        raise SystemExit(f"unknown OpenRouter wire format: {wire_format}")


def cmd_models_refresh(args):
    client = OpenRouterClient(api_key=args.api_key, api_key_file=getattr(args, "api_key_file", None), base_url=args.base_url, http_referer=args.http_referer, title=args.title, timeout_s=args.timeout)
    out = client.write_models_snapshot(args.out, require_auth=args.require_auth)
    print(f"wrote OpenRouter model snapshot: {out}")


def cmd_models_list(args):
    try:
        snapshot, source = load_models_snapshot(args.input, fallback_to_seed=not args.no_seed_fallback)
        rows = compact_model_options(rows_from_snapshot(snapshot), limit=args.limit)
    except FileNotFoundError:
        raise SystemExit(f"model snapshot not found: {args.input}")
    if args.json:
        print(json.dumps({"source": source, "models": rows}, indent=2, ensure_ascii=False))
        return
    if source == "bundled-starter-catalog":
        print("# using bundled starter catalog; run `apex models refresh` for live OpenRouter prices")
    for row in rows:
        pricing = row.get("pricing", {}) if isinstance(row, dict) else {}
        prompt = pricing.get("prompt", "?") if isinstance(pricing, dict) else "?"
        completion = pricing.get("completion", "?") if isinstance(pricing, dict) else "?"
        name = row.get("name") or ""
        print(f"{row.get('id', '(unknown)')}\tprompt={prompt}\tcompletion={completion}\t{name}")


def cmd_cost(args):
    report = estimate_request_costs(args.rates, args.requests)
    if args.out:
        write_cost_report(args.out, report)
    if args.json or not args.out:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"estimated {report['request_count']} request(s): ${report['total_usd']}")


def cmd_web_api(args):
    from .web_api import run_dev_server

    run_dev_server(host=args.host, port=args.port, debug=args.debug, workdir=args.workdir, allow_install=args.allow_install)


def cmd_web_info(args):
    info = {
        "api": "apex web api --host 0.0.0.0 --port 8765",
        "react_dev": "cd apps/web && npm install && npm run dev -- --host 0.0.0.0",
        "api_base_env": "VITE_APEX_API_BASE=http://localhost:8765",
        "notes": "The Flask API exposes structured endpoints; it does not execute arbitrary CLI strings.",
    }
    print(json.dumps(info, indent=2))


def cmd_rates_example(args):
    out = write_example_rates(args.out)
    print(f"wrote example rate file: {out}")


def cmd_rates_seed(args):
    out = write_seed_rates(args.out)
    info = seed_rates_info()
    print(f"wrote starter OpenRouter rate file with {info['model_count']} models: {out}")


def cmd_chatter(args):
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    schedule = generate_schedule(load_fragments(args.fragments), seed=args.seed)
    write_schedule_json(schedule, out / "schedule.json")
    (out / "tts_script.txt").write_text(render_tts_script(schedule), encoding="utf-8")
    write_placeholder_wav(schedule, out / "placeholder.wav")


def cmd_benchmark(args):
    conversations = load_conversations(args.input)
    pack = EvidencePack("fixture", conversations, expected_fragment_terms=args.expected_term or [])
    Path(args.out).write_text(render_benchmark_report([run_pack(pack)]), encoding="utf-8")




def cmd_preprocess(args):
    result = preprocess_file(args.input, dedupe=not args.no_dedupe)
    data = {
        "dropped_message_ids": result.dropped_message_ids,
        "conversations": [c.to_dict() for c in result.conversations],
    }
    Path(args.out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_code_windows(args):
    conversations = load_conversations(args.input)
    windows = extract_code_windows(conversations, radius=args.radius, min_score=args.min_score)
    data = [
        {
            "conversation_id": w.conversation_id,
            "center_message_id": w.center_message_id,
            "start_ordinal": w.start_ordinal,
            "end_ordinal": w.end_ordinal,
            "score": w.score,
            "message_ids": [m.id for m in w.messages],
        }
        for w in windows
    ]
    Path(args.out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_search(args):
    conversations = load_conversations(args.input)
    docs = conversation_documents(conversations)
    idx = build_search_index(docs)
    results = idx.search(args.query, limit=args.limit)
    data = [{"id": d.id, "score": score, "metadata": d.metadata, "text": d.text} for d, score in results]
    Path(args.out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_sentences(args):
    conversations = load_conversations(args.input)
    rows = preprocess_sentences(conversations)
    Path(args.out).write_text(to_tsv(rows), encoding="utf-8")


def cmd_chunks(args):
    conversations = load_conversations(args.input)
    chunks = split_many(conversations, max_tokens=args.max_tokens)
    data = [
        {
            "id": c.id,
            "conversation_id": c.conversation_id,
            "title": c.title,
            "start_ordinal": c.start_ordinal,
            "end_ordinal": c.end_ordinal,
            "message_ids": [m.id for m in c.messages],
            "text": c.text(),
        }
        for c in chunks
    ]
    Path(args.out).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")




def _require_optional_feature(name: str, exc: ImportError):
    raise SystemExit(f"{name} requires optional dependencies. Run: python -m pip install -e '.[all]'\nMissing import: {exc}") from exc


def cmd_image_metadata(args):
    try:
        from .media.image_metadata import check_metadata
    except ImportError as exc:
        _require_optional_feature("image metadata inspection", exc)
    check_metadata(Path(args.image))


def cmd_flux_distill(args):
    try:
        from .media import flux_pipeline
    except ImportError as exc:
        _require_optional_feature("flux prompt distillation", exc)
    argv = ["--source", args.source, "--out", args.out, "--prompt-count", str(args.prompt_count)]
    flux_pipeline.main(argv)


def cmd_flux_variants(args):
    from .media import flux_subject_variants
    flux_subject_variants.main(["--base-dir", args.base_dir, "--out-dir", args.out_dir])


def cmd_chatter_build(args):
    try:
        from .media import audio_chatter_builder
    except ImportError as exc:
        _require_optional_feature("audio chatter building", exc)
    argv = [
        "--input", args.input,
        "--output-root", args.output_root,
        "--track-count", str(args.track_count),
        "--track-seconds", str(args.track_seconds),
        "--seed", str(args.seed),
        "--sample-rate", str(args.sample_rate),
        "--min-gap", str(args.min_gap),
        "--max-gap", str(args.max_gap),
        "--sentence-bitrate", args.sentence_bitrate,
        "--track-bitrate", args.track_bitrate,
        "--min-silence-ms", str(args.min_silence_ms),
        "--keep-silence-ms", str(args.keep_silence_ms),
        "--minimum-clip-ms", str(args.minimum_clip_ms),
        "--silence-thresh-offset-db", str(args.silence_thresh_offset_db),
    ]
    if args.drop_first_chunk:
        argv.append("--drop-first-chunk")
    audio_chatter_builder.main(argv)


def cmd_output_trends_extract(args):
    try:
        from .analytics.output_trends_export import extract_metrics
    except ImportError as exc:
        _require_optional_feature("output trends extraction", exc)
    argv = ["--zip", args.zip, "--out", args.out, "--session-gap-minutes", str(args.session_gap_minutes)]
    if args.extract_dir:
        argv += ["--extract-dir", args.extract_dir]
    extract_metrics.main(argv)


def cmd_output_trends_charts(args):
    try:
        from .analytics.output_trends_export import make_charts
    except ImportError as exc:
        _require_optional_feature("output trends charts", exc)
    make_charts.main(["--metrics-dir", args.metrics_dir, "--drop-days", str(args.drop_days)])


def cmd_output_trends_peaks(args):
    try:
        from .analytics.output_trends_export import make_peaks
    except ImportError as exc:
        _require_optional_feature("output trends peaks", exc)
    argv = ["--zip", args.zip, "--metrics-dir", args.metrics_dir]
    if args.extract_dir:
        argv += ["--extract-dir", args.extract_dir]
    make_peaks.main(argv)


def cmd_output_trends_key(args):
    try:
        from .analytics.output_trends_export import make_peak_pdf_key
    except ImportError as exc:
        _require_optional_feature("output trends PDF key", exc)
    argv = ["--metrics-dir", args.metrics_dir]
    if args.render_check:
        argv.append("--render-check")
    make_peak_pdf_key.main(argv)


def cmd_output_trends_bundle(args):
    from .analytics.output_trends_export import make_bundle
    make_bundle.main(["--metrics-dir", args.metrics_dir, "--zip-out", args.zip_out])


def cmd_output_trends_run(args):
    class _A: pass
    extract = _A(); extract.zip=args.zip; extract.out=args.out; extract.extract_dir=args.extract_dir; extract.session_gap_minutes=args.session_gap_minutes
    cmd_output_trends_extract(extract)
    charts = _A(); charts.metrics_dir=args.out; charts.drop_days=args.drop_days
    cmd_output_trends_charts(charts)
    peaks = _A(); peaks.zip=args.zip; peaks.metrics_dir=args.out; peaks.extract_dir=args.extract_dir
    cmd_output_trends_peaks(peaks)
    key = _A(); key.metrics_dir=args.out; key.render_check=args.render_check
    cmd_output_trends_key(key)
    if args.zip_out:
        bundle = _A(); bundle.metrics_dir=args.out; bundle.zip_out=args.zip_out
        cmd_output_trends_bundle(bundle)

def cmd_repo_apply(args):
    report = apply_source(
        args.source,
        repo=args.repo,
        apply=args.apply,
        match_mode=args.match,
        backup_dir=args.backup_dir,
        create_missing=args.create_missing,
        target=args.target,
        fuzzy_threshold=args.fuzzy_threshold,
        cross_extension=args.cross_extension,
    )
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.json or args.out:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        summary = report["summary"]
        verb = "overwrote" if summary["applied"] else "would overwrite"
        print(
            f"{verb} {summary['matched_count']} of {summary['incoming_count']} incoming file(s); "
            f"created={summary.get('created_count', 0)} would_create={summary.get('would_create_count', 0)} "
            f"ambiguous={summary['ambiguous_count']} no_match={summary['no_match_count']}"
        )
        if summary.get("backup_dir"):
            print(f"backup: {summary['backup_dir']}")
        for row in report["matches"]:
            target = row.get("target_path") or "-"
            print(f"{row['status']}	{row['incoming_path']}	->	{target}	{row.get('method') or ''}")


def cmd_tex_validate(args):
    tex = Path(args.input).read_text(encoding="utf-8")
    Path(args.out).write_text(json.dumps(summarize_tex_atlas(tex), indent=2, ensure_ascii=False), encoding="utf-8")



def cmd_keys_status(args):
    status = secret_status(args.provider, args.path).to_dict()
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(f"{status['provider']} key file: {status['path']}")
        print(f"exists: {status['exists']}")
        print(f"readable: {status['readable']}")
        if status.get('mode'):
            print(f"mode: {status['mode']}")


def cmd_keys_path(args):
    print(secret_path(args.provider, args.path))


def cmd_keys_set(args):
    if args.stdin:
        import sys
        value = sys.stdin.read().strip()
    elif args.value:
        value = args.value
    elif args.file:
        value = Path(args.file).read_text(encoding="utf-8").strip()
    else:
        raise SystemExit("provide --stdin, --value, or --file")
    out = write_secret(value, args.provider, args.path)
    print(f"wrote {args.provider} key file: {out}")



def _add_openrouter_common_args(p):
    p.add_argument("--model", required=True)
    p.add_argument("--prompt")
    p.add_argument("--system")
    p.add_argument("--messages")
    p.add_argument("--temperature", type=float)
    p.add_argument("--max-tokens", type=int, help="Maximum output tokens. Mapped onto the selected wire format's native field name.")
    p.add_argument("--stream", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--out")
    p.add_argument("--api-key", help="Explicit key for one-off/debug calls. Prefer `apex keys set openrouter --stdin`.")
    p.add_argument("--api-key-file", help="Path to a file containing the OpenRouter API key. Defaults to ~/.config/apex/openrouter.key.")
    p.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    p.add_argument("--http-referer")
    p.add_argument("--title", default="apex-dev")
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--extra", help="JSON object merged into the request payload")
    p.add_argument(
        "--wire-format",
        choices=["auto", "openai-responses", "anthropic-messages", "chat-completions"],
        default="auto",
        help=(
            "OpenRouter compatibility wire format. "
            "auto chooses openai-responses for openai/*, anthropic-messages for anthropic/*, "
            "and chat-completions for everything else."
        ),
    )

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="apex")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("extract"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_extract)
    p = sub.add_parser("index"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_index)
    p = sub.add_parser("noticing-packet"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.add_argument("--seed", type=int, default=0); p.add_argument("--max-fragments", type=int, default=24); p.set_defaults(func=cmd_noticing_packet)
    p = sub.add_parser("analytics"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_analytics)
    p = sub.add_parser("doc-export"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.add_argument("--pdf", action="store_true"); p.set_defaults(func=cmd_doc_export)
    p = sub.add_parser("convert", help="convert files by suffix or explicit --from/--to"); p.add_argument("input", nargs="?"); p.add_argument("output", nargs="?"); p.add_argument("--from", dest="from_format"); p.add_argument("--to", dest="to_format"); p.add_argument("--no-pandoc", action="store_true"); p.add_argument("--json", action="store_true"); p.add_argument("--list", action="store_true"); p.set_defaults(func=cmd_convert)

    p = sub.add_parser("llm", help="send a prompt through OpenRouter; select provider/API compatibility with --wire-format")
    _add_openrouter_common_args(p); p.set_defaults(func=cmd_llm)

    p_models = sub.add_parser("models", help="OpenRouter model catalog tools")
    models_sub = p_models.add_subparsers(dest="models_cmd", required=True)
    p = models_sub.add_parser("refresh", help="download /api/v1/models to a local snapshot"); p.add_argument("--out", default="rates/openrouter.models.json"); p.add_argument("--api-key", help="Explicit key for one-off/debug calls. Prefer `apex keys set openrouter --stdin`."); p.add_argument("--api-key-file", help="Path to a file containing the OpenRouter API key. Defaults to ~/.config/apex/openrouter.key."); p.add_argument("--base-url", default="https://openrouter.ai/api/v1"); p.add_argument("--http-referer"); p.add_argument("--title", default="apex-dev"); p.add_argument("--timeout", type=float, default=120.0); p.add_argument("--require-auth", action="store_true"); p.set_defaults(func=cmd_models_refresh)
    p = models_sub.add_parser("list", help="list model ids/prices from a local snapshot or bundled starter catalog"); p.add_argument("--input", default="rates/openrouter.models.json"); p.add_argument("--limit", type=int, default=50); p.add_argument("--json", action="store_true"); p.add_argument("--no-seed-fallback", action="store_true", help="fail if the snapshot file is missing instead of using the bundled starter catalog"); p.set_defaults(func=cmd_models_list)

    p = sub.add_parser("cost", help="estimate OpenRouter request costs from local rates + JSON/JSONL usage records"); p.add_argument("--rates", required=True); p.add_argument("--requests", required=True); p.add_argument("--out"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_cost)

    p_web = sub.add_parser("web", help="run or inspect the Flask/React web surface")
    web_sub = p_web.add_subparsers(dest="web_cmd", required=True)
    p = web_sub.add_parser("api", help="run the Flask API that exposes apex operations")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--debug", action="store_true")
    p.add_argument("--workdir", default=".apex-web")
    p.add_argument("--allow-install", action="store_true", help="allow non-dry-run /api/deps/install calls")
    p.set_defaults(func=cmd_web_api)
    p = web_sub.add_parser("info", help="print commands for running the API and React app")
    p.set_defaults(func=cmd_web_info)

    p_rates = sub.add_parser("rates", help="local rate-file helpers")
    rates_sub = p_rates.add_subparsers(dest="rates_cmd", required=True)
    p = rates_sub.add_parser("example"); p.add_argument("--out", default="rates/example.openrouter.models.json"); p.set_defaults(func=cmd_rates_example)
    p = rates_sub.add_parser("seed", help="write bundled starter OpenRouter catalog/rates"); p.add_argument("--out", default="rates/openrouter.models.json"); p.set_defaults(func=cmd_rates_seed)
    p_keys = sub.add_parser("keys", help="file-backed API key helpers")
    keys_sub = p_keys.add_subparsers(dest="keys_cmd", required=True)
    p = keys_sub.add_parser("status", help="show key-file status without printing the secret"); p.add_argument("provider", nargs="?", default="openrouter"); p.add_argument("--path"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_keys_status)
    p = keys_sub.add_parser("path", help="print the default key-file path"); p.add_argument("provider", nargs="?", default="openrouter"); p.add_argument("--path"); p.set_defaults(func=cmd_keys_path)
    p = keys_sub.add_parser("set", help="write a provider API key to a chmod 600 file"); p.add_argument("provider", nargs="?", default="openrouter"); p.add_argument("--path"); p.add_argument("--value"); p.add_argument("--file"); p.add_argument("--stdin", action="store_true"); p.set_defaults(func=cmd_keys_set)

    p_deps = sub.add_parser("deps", help="check/install external tools such as ffmpeg and pandoc")
    deps_sub = p_deps.add_subparsers(dest="deps_cmd", required=True)
    p = deps_sub.add_parser("doctor"); p.add_argument("tool", nargs="*"); p.add_argument("--out"); p.set_defaults(func=cmd_deps_doctor)
    p = deps_sub.add_parser("install"); p.add_argument("tool", nargs="*"); p.add_argument("--yes", action="store_true"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--force", action="store_true"); p.add_argument("--json", action="store_true"); p.set_defaults(func=cmd_deps_install)

    p = sub.add_parser("image-metadata", help="inspect image metadata without printing image pixels"); p.add_argument("image"); p.set_defaults(func=cmd_image_metadata)

    p_flux = sub.add_parser("flux", help="prompt corpus distillation and subject variant helpers")
    flux_sub = p_flux.add_subparsers(dest="flux_cmd", required=True)
    p = flux_sub.add_parser("distill", help="extract prompt terms, generate prompt samples, and write reports"); p.add_argument("--source", required=True); p.add_argument("--out", required=True); p.add_argument("--prompt-count", type=int, default=720); p.set_defaults(func=cmd_flux_distill)
    p = flux_sub.add_parser("variants", help="generate male-subject and animal-subject prompt variants from a distillation output"); p.add_argument("--base-dir", required=True); p.add_argument("--out-dir", required=True); p.set_defaults(func=cmd_flux_variants)

    p = sub.add_parser("chatter", help="make a placeholder chatter schedule from text fragments"); p.add_argument("--fragments", required=True); p.add_argument("--out", required=True); p.add_argument("--seed", type=int, default=0); p.set_defaults(func=cmd_chatter)
    p = sub.add_parser("chatter-build", help="split source audio into clips and build layered chatter tracks")
    p.add_argument("--input", required=True); p.add_argument("--output-root", default="out_chatter"); p.add_argument("--drop-first-chunk", action="store_true"); p.add_argument("--track-count", type=int, default=360); p.add_argument("--track-seconds", type=int, default=120); p.add_argument("--seed", type=int, default=60526); p.add_argument("--sample-rate", type=int, default=44100); p.add_argument("--min-gap", type=float, default=4.0); p.add_argument("--max-gap", type=float, default=24.0); p.add_argument("--sentence-bitrate", default="96k"); p.add_argument("--track-bitrate", default="160k"); p.add_argument("--min-silence-ms", type=int, default=550); p.add_argument("--keep-silence-ms", type=int, default=110); p.add_argument("--minimum-clip-ms", type=int, default=350); p.add_argument("--silence-thresh-offset-db", type=float, default=-16.0); p.set_defaults(func=cmd_chatter_build)

    p_ot = sub.add_parser("output-trends", help="conversation-export output metrics, charts, peaks, and bundles")
    ot_sub = p_ot.add_subparsers(dest="output_trends_cmd", required=True)
    p = ot_sub.add_parser("extract"); p.add_argument("--zip", required=True); p.add_argument("--out", required=True); p.add_argument("--extract-dir"); p.add_argument("--session-gap-minutes", type=float, default=60.0); p.set_defaults(func=cmd_output_trends_extract)
    p = ot_sub.add_parser("charts"); p.add_argument("--metrics-dir", required=True); p.add_argument("--drop-days", type=int, default=8); p.set_defaults(func=cmd_output_trends_charts)
    p = ot_sub.add_parser("peaks"); p.add_argument("--zip", required=True); p.add_argument("--metrics-dir", required=True); p.add_argument("--extract-dir"); p.set_defaults(func=cmd_output_trends_peaks)
    p = ot_sub.add_parser("key"); p.add_argument("--metrics-dir", required=True); p.add_argument("--render-check", action="store_true"); p.set_defaults(func=cmd_output_trends_key)
    p = ot_sub.add_parser("bundle"); p.add_argument("--metrics-dir", required=True); p.add_argument("--zip-out", required=True); p.set_defaults(func=cmd_output_trends_bundle)
    p = ot_sub.add_parser("run", help="run extract, charts, peaks, key, and optional bundle in sequence"); p.add_argument("--zip", required=True); p.add_argument("--out", required=True); p.add_argument("--extract-dir"); p.add_argument("--session-gap-minutes", type=float, default=60.0); p.add_argument("--drop-days", type=int, default=8); p.add_argument("--render-check", action="store_true"); p.add_argument("--zip-out"); p.set_defaults(func=cmd_output_trends_run)
    p = sub.add_parser("benchmark"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.add_argument("--expected-term", action="append"); p.set_defaults(func=cmd_benchmark)
    p = sub.add_parser("preprocess"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.add_argument("--no-dedupe", action="store_true"); p.set_defaults(func=cmd_preprocess)
    p = sub.add_parser("code-windows"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.add_argument("--radius", type=int, default=2); p.add_argument("--min-score", type=float, default=5.0); p.set_defaults(func=cmd_code_windows)
    p = sub.add_parser("search"); p.add_argument("--input", required=True); p.add_argument("--query", required=True); p.add_argument("--out", required=True); p.add_argument("--limit", type=int, default=10); p.set_defaults(func=cmd_search)
    p = sub.add_parser("sentences"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_sentences)
    p = sub.add_parser("chunks"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.add_argument("--max-tokens", type=int, default=1200); p.set_defaults(func=cmd_chunks)

    p_repo = sub.add_parser("repo", help="repo maintenance helpers")
    repo_sub = p_repo.add_subparsers(dest="repo_cmd", required=True)
    p = repo_sub.add_parser("apply", help="match incoming files from a file/folder/zip to repo files and optionally write them")
    p.add_argument("source", help="file, folder, or zip containing incoming files")
    p.add_argument("--repo", default=".", help="repository root to patch; defaults to current directory")
    p.add_argument("--match", choices=["auto", "path", "suffix", "name", "stem", "content", "similarity", "exact", "basename", "fuzzy"], default="auto", help="matching strategy; auto tries safe path/name/stem matches; similarity is explicit")
    p.add_argument("--target", help="explicit target repo-relative path; source must resolve to one incoming file")
    p.add_argument("--create-missing", action="store_true", help="create unmatched files at their incoming relative paths, or at --target for a single file")
    p.add_argument("--fuzzy-threshold", type=float, default=0.78, help="minimum similarity score for --match similarity/fuzzy")
    p.add_argument("--cross-extension", action="store_true", help="allow similarity matching across file extensions")
    p.add_argument("--apply", action="store_true", help="actually overwrite/create files; default is preview only")
    p.add_argument("--backup-dir", help="backup matched originals here before applying")
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", help="write the apply report JSON to this path")
    p.set_defaults(func=cmd_repo_apply)

    p = sub.add_parser("tex-validate"); p.add_argument("--input", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_tex_validate)


    args = parser.parse_args(argv)
    args.func(args)
    return 0
