import os
import re
import math
import json
from typing import Dict, Any, List, Optional, Tuple

from openai import OpenAI
from budget_manager import budget_manager, ModelType
from vector_store import query_documents
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EXCERPT_MAX = 400


def _where_for_sources(sources: List[str]) -> dict:
    unique = [s for s in dict.fromkeys(sources) if s]
    if len(unique) == 1:
        return {"source": unique[0]}
    return {"$or": [{"source": s} for s in unique]}


def _meta_page(meta: Optional[dict], chunk_id: Optional[str] = None) -> Optional[int]:
    """Normalize page from metadata; fallback to chunk-id pattern like `_p12_`."""
    if not meta:
        p = None
    else:
        p = meta.get("page")
        if p is not None:
            try:
                return int(float(p))
            except (TypeError, ValueError):
                pass
        pidx = meta.get("page_index")
        if pidx is not None:
            try:
                return int(float(pidx)) + 1
            except (TypeError, ValueError):
                pass
    if chunk_id:
        m = re.search(r"_p(\d+)_", str(chunk_id))
        if m:
            try:
                return int(m.group(1))
            except (TypeError, ValueError):
                pass
    return None


def _distance_to_similarity(d: Optional[float]) -> float:
    if d is None or (isinstance(d, float) and math.isnan(d)):
        return 0.0
    try:
        x = float(d)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, math.exp(-x)))


def _pad_query_rows(results: dict) -> Tuple[List, List, List, List]:
    row_docs = (results.get("documents") or [[]])[0]
    row_metas = (results.get("metadatas") or [[]])[0]
    row_dists = (results.get("distances") or [[]])[0]
    row_ids = (results.get("ids") or [[]])[0]
    n = max(len(row_docs), len(row_metas), len(row_dists), len(row_ids))
    return (
        list(row_docs) + [""] * (n - len(row_docs)),
        list(row_metas) + [None] * (n - len(row_metas)),
        list(row_dists) + [None] * (n - len(row_dists)),
        list(row_ids) + [None] * (n - len(row_ids)),
    )


def _build_evidence_items(
    docs: List[str],
    metas: List[Optional[dict]],
    dists: List[Optional[float]],
    ids: List[Optional[str]],
    allow: Optional[set[str]],
    max_items: int,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    contexts: List[str] = []
    evidence: List[Dict[str, Any]] = []

    for doc, meta, dist, cid in zip(docs, metas, dists, ids):
        if not doc:
            continue
        src = (meta or {}).get("source")
        if allow and (not meta or src not in allow):
            continue

        rank = len(evidence) + 1
        rank_conf = max(0.05, 1.0 - ((rank - 1) * 0.08))
        vec_sim = _distance_to_similarity(dist)
        confidence = round(0.5 * rank_conf + 0.5 * vec_sim, 4)
        page = _meta_page(meta, cid)

        excerpt = doc.strip().replace("\n", " ")
        if len(excerpt) > EXCERPT_MAX:
            excerpt = excerpt[: EXCERPT_MAX - 1] + "…"

        try:
            dist_f = float(dist) if dist is not None else None
        except (TypeError, ValueError):
            dist_f = None

        meta = meta or {}
        content_type = meta.get("content_type")
        extraction_method = meta.get("extraction_method")

        evidence.append(
            {
                "chunk_id": cid,
                "source": src,
                "page": page,
                "excerpt": excerpt,
                "full_text_length": len(doc),
                "confidence_score": confidence,
                "vector_distance": dist_f,
                "retrieval_rank": rank,
                "content_type": content_type,
                "extraction_method": extraction_method,
            }
        )
        contexts.append(doc)
        if len(contexts) >= max_items:
            break

    return contexts, evidence


def _retrieve_balanced_multi_source(
    user_query: str, allow: set[str], max_contexts: int
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    When multiple PDFs are scoped, query each file separately so comparison questions
    get chunks from every selected document (not only the single best-matching file).
    """
    sources_list = list(allow)
    per_file = max(5, (max_contexts + len(sources_list) - 1) // len(sources_list))

    best: dict[str, Tuple[str, Optional[dict], Optional[float], Optional[str]]] = {}

    def dist_key(d: Optional[float]) -> float:
        if d is None:
            return 9999.0
        try:
            return float(d)
        except (TypeError, ValueError):
            return 9999.0

    for src in sources_list:
        results = query_documents(
            [user_query], n_results=per_file, where={"source": src}
        )
        row_docs, row_metas, row_dists, row_ids = _pad_query_rows(results)
        for doc, meta, dist, cid in zip(row_docs, row_metas, row_dists, row_ids):
            if not doc or not cid:
                continue
            if (meta or {}).get("source") != src:
                continue
            if cid not in best or dist_key(dist) < dist_key(best[cid][2]):
                best[cid] = (doc, meta, dist, cid)

    if not best:
        return [], []

    merged = sorted(best.values(), key=lambda row: dist_key(row[2]))[:max_contexts]
    docs, metas, dists, ids = zip(*merged)
    return _build_evidence_items(
        list(docs), list(metas), list(dists), list(ids), allow, max_contexts
    )


def _retrieve_filtered_with_evidence(
    user_query: str, selected_files: Optional[List[str]]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    allow: Optional[set[str]] = None
    if selected_files:
        allow = {f for f in selected_files if f}

    max_contexts = 15 if allow else 8

    if allow and len(allow) >= 2:
        contexts, evidence = _retrieve_balanced_multi_source(
            user_query, allow, max_contexts
        )
        if len(contexts) < 1:
            wide = query_documents([user_query], n_results=50, where=None)
            wd, wm, wdist, wid = _pad_query_rows(wide)
            contexts, evidence = _build_evidence_items(
                wd, wm, wdist, wid, allow, max_contexts
            )
        return contexts, evidence

    n_results = 24 if allow else 10
    where_clause = _where_for_sources(list(allow)) if allow else None

    results = query_documents([user_query], n_results=n_results, where=where_clause)
    row_docs, row_metas, row_dists, row_ids = _pad_query_rows(results)

    contexts, evidence = _build_evidence_items(
        row_docs, row_metas, row_dists, row_ids, allow, max_contexts
    )

    if allow and len(contexts) < 1:
        wide = query_documents([user_query], n_results=50, where=None)
        wd, wm, wdist, wid = _pad_query_rows(wide)
        contexts, evidence = _build_evidence_items(
            wd, wm, wdist, wid, allow, max_contexts
        )

    return contexts, evidence


def _format_labeled_context(contexts: List[str], evidence: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for i, (doc, ev) in enumerate(zip(contexts, evidence), start=1):
        src = ev.get("source") or "unknown"
        pg = ev.get("page")
        conf = ev.get("confidence_score")
        page_part = f"page {int(pg)}" if pg is not None else "page unknown"
        header = f"[E{i}] source: {src} | {page_part} | retrieval_confidence: {conf}"
        parts.append(f"{header}\n{doc.strip()}")
    return "\n\n---\n\n".join(parts)


MULTI_DOC_INSTRUCTION = (
    "\n\nWhen MULTIPLE files appear in the context ([E1], [E2], … from different `source` names), "
    "the user wants cross-document reasoning. Use excerpts from EACH distinct source where possible. "
    "If one company/file has little relevant text in the snippets, say what you can infer from what is shown "
    "and explicitly note which companies lack detail in the provided excerpts. "
    "Never claim that \"no context was retrieved\" if any [E…] blocks are present above."
)

# Core answer formatting and grounding contract.
ANSWER_STYLE_INSTRUCTION = (
    "\n\nANSWER FORMAT (mandatory):\n"
    "1) Start with a short paragraph (3-6 sentences) that directly answers the user's question.\n"
    "2) Then add a heading exactly: `Key points from the provided files`.\n"
    "3) Under that heading, provide 3-7 concise bullet points.\n"
    "4) Every claim must be grounded in the retrieved context blocks [E1], [E2], ... only.\n"
    "   Add inline citations like [E1], [E2] in the paragraph and bullet points.\n"
    "5) If the context is insufficient for any requested part, explicitly state that limitation.\n"
    "6) Do not use external knowledge, assumptions, or prior chat memory outside the provided context."
)

# Model must not duplicate the evidence footer; we append it in code for consistency.
EVIDENCE_CLOSE_INSTRUCTION = (
    "\n\nDo NOT add a \"### Retrieval evidence\" section yourself — it is appended automatically after your reply. "
    "Answer using the labeled [E1], [E2], … blocks. "
    "If you include ```chart-data```, place it after your main answer and before the evidence footer."
)

SCOPED_EVIDENCE_CONSISTENCY_INSTRUCTION = (
    "\n\nSCOPED CONSISTENCY RULE: If one or more [E#] context blocks are present above, "
    "you MUST NOT say 'no evidence', 'no context', or 'no retrieved information'. "
    "Instead, if weak, say the evidence is limited/indirect and explain what is available from the selected files."
)


def _strip_model_evidence_section(text: str) -> str:
    return re.sub(r"\n###\s*Retrieval evidence\b[\s\S]*$", "", text, flags=re.IGNORECASE).rstrip()


def _sanitize_contradictory_no_evidence(text: str, evidence: List[Dict[str, Any]]) -> str:
    """
    Prevent contradictory wording like "no evidence" when retrieval actually returned chunks.
    Keep model meaning, but switch to "limited evidence" phrasing.
    """
    if not evidence:
        return text
    fixed = text
    fixed = re.sub(
        r"\b(no|not enough)\s+(retrieved\s+)?(evidence|context|information)\b",
        "limited retrieved evidence",
        fixed,
        flags=re.IGNORECASE,
    )
    fixed = re.sub(
        r"\bthere\s+is\s+no\s+(retrieved\s+)?(evidence|context|information)\b",
        "there is limited retrieved evidence",
        fixed,
        flags=re.IGNORECASE,
    )
    return fixed


def _append_evidence_footer(evidence: List[Dict[str, Any]]) -> str:
    if not evidence:
        return "\n\n### Retrieval evidence\n\n- No chunks were retrieved for this query."
    lines = ["\n\n### Retrieval evidence\n"]
    for i, ev in enumerate(evidence, 1):
        src = ev.get("source") or "?"
        pg = ev.get("page")
        pg_s = str(pg) if pg is not None else "unknown"
        conf = ev.get("confidence_score")
        cid = ev.get("chunk_id") or f"E{i}"
        ct = ev.get("content_type")
        em = ev.get("extraction_method")
        tag = ""
        if ct or em:
            parts = []
            if ct:
                parts.append(f"content_type: {ct}")
            if em:
                parts.append(f"extraction_method: {em}")
            tag = " | " + ", ".join(parts)
        lines.append(
            f"- **{cid}** | **{src}** | page {pg_s}{tag} | confidence **{conf}** (vector distance: {ev.get('vector_distance')})"
        )
    return "\n".join(lines)


def _finalize_answer(raw_answer: str, evidence: List[Dict[str, Any]]) -> str:
    body = _strip_model_evidence_section(raw_answer)
    body = _sanitize_contradictory_no_evidence(body, evidence)
    body = _ensure_chart_block(body, evidence)
    return body + _append_evidence_footer(evidence)


def _has_chart_block(text: str) -> bool:
    return bool(re.search(r"```chart-data\s*[\s\S]*?```", text, flags=re.IGNORECASE))


def _safe_source_label(src: Optional[str], idx: int) -> str:
    if not src:
        return f"E{idx}"
    base = os.path.basename(str(src))
    return base[:26]


def _fallback_chart_data(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Always produce graphable numeric data when model omits chart-data.
    Uses retrieval confidence as y-axis and source/page as labels.
    """
    rows: List[Dict[str, Any]] = []
    for i, ev in enumerate(evidence[:8], 1):
        conf = ev.get("confidence_score")
        try:
            conf_val = round(float(conf) * 100.0, 2)
        except (TypeError, ValueError):
            conf_val = 0.0
        page = ev.get("page")
        try:
            page_val = int(page) if page is not None else 0
        except (TypeError, ValueError):
            page_val = 0
        rows.append(
            {
                "label": _safe_source_label(ev.get("source"), i),
                "confidence": conf_val,
                "page": page_val,
            }
        )
    if not rows:
        rows = [{"label": "No data", "confidence": 0.0, "page": 0}]
    return rows


def _ensure_chart_block(text: str, evidence: List[Dict[str, Any]]) -> str:
    """
    Guarantee one chart-data block for the UI chart renderer.
    If model did not return one, append fallback chart data.
    """
    if _has_chart_block(text):
        return text
    fallback = _fallback_chart_data(evidence)
    return (
        text.rstrip()
        + "\n\n```chart-data\n"
        + json.dumps(fallback, ensure_ascii=True)
        + "\n```"
    )


def _payload_with_evidence(
    answer: str,
    model: str,
    evidence: List[Dict[str, Any]],
) -> Dict[str, Any]:
    parts = []
    for e in evidence:
        src = e.get("source") or "?"
        pg = e.get("page")
        parts.append(f"{src} p.{pg}" if pg is not None else str(src))
    return {
        "answer": answer,
        "model": model,
        "evidence": evidence,
        "sources_summary": "; ".join(parts) if parts else None,
    }


def ask_question(user_query: str, selected_files: Optional[List[str]] = None) -> Dict[str, Any]:
    scoped = bool(selected_files)
    contexts, evidence = _retrieve_filtered_with_evidence(user_query, selected_files)

    multi = bool(selected_files and len({f for f in selected_files if f}) >= 2)

    if scoped and not contexts:
        context_text = (
            "(No text chunks were retrieved from the selected document(s) for this query. "
            "Do not use outside knowledge; state that the selected files do not contain relevant information.)"
        )
    elif contexts and evidence and len(contexts) == len(evidence):
        context_text = _format_labeled_context(contexts, evidence)
    else:
        context_text = "\n---\n".join(contexts) if contexts else "No relevant documents found."

    scope_instruction = ""
    if scoped and selected_files:
        names = ", ".join(selected_files)
        scope_instruction = (
            f"\n\nThe user limited scope to ONLY these PDF file(s): {names}. "
            "You MUST use only the context above. If it is insufficient, say clearly that "
            "the answer is not found in the selected document(s). Do not invent facts from other sources."
        )

    chart_instruction = (
        "\n\nCHARTS: Include a ```chart-data``` JSON block ONLY when the answer has numeric trend/comparison data "
        "from the provided context. If the answer is qualitative or there are no reliable numeric points in context, "
        "do not output chart-data."
    )

    multi_extra = MULTI_DOC_INSTRUCTION if multi else ""
    scoped_extra = SCOPED_EVIDENCE_CONSISTENCY_INSTRUCTION if scoped and evidence else ""

    system_prompt = (
        "You are a financial intelligence assistant. Given the following context, answer the user's query.\n"
        "If the query requires complex mathematical comparisons or deep multi-document reasoning that you cannot safely and confidently perform, "
        "output exactly and only the word 'ESCALATE'.\n\nContext:\n\n"
        + context_text
        + scope_instruction
        + multi_extra
        + scoped_extra
        + ANSWER_STYLE_INSTRUCTION
        + chart_instruction
        + EVIDENCE_CLOSE_INSTRUCTION
    )

    model_to_use = budget_manager.get_current_model(ModelType.GPT4O_MINI)

    try:
        response = client.chat.completions.create(
            model=model_to_use.value,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ],
        )

        budget_manager.add_cost(
            model_to_use,
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
        )

        answer = response.choices[0].message.content.strip()
    except Exception as e:
        return {"error": str(e)}

    if answer == "ESCALATE":
        if budget_manager.can_use_expensive_model():
            print("Escalating to GPT-4o...")
            model_to_use = ModelType.GPT4O

            try:
                response_esc = client.chat.completions.create(
                    model=model_to_use.value,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a senior financial analyst. Answer this query comprehensively using the context:\n\n"
                                + context_text
                                + scope_instruction
                                + multi_extra
                                + scoped_extra
                                + ANSWER_STYLE_INSTRUCTION
                                + chart_instruction
                                + EVIDENCE_CLOSE_INSTRUCTION
                            ),
                        },
                        {"role": "user", "content": user_query},
                    ],
                )
                budget_manager.add_cost(
                    model_to_use,
                    response_esc.usage.prompt_tokens,
                    response_esc.usage.completion_tokens,
                )
                raw = response_esc.choices[0].message.content.strip()
                return _payload_with_evidence(
                    _finalize_answer(raw, evidence),
                    model_to_use.value,
                    evidence,
                )
            except Exception as e:
                return {"error": str(e)}
        else:
            msg = "The query is too complex, but limits ($7.50 cutoff) have been reached. Unable to escalate."
            return _payload_with_evidence(
                _finalize_answer(msg, evidence),
                model_to_use.value,
                evidence,
            )

    return _payload_with_evidence(
        _finalize_answer(answer, evidence),
        model_to_use.value,
        evidence,
    )
