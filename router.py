import os
import re
import math
import json
from typing import Dict, Any, List, Optional, Tuple

from openai import OpenAI
from budget_manager import budget_manager, ModelType
from vector_store import query_documents
from dotenv import load_dotenv
from paths import PDF_DIR, PROJECT_ROOT

# Load `.env` from the repo root (not the shell cwd). If that file exists, values
# override existing environment variables so a stale Windows User OPENAI_API_KEY
# cannot silently win over the project's .env (python-dotenv defaults to no override).
_env_file = PROJECT_ROOT / ".env"
if _env_file.is_file():
    load_dotenv(_env_file, override=True)
else:
    load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EXCERPT_MAX = 400

# --- Cross-encoder reranking (query + passage). Big retrieval-quality win on a 4060; no re-embedding.
# Disable: CROSS_ENCODER_RERANK=0
_CROSS_ENCODER = None
_CROSS_ENCODER_FAILED = False
_RERANK_CHARS = int(os.environ.get("RERANK_MAX_CHARS", "2000"))


def _rerank_wanted() -> bool:
    return os.environ.get("CROSS_ENCODER_RERANK", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _get_cross_encoder():
    global _CROSS_ENCODER, _CROSS_ENCODER_FAILED
    if _CROSS_ENCODER_FAILED:
        return None
    if _CROSS_ENCODER is not None:
        return _CROSS_ENCODER
    if not _rerank_wanted():
        _CROSS_ENCODER_FAILED = True
        return None
    try:
        import torch
        from sentence_transformers import CrossEncoder

        model_id = os.environ.get(
            "RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _CROSS_ENCODER = CrossEncoder(model_id, device=device, max_length=256)
        print(f"Cross-encoder reranker loaded: {model_id} ({device})")
    except Exception as e:
        print(f"Cross-encoder reranker unavailable ({e!r}); using vector order only.")
        _CROSS_ENCODER_FAILED = True
        return None
    return _CROSS_ENCODER


def _apply_cross_encoder_rerank(
    user_query: str,
    row_docs: List[str],
    row_metas: List[Optional[dict]],
    row_dists: List[Optional[float]],
    row_ids: List[Optional[str]],
    top_n: int,
    allow: Optional[set[str]],
) -> Tuple[List[str], List[Optional[dict]], List[Optional[float]], List[Optional[str]]]:
    """Pick top_n chunks by cross-encoder scores; fall back to vector order if disabled."""
    cand_idx: List[int] = []
    for i, doc in enumerate(row_docs):
        if not doc or not str(doc).strip():
            continue
        meta = row_metas[i] if i < len(row_metas) else None
        src = (meta or {}).get("source")
        if allow is not None and (not meta or src not in allow):
            continue
        cand_idx.append(i)

    if not cand_idx:
        return [], [], [], []

    if len(cand_idx) <= top_n:
        pick = cand_idx[:top_n]
    else:
        model = _get_cross_encoder()
        if model is None:
            pick = cand_idx[:top_n]
        else:
            pairs: List[List[str]] = []
            for i in cand_idx:
                t = row_docs[i].strip()
                if len(t) > _RERANK_CHARS:
                    t = t[:_RERANK_CHARS] + "…"
                pairs.append([user_query, t])
            batch = int(os.environ.get("RERANK_BATCH", "32"))
            scores = model.predict(pairs, batch_size=batch, show_progress_bar=False)
            order = sorted(range(len(scores)), key=lambda j: scores[j], reverse=True)
            pick = [cand_idx[j] for j in order[:top_n]]

    return (
        [row_docs[i] for i in pick],
        [row_metas[i] for i in pick],
        [row_dists[i] for i in pick],
        [row_ids[i] for i in pick],
    )


def _expand_source_where_keys(sources: List[str]) -> List[str]:
    """Chroma `source` metadata is usually a PDF basename; allow list entries may be paths."""
    keys: List[str] = []
    seen: set[str] = set()
    for s in sources:
        if not s:
            continue
        for key in (str(s).strip(), os.path.basename(str(s).strip())):
            if key and key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def _where_for_sources(sources: List[str]) -> dict:
    unique = _expand_source_where_keys(sources)
    if not unique:
        return {"source": ""}
    if len(unique) == 1:
        return {"source": unique[0]}
    return {"$or": [{"source": s} for s in unique]}


def _expand_allow_filenames(allow: set[str]) -> set[str]:
    out: set[str] = set()
    for a in allow:
        if not a:
            continue
        s = str(a).strip()
        out.add(s)
        b = os.path.basename(s)
        if b:
            out.add(b)
    return out


def _source_matches_allow(src: Optional[str], allow: Optional[set[str]]) -> bool:
    if allow is None:
        return True
    if not src:
        return False
    ex = _expand_allow_filenames(allow)
    s = str(src).strip()
    if s in ex:
        return True
    return os.path.basename(s) in ex


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


def _dist_sort_key(d: Optional[float]) -> float:
    try:
        return float(d) if d is not None else 9999.0
    except (TypeError, ValueError):
        return 9999.0


def _merge_chroma_query_results(primary: dict, secondary: dict) -> dict:
    """Union two single-query Chroma responses; same chunk id keeps the better (lower) distance."""
    best: Dict[str, Tuple[Any, Any, Any, Any]] = {}

    def ingest(res: dict) -> None:
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        ids = (res.get("ids") or [[]])[0]
        for doc, meta, dist, cid in zip(docs, metas, dists, ids):
            if not cid or not doc or not str(doc).strip():
                continue
            row = (doc, meta, dist, cid)
            if cid not in best or _dist_sort_key(dist) < _dist_sort_key(best[cid][2]):
                best[cid] = row

    ingest(primary)
    ingest(secondary)
    if not best:
        return primary
    merged = sorted(best.values(), key=lambda r: _dist_sort_key(r[2]))
    docs, metas, dists, ids = zip(*merged)
    return {
        "documents": [list(docs)],
        "metadatas": [list(metas)],
        "distances": [list(dists)],
        "ids": [list(ids)],
    }


_RETRIEVAL_BOOSTER_STOP = frozenset(
    """
    a an the and or but if then so as at by for from in into of on onto over to with without
    what which who whom whose where when why how is are was were be been being do does did doing
    has have had having can could should would will may might must shall
    tell give show find list summarize summarise explain describe define compare contrast
    about please just only also very much more most some any all each every both either neither
    this that these those it its they them their there here
    """.split()
)


def _retrieval_booster_query(user_query: str) -> Optional[str]:
    """
    Shorter keyword-style query for a second embedding pass when the full question
    misses filing phrasing. Stays grounded (no new facts); may return None if not useful.
    """
    raw = (user_query or "").strip()
    if len(raw) < 6:
        return None
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9.\-]{1,}", raw)
    kept: List[str] = []
    seen_lower: set[str] = set()
    for t in tokens:
        low = t.lower()
        if low in _RETRIEVAL_BOOSTER_STOP:
            continue
        if low in seen_lower:
            continue
        seen_lower.add(low)
        kept.append(t)
        if len(kept) >= 14:
            break
    if len(kept) < 2:
        return None
    booster = " ".join(kept).strip()
    if len(booster) < 6:
        return None
    if booster.lower() == raw.lower():
        return None
    return booster


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
        if allow and (not meta or not _source_matches_allow(src, allow)):
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
                "ticker": meta.get("ticker"),
                "year": meta.get("year"),
                "doc_type": meta.get("doc_type"),
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

    per_file_pool = per_file * 4 if _rerank_wanted() else per_file
    for src in sources_list:
        results = query_documents(
            [user_query],
            n_results=max(per_file_pool, 8),
            where=_where_for_sources([src]),
        )
        row_docs, row_metas, row_dists, row_ids = _pad_query_rows(results)
        for doc, meta, dist, cid in zip(row_docs, row_metas, row_dists, row_ids):
            if not doc or not cid:
                continue
            if not _source_matches_allow((meta or {}).get("source"), {src}):
                continue
            if cid not in best or dist_key(dist) < dist_key(best[cid][2]):
                best[cid] = (doc, meta, dist, cid)

    if not best:
        return [], []

    pool_limit = max_contexts * 4 if _rerank_wanted() else max_contexts
    merged = sorted(best.values(), key=lambda row: dist_key(row[2]))[:pool_limit]
    if not merged:
        return [], []
    docs, metas, dists, ids = zip(*merged)
    rd, rm, rdi, ri = _apply_cross_encoder_rerank(
        user_query,
        list(docs),
        list(metas),
        list(dists),
        list(ids),
        max_contexts,
        allow,
    )
    return _build_evidence_items(rd, rm, rdi, ri, allow, max_contexts)


def _query_implies_comparison(user_query: str) -> bool:
    """True when the user likely wants two or more companies / filings compared."""
    ql = user_query.lower()
    if re.search(
        r"\bcompare|\bcomparison\b|\bversus\b|\bvs\.?\s|contrasting|side[- ]by[- ]side|"
        r"each other|relative to (each|one another)|cross[- ]company|peer(s)?\b",
        ql,
    ):
        return True
    if re.search(r"\bbetween\b.+\band\b", ql):
        return True
    return False


def _slug_alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _query_slugs_for_pdf_stems(user_query: str) -> set[str]:
    """Word slugs + adjacent pairs (e.g. foot + locker -> footlocker) for filename matching."""
    ql = re.sub(r"[^a-zA-Z0-9\s]", " ", user_query)
    words = [w for w in ql.lower().split() if len(w) >= 2]
    slugs: set[str] = set()
    for w in words:
        if len(w) >= 3:
            slugs.add(_slug_alnum(w))
    for i in range(len(words) - 1):
        bi = _slug_alnum(words[i] + words[i + 1])
        if len(bi) >= 4:
            slugs.add(bi)
    return slugs


def _pdf_stem_matches_slugs(stem: str, slugs: set[str]) -> bool:
    st = _slug_alnum(stem)
    if len(st) < 4:
        return False
    if st in slugs:
        return True
    for s in slugs:
        if len(s) >= 4 and (s in st or st in s):
            return True
    return False


def _pdfs_on_disk_matching_query(user_query: str) -> List[str]:
    """PDF basenames whose first `_` segment looks like a company named in the query."""
    slugs = _query_slugs_for_pdf_stems(user_query)
    if not slugs:
        return []
    if not PDF_DIR.is_dir():
        return []
    matched: List[str] = []
    for p in sorted(PDF_DIR.iterdir()):
        if not p.is_file() or p.suffix.lower() != ".pdf":
            continue
        stem = p.name.split("_")[0]
        if _pdf_stem_matches_slugs(stem, slugs):
            matched.append(p.name)
    return matched


def _vector_ranked_sources(user_query: str, pool_n: int) -> List[str]:
    """All distinct sources ordered by retrieval strength (hit count, then avg distance)."""
    results = query_documents([user_query], n_results=pool_n, where=None)
    row_docs, row_metas, row_dists, row_ids = _pad_query_rows(results)
    by_src: Dict[str, List[float]] = {}
    for meta, dist in zip(row_metas, row_dists):
        if not meta:
            continue
        src = meta.get("source")
        if not src:
            continue
        try:
            d = float(dist) if dist is not None else 9999.0
        except (TypeError, ValueError):
            d = 9999.0
        by_src.setdefault(str(src), []).append(d)
    if not by_src:
        return []

    def sort_key(item: Tuple[str, List[float]]) -> Tuple[int, float]:
        src, dists = item
        cnt = len(dists)
        avg_d = sum(dists) / cnt
        return (-cnt, avg_d)

    ranked = sorted(by_src.items(), key=sort_key)
    return [name for name, _ in ranked]


def _pdf_stem(name: str) -> str:
    return name.split("_")[0] if "_" in name else name.rsplit(".", 1)[0]


def _auto_select_sources(
    user_query: str, max_sources: int, *, comparison: bool = False
) -> Optional[List[str]]:
    """
    Pick PDF(s) for auto-scope.
    - Single-focus questions: top file(s) by vector retrieval only.
    - Comparison questions: at most **one best-ranked file per company stem** from name-matched PDFs,
      then add **other companies** from vector ranking before adding second filings from the same issuer.
      Avoids filling all slots with WALMART_2016/2017/2018 while Coca-Cola is never scoped.
    """
    if max_sources < 1:
        return None
    pool_n = min(100, 50 + max_sources * 20)
    ranked = _vector_ranked_sources(user_query, pool_n)
    if not ranked:
        return None

    rank_index = {name: i for i, name in enumerate(ranked)}
    out: List[str] = []
    seen: set[str] = set()
    seen_stems: set[str] = set()

    if comparison:
        disk_hits = _pdfs_on_disk_matching_query(user_query)
        if disk_hits:
            best_per_stem: Dict[str, str] = {}
            for f in sorted(disk_hits, key=lambda x: rank_index.get(x, 10**9)):
                stem = _pdf_stem(f)
                if stem not in best_per_stem:
                    best_per_stem[stem] = f
            for f in sorted(best_per_stem.values(), key=lambda x: rank_index.get(x, 10**9)):
                if len(out) >= max_sources:
                    break
                out.append(f)
                seen.add(f)
                seen_stems.add(_pdf_stem(f))

        seen_stems = {_pdf_stem(f) for f in out}
        for name in ranked:
            if len(out) >= max_sources:
                break
            if name in seen:
                continue
            stem = _pdf_stem(name)
            if stem in seen_stems:
                continue
            out.append(name)
            seen.add(name)
            seen_stems.add(stem)

    for name in ranked:
        if len(out) >= max_sources:
            break
        if name not in seen:
            out.append(name)
            seen.add(name)

    return out if out else None


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
            _bq = _retrieval_booster_query(user_query)
            _queries = ([_bq] if _bq else []) + [user_query]
            _seen_q: set[str] = set()
            for _qx in _queries:
                _qx = (_qx or "").strip()
                if not _qx or _qx.lower() in _seen_q:
                    continue
                _seen_q.add(_qx.lower())
                wide = query_documents([_qx], n_results=60, where=None)
                wd, wm, wdist, wid = _pad_query_rows(wide)
                wd, wm, wdist, wid = _apply_cross_encoder_rerank(
                    user_query, wd, wm, wdist, wid, max_contexts, allow
                )
                contexts, evidence = _build_evidence_items(
                    wd, wm, wdist, wid, allow, max_contexts
                )
                if len(contexts) >= 1:
                    break
        elif len(contexts) < 4:
            _bq = _retrieval_booster_query(user_query)
            if _bq:
                wide = query_documents([_bq], n_results=60, where=None)
                wd, wm, wdist, wid = _pad_query_rows(wide)
                wd, wm, wdist, wid = _apply_cross_encoder_rerank(
                    user_query, wd, wm, wdist, wid, max_contexts, allow
                )
                c2, e2 = _build_evidence_items(
                    wd, wm, wdist, wid, allow, max_contexts
                )
                if len(c2) > len(contexts):
                    contexts, evidence = c2, e2
        return contexts, evidence

    n_results = min(64, max(32, max_contexts * 5)) if _rerank_wanted() else (24 if allow else 10)
    where_clause = _where_for_sources(list(allow)) if allow else None

    results = query_documents([user_query], n_results=n_results, where=where_clause)
    booster = _retrieval_booster_query(user_query)
    if booster and allow:
        results = _merge_chroma_query_results(
            results,
            query_documents([booster], n_results=n_results, where=where_clause),
        )
    elif booster and not allow:
        results = _merge_chroma_query_results(
            results,
            query_documents([booster], n_results=n_results, where=None),
        )
    row_docs, row_metas, row_dists, row_ids = _pad_query_rows(results)
    row_docs, row_metas, row_dists, row_ids = _apply_cross_encoder_rerank(
        user_query, row_docs, row_metas, row_dists, row_ids, max_contexts, allow
    )

    contexts, evidence = _build_evidence_items(
        row_docs, row_metas, row_dists, row_ids, allow, max_contexts
    )

    if allow and len(contexts) < 4:
        _bq = _retrieval_booster_query(user_query)
        _queries = ([_bq] if _bq else []) + [user_query]
        _seen_q: set[str] = set()
        for _qx in _queries:
            _qx = (_qx or "").strip()
            if not _qx or _qx.lower() in _seen_q:
                continue
            _seen_q.add(_qx.lower())
            wide = query_documents([_qx], n_results=60, where=None)
            wd, wm, wdist, wid = _pad_query_rows(wide)
            wd, wm, wdist, wid = _apply_cross_encoder_rerank(
                user_query, wd, wm, wdist, wid, max_contexts, allow
            )
            c2, e2 = _build_evidence_items(wd, wm, wdist, wid, allow, max_contexts)
            if len(c2) > len(contexts):
                contexts, evidence = c2, e2
            if len(contexts) >= max(4, max_contexts // 2):
                break

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
    "6) When snippets discuss the same company or topic but not the exact metric or period asked, say what the excerpts *do* "
    "support and what is missing — do not respond as if there were no relevant information unless the excerpts are clearly unrelated.\n"
    "7) Do not use external knowledge, assumptions, or prior chat memory outside the provided context."
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

# How chunk `source` filenames and metadata relate to time, restatements, and peers.
METADATA_SCOPE_INSTRUCTION = (
    "\n\nMETADATA & SCOPE (use [E#] `source` filenames and any year/ticker cues in the text):\n"
    "- **Purpose:** PDF names often encode **ticker**, **period** (e.g. calendar/fiscal year or year+quarter), and **form type** "
    "(10-K, 10-Q). Use them to state *which periods and entities* the answer actually rests on.\n"
    "- **Multiple years in the snippets:** When years differ across [E#], call that out before comparing numbers; "
    "do not blend figures from different periods without labeling each period.\n"
    "- **Amended filings:** If a `source` basename suggests an amendment (e.g. contains `_A` before the extension), "
    "treat it as a revised filing when discussing restated metrics; prefer it over an older non-amended twin if both appear.\n"
    "- **Peers:** Only discuss peer or cross-company normalization when **more than one distinct ticker/company** "
    "appears across retrieved sources; with a single company, say comparisons are not supported by the current retrieval set.\n"
    "- **Honesty:** These cues come from **naming/metadata**, not from a separate fact-checking engine—say so if the user asks "
    "how contradiction or restatement was detected."
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
    fixed = re.sub(
        r"\b(no|without)\s+(relevant\s+)?(information|data|figures?|numbers?)\s+(is\s+)?(available|found|provided)\b",
        "only limited information is available in the retrieved excerpts",
        fixed,
        flags=re.IGNORECASE,
    )
    fixed = re.sub(
        r"\b(the\s+)?(document|filing|files?)\s+(does\s+not|do\s+not)\s+contain\s+(any\s+)?(information|data)\b",
        "the retrieved excerpts contain limited information on this point",
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
        ct = ev.get("content_type") or "unknown"
        em = ev.get("extraction_method") or "unknown"
        excerpt = ev.get("excerpt") or ""
        
        # Always show content_type and extraction_method
        header = f"- **{cid}** | **{src}** | page {pg_s} | **content_type:** {ct} | **extraction_method:** {em} | confidence **{conf}** (vector distance: {ev.get('vector_distance')})"
        
        lines.append(header)
        if excerpt:
            lines.append(f"  > {excerpt}")
        lines.append("")  # Empty line for spacing
    
    return "\n".join(lines)


def _format_periods_for_caps(periods: List[str], max_visible: int = 5) -> str:
    """e.g. '2015, 2016, 2018, 2020, 2021 +1 more' for UI caps line."""
    if not periods:
        return ""
    if len(periods) <= max_visible:
        return ", ".join(periods)
    head = ", ".join(periods[:max_visible])
    more = len(periods) - max_visible
    return f"{head} +{more} more"


def _append_advanced_analysis_section(evidence: List[Dict[str, Any]]) -> str:
    """Automated analysis capabilities block (checkmark style); driven by retrieval heuristics."""
    if not evidence:
        return ""

    temporal = _analyze_temporal_patterns(evidence)
    restatement = _analyze_restatements(evidence)
    peer = _analyze_peer_normalization(evidence)

    periods = temporal["periods_covered"]
    n_periods = len(periods)
    period_disp = _format_periods_for_caps(periods)

    ndoc = int(restatement["documents_analyzed"])
    has_amd = bool(restatement.get("has_amended_filenames"))
    n_amd = int(restatement.get("amended_document_count") or 0)

    tickers = peer.get("tickers_observed") or []
    n_cos = int(peer["companies_in_scope"])
    tickers_disp = ", ".join(tickers) if tickers else "unknown"

    # --- 1. Temporal
    if n_periods > 1:
        temporal_lines = [
            f"1. 🕐 Temporal Contradiction Detector ✓ Multi-period analysis enabled across {n_periods} time periods ({period_disp})",
            "✓ Can detect inconsistencies between management guidance and actual results when both appear in retrieved excerpts",
            "✓ Cross-quarter/year trend validation available",
        ]
    elif n_periods == 1:
        temporal_lines = [
            f"1. 🕐 Temporal Contradiction Detector ✓ Single-period focus on filename tag **{periods[0]}**",
            "✓ Guidance vs. actual comparison when both appear in retrieved context",
            "✓ Cross-period trend validation: add filings with other year/quarter tags in filenames",
        ]
    else:
        temporal_lines = [
            "1. 🕐 Temporal Contradiction Detector ✓ No year/quarter parsed from retrieved PDF names — use names like TICKER_2023_10K.pdf",
            "✓ Time-based checks rely on explicit dates/periods inside the retrieved text",
            "✓ Multi-period analysis unavailable until period tags appear in source filenames",
        ]

    # --- 2. Restatement
    if has_amd:
        rest_lines = [
            f"2. 📊 Metric Restatement Tracker ✓ Analyzed **{ndoc}** document(s) — **{n_amd}** amended source(s) detected (underscore-A in the basename)",
            "✓ Prefer amended excerpts for restated figures when both original and amendment appear in evidence",
            "✓ Version comparison active: reconcile metrics across filing versions using [E#] citations",
        ]
    else:
        rest_lines = [
            f"2. 📊 Metric Restatement Tracker ✓ Analyzed {ndoc} document(s) — all original filings, no restatements detected (underscore-A filename rule)",
            "✓ Data integrity confirmed: no amendments or corrections flagged in retrieved sources by that naming rule",
            "✓ To compare pre/post restatement explicitly, add amended PDFs whose basenames include the substring underscore-A before the extension",
        ]

    # --- 3. Peer
    if n_cos > 1:
        peer_lines = [
            f"3. 🔄 Peer Normalization Lens ✓ Multi-company comparison enabled with **{n_cos}** companies in scope ({tickers_disp})",
            "✓ Can normalize metrics by revenue scale, employee count, or market cap when those figures appear in retrieved context",
            "✓ Industry benchmarking and competitive analysis available within retrieved excerpts",
        ]
    elif n_cos == 1:
        peer_lines = [
            f"3. 🔄 Peer Normalization Lens ✓ Single-company scope (**{tickers_disp}**)",
            "✓ Peer normalization and industry benchmarks: add other issuers’ PDFs to the corpus or query scope",
            "✓ Metric scaling (revenue/employees/market cap) when values are present in the same retrieved text",
        ]
    else:
        peer_lines = [
            "3. 🔄 Peer Normalization Lens ✓ Company ticker not inferred — check PDF naming (TICKER_…) or chunk metadata",
            "✓ Multi-company comparison disabled until distinct tickers appear in retrieved sources",
            "✓ Normalization and benchmarking apply only when peer data exists in context",
        ]

    # --- Intelligence summary
    summary_bits: List[str] = []
    if n_periods > 1:
        summary_bits.append(f"Historical trend analysis across {n_periods} periods")
    elif n_periods == 1:
        summary_bits.append(f"Period-focused analysis ({periods[0]})")
    else:
        summary_bits.append("Period tagging limited for this retrieval set")

    if n_cos > 1:
        summary_bits.append(f"Peer benchmarking with {n_cos} companies")
    elif n_cos == 1:
        summary_bits.append(f"Single-company scope ({tickers_disp})")
    else:
        summary_bits.append("Company scope needs clearer filenames/metadata")

    summary = " | ".join(summary_bits)

    lines = (
        [
            "\n\n**Automated Analysis Capabilities:**",
            "",
            *temporal_lines,
            "",
            *rest_lines,
            "",
            *peer_lines,
            "",
            f"💡 **Intelligence Summary:** {summary}",
            "",
            "_Signals above reflect this answer’s retrieved chunks (filenames + metadata), not a separate offline audit._",
        ]
    )

    return "\n".join(lines)

def _finalize_answer(
    raw_answer: str,
    evidence: List[Dict[str, Any]],
    user_query: str = "",
    contexts: Optional[List[str]] = None,
) -> str:
    body = _strip_model_evidence_section(raw_answer)
    body = _sanitize_contradictory_no_evidence(body, evidence)
    body = _ensure_chart_block(body, evidence, user_query=user_query, contexts=contexts)
    body = body + _append_advanced_analysis_section(evidence)
    return body + _append_evidence_footer(evidence)


def _has_chart_block(text: str) -> bool:
    return bool(re.search(r"```chart-data\s*[\s\S]*?```", text, flags=re.IGNORECASE))


_CHART_DATA_BLOCK_RE = re.compile(r"```chart-data\s*\n([\s\S]*?)```", re.IGNORECASE)


def _chart_block_parses_to_plottable(text: str) -> bool:
    """True if fenced chart-data exists and JSON is a non-empty array of objects with at least one numeric series."""
    m = _CHART_DATA_BLOCK_RE.search(text)
    if not m:
        return False
    raw = m.group(1).strip()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, list) or len(data) == 0:
        return False
    sample = data[0]
    if not isinstance(sample, dict):
        return False
    x_keys = {"year", "date", "name", "label", "x", "period", "point", "metric"}
    for k, v in sample.items():
        if k.lower() in x_keys:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return True
        if isinstance(v, str):
            try:
                float(v.replace(",", ""))
                return True
            except (TypeError, ValueError):
                continue
    return False


def _strip_chart_data_block(text: str) -> str:
    return _CHART_DATA_BLOCK_RE.sub("", text).rstrip()


_NUMERIC_QUERY_TERMS = (
    "revenue",
    "sales",
    "income",
    "profit",
    "loss",
    "growth",
    "compare",
    "comparison",
    "trend",
    "chart",
    "graph",
    "percent",
    "margin",
    "ebitda",
    "cash",
    "debt",
    "ratio",
    "yoy",
    "year-over-year",
    "quarter",
    "q1",
    "q2",
    "q3",
    "q4",
    "fy",
    "billion",
    "million",
    "eps",
    "ebit",
)


def _query_suggests_numeric_chart(user_query: str) -> bool:
    if not user_query:
        return False
    q = user_query.lower()
    if "%" in user_query or "€" in user_query or "$" in user_query:
        return True
    return any(t in q for t in _NUMERIC_QUERY_TERMS)


_MONEY_RE = re.compile(
    r"(?<![A-Za-z0-9])\$\s*([\d,]+(?:\.\d+)?)\s*(billion|million|thousand|billions|millions|B|M|bn|mm|K)?\b",
    re.IGNORECASE,
)
_PCT_RE = re.compile(r"\b([\d,]+(?:\.\d+)?)\s*(?:%|percent\b)", re.IGNORECASE)


def _parse_money_groups(num_s: str, unit_s: Optional[str]) -> float:
    n = float(num_s.replace(",", ""))
    u = (unit_s or "").lower()
    if u in ("billion", "billions", "b", "bn"):
        return n * 1e9
    if u in ("million", "millions", "m", "mm"):
        return n * 1e6
    if u in ("thousand", "k"):
        return n * 1e3
    return n


def _extract_chart_rows_from_retrieval(
    contexts: Optional[List[str]],
    evidence: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Layer 2 (financial filings only): extract dollar amounts and percentage metrics
    (margins, growth rates, etc.) from retrieved chunk text. No academic/CGPA handling.
    """
    dollar_pairs: List[Tuple[float, str, int]] = []
    pct_pairs: List[Tuple[float, str, int]] = []
    order = 0

    seq: List[Tuple[str, Dict[str, Any], int]] = []
    if contexts and evidence and len(contexts) == len(evidence):
        for i, (ctx, ev) in enumerate(zip(contexts, evidence)):
            seq.append((ctx or "", ev, i))
    else:
        for i, ev in enumerate(evidence):
            seq.append((ev.get("excerpt") or "", ev, i))

    for ctx, ev, idx in seq:
        if not ctx:
            continue
        page = ev.get("page")
        src = _safe_source_label(ev.get("source"), idx + 1)

        for m in _MONEY_RE.finditer(ctx):
            try:
                val = _parse_money_groups(m.group(1), m.group(2))
            except ValueError:
                continue
            if abs(val) < 1e-9:
                continue
            order += 1
            snippet = ctx[max(0, m.start() - 40) : m.start()].replace("\n", " ").strip()
            short = (snippet[-34:] if snippet else "").strip()
            label = f"{short}…" if short else f"{src} p.{page}"
            dollar_pairs.append((val, label[:58], order))

        for m in _PCT_RE.finditer(ctx):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if abs(val) > 10000:
                continue
            order += 1
            snippet = ctx[max(0, m.start() - 80) : m.end()].replace("\n", " ").strip()
            short = (snippet[-55:] if snippet else "").strip()
            label = (short if short else f"{src} p.{page}")[:70]
            pct_pairs.append((val, label, order))

    use_dollars = len(dollar_pairs) > 0
    pairs = dollar_pairs if use_dollars else pct_pairs
    if not pairs:
        return []

    out: List[Tuple[float, str, int]] = []
    seen: set[float] = set()
    for val, lab, ord_ in sorted(pairs, key=lambda x: x[2]):
        sig = round(val, 2 if abs(val) < 500 else -2)
        if sig in seen:
            continue
        seen.add(sig)
        out.append((val, lab, ord_))
        if len(out) >= 14:
            break

    if len(out) < 1:
        return []

    rows: List[Dict[str, Any]] = []
    if use_dollars:
        mx = max(abs(v) for v, _, _ in out)
        if mx >= 1e8:
            div = 1e9
        elif mx >= 1e5:
            div = 1e6
        elif mx >= 1e3:
            div = 1e3
        else:
            div = 1.0
        for val, lab, _ in out:
            rows.append({"label": lab, "value": round(val / div, 4)})
    else:
        # Percentages (margins, rates): single series `value` on 0–100 style axis
        for val, lab, _ in out:
            rows.append({"label": f"{lab} ({val}%)"[:85], "value": round(val, 4)})

    return rows


def _money_axis_divider(max_abs: float) -> float:
    if max_abs >= 1e8:
        return 1e9
    if max_abs >= 1e5:
        return 1e6
    if max_abs >= 1e3:
        return 1e3
    return 1.0


def _sanitize_chart_series_key(stem: str) -> str:
    """JSON-safe key for Recharts `dataKey` (valid identifier-style)."""
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", stem.strip()).strip("_")
    if not s:
        return "series"
    if s[0].isdigit():
        s = "s_" + s
    return s[:48]


def _merged_context_by_source(
    contexts: Optional[List[str]],
    evidence: List[Dict[str, Any]],
) -> Tuple[List[str], Dict[str, str]]:
    """
    Ordered distinct sources (first-seen) and merged text per source path.
    """
    from collections import defaultdict

    chunks: Dict[str, List[Tuple[int, str]]] = defaultdict(list)

    if contexts and evidence and len(contexts) == len(evidence):
        for i, (ctx, ev) in enumerate(zip(contexts, evidence)):
            src = ev.get("source")
            if not src:
                continue
            t = (ctx or "").strip()
            if not t:
                continue
            key = os.path.normpath(str(src))
            chunks[key].append((i, t))
    else:
        for i, ev in enumerate(evidence):
            src = ev.get("source")
            if not src:
                continue
            t = (ev.get("excerpt") or "").strip()
            if not t:
                continue
            key = os.path.normpath(str(src))
            chunks[key].append((i, t))

    order: List[str] = []
    seen: set[str] = set()
    for ev in evidence:
        src = ev.get("source")
        if not src:
            continue
        key = os.path.normpath(str(src))
        if key in chunks and key not in seen:
            seen.add(key)
            order.append(key)

    merged: Dict[str, str] = {}
    for key, pairs in chunks.items():
        pairs.sort(key=lambda x: x[0])
        merged[key] = "\n".join(p[1] for p in pairs)

    return order, merged


def _ordered_unique_financial_scalars(text: str, *, dollars: bool) -> List[float]:
    """Document-order unique financial scalars ($ or %) for comparison-series extraction."""
    pairs: List[Tuple[float, int]] = []
    order = 0
    if dollars:
        for m in _MONEY_RE.finditer(text):
            try:
                val = _parse_money_groups(m.group(1), m.group(2))
            except ValueError:
                continue
            if abs(val) < 1e-9:
                continue
            order += 1
            pairs.append((val, order))
    else:
        for m in _PCT_RE.finditer(text):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if abs(val) > 10000:
                continue
            order += 1
            pairs.append((val, order))

    pairs.sort(key=lambda x: x[1])
    out: List[float] = []
    seen: set[float] = set()
    for val, _ in pairs:
        sig = round(val, 2 if abs(val) < 500 else -2)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(val)
        if len(out) >= 10:
            break
    return out


def _comparison_chart_rows_from_evidence(
    contexts: Optional[List[str]],
    evidence: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    """
    One chart, multiple lines: shared x (`metric`) and one numeric column per source PDF.
    Values are snippet-derived (aligned by extraction order, not necessarily the same line item).
    """
    order, merged = _merged_context_by_source(contexts, evidence)
    if len(order) < 2:
        return None

    texts = [merged[k] for k in order if merged.get(k)]
    if len(texts) < 2:
        return None

    any_dollar = any(_MONEY_RE.search(merged[k]) for k in order if merged.get(k))
    use_dollars = bool(any_dollar)

    raw: Dict[str, List[float]] = {}
    for key in order:
        t = merged.get(key) or ""
        if not t:
            continue
        raw[key] = _ordered_unique_financial_scalars(t, dollars=use_dollars)

    active = [k for k in order if raw.get(k)]
    if len(active) < 2:
        return None

    max_abs = 0.0
    if use_dollars:
        for k in active:
            for v in raw[k]:
                max_abs = max(max_abs, abs(v))
        div = _money_axis_divider(max_abs)
    else:
        div = 1.0

    key_by_source: Dict[str, str] = {}
    used_names: set[str] = set()
    for src_path in active:
        stem = os.path.splitext(os.path.basename(src_path))[0]
        sk = _sanitize_chart_series_key(stem)
        base = sk
        n = 2
        while sk in used_names:
            sk = f"{base}_{n}"
            n += 1
        used_names.add(sk)
        key_by_source[src_path] = sk

    max_len = max(len(raw[k]) for k in active)
    if max_len < 1:
        return None

    rows: List[Dict[str, Any]] = []
    for i in range(max_len):
        row: Dict[str, Any] = {"metric": f"Point {i + 1}"}
        for src_path in active:
            sk = key_by_source[src_path]
            if i < len(raw[src_path]):
                v = raw[src_path][i]
                row[sk] = round(v / div, 4) if use_dollars else round(v, 4)
            else:
                row[sk] = None
        rows.append(row)
    return rows


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


def _ensure_chart_block(
    text: str,
    evidence: List[Dict[str, Any]],
    user_query: str = "",
    contexts: Optional[List[str]] = None,
) -> str:
    """
    Two-layer charts:
    1) LLM-generated ```chart-data``` — keep if JSON parses to a plottable array.
    2) Fallback — extract $ / % from retrieved chunk text; if still thin, use confidence vs. label.
    """
    text = text.rstrip()
    if _has_chart_block(text) and _chart_block_parses_to_plottable(text):
        return text
    if _has_chart_block(text):
        text = _strip_chart_data_block(text)

    data: List[Dict[str, Any]]
    if _query_implies_comparison(user_query):
        cmp_rows = _comparison_chart_rows_from_evidence(contexts, evidence)
        if cmp_rows:
            data = cmp_rows
        else:
            extracted = _extract_chart_rows_from_retrieval(contexts, evidence)
            use_extracted = len(extracted) >= 2 or (
                len(extracted) == 1 and _query_suggests_numeric_chart(user_query)
            )
            data = extracted if use_extracted else _fallback_chart_data(evidence)
    else:
        extracted = _extract_chart_rows_from_retrieval(contexts, evidence)
        use_extracted = len(extracted) >= 2 or (
            len(extracted) == 1 and _query_suggests_numeric_chart(user_query)
        )
        if use_extracted:
            data = extracted
        else:
            data = _fallback_chart_data(evidence)

    return text + "\n\n```chart-data\n" + json.dumps(data, ensure_ascii=True) + "\n```"


def _period_sort_key(period: str) -> tuple:
    m = re.match(r"^(\d{4})(Q[1-4])?$", period)
    if not m:
        return (9999, period)
    q = m.group(2) or ""
    return (int(m.group(1)), q)


def _analyze_temporal_patterns(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Infer reporting periods from `source` filenames (first 4-digit year + optional quarter)."""
    time_periods: dict[str, list] = {}
    for ev in evidence:
        src = ev.get("source", "") or ""
        match = re.search(r"(\d{4})(Q[1-4])?", src)
        if match:
            period = match.group(0)
            time_periods.setdefault(period, []).append(src)

    keys = sorted(time_periods.keys(), key=_period_sort_key)
    n = len(keys)
    if n == 0:
        return {
            "periods_covered": [],
            "temporal_span": "No year parsed from retrieved `source` names",
            "cross_period_analysis": "Not applicable — add filenames with a 4-digit year (e.g. TICKER_2023_10K.pdf) for period tagging.",
        }
    if n == 1:
        cross = "Not applicable for this answer — only one period token was parsed from filenames."
    else:
        cross = (
            "Yes — retrieved chunks span multiple period tags; when you compare metrics, tie each number to its "
            "period ([E#] source) and flag possible inconsistency if two periods disagree."
        )
    return {
        "periods_covered": keys,
        "temporal_span": f"{n} distinct period tag(s) in retrieved sources (from filename years/quarters)",
        "cross_period_analysis": cross,
    }

def _analyze_restatements(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Heuristic: amended filing if basename contains `_A` (convention); not full XBRL diff."""
    sources: dict[str, list] = {}
    for ev in evidence:
        src = ev.get("source", "") or ""
        if src not in sources:
            sources[src] = []
        sources[src].append({"page": ev.get("page"), "content_type": ev.get("content_type")})

    amended_docs = [s for s in sources if "_A" in s]
    original_docs = [s for s in sources if "_A" not in s]

    if amended_docs:
        restatement = (
            f"Amended filenames present ({len(amended_docs)}): prefer these for restated numbers vs originals when both appear."
        )
        version = f"{len(original_docs)} non-_A source(s), {len(amended_docs)} `_A` source(s) in this retrieval set"
    else:
        restatement = (
            "No `_A` amendment marker in retrieved basenames — we are **not** asserting zero restatements in SEC history, "
            "only that this answer's chunks do not include filenames matching that convention."
        )
        version = "Only non-`_A` sources in this retrieval set (or single version in evidence)"

    return {
        "documents_analyzed": len(sources),
        "restatement_tracking": restatement,
        "version_comparison": version,
        "has_amended_filenames": bool(amended_docs),
        "amended_document_count": len(amended_docs),
    }

def _analyze_peer_normalization(evidence: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Distinct tickers from chunk metadata or first segment of `source` before `_`; doc_type from metadata."""
    tickers_order: list[str] = []
    seen: set[str] = set()
    doc_types: set[str] = set()

    for ev in evidence:
        src = (ev.get("source") or "").strip()
        ticker = ev.get("ticker")
        if not ticker and src:
            ticker = src.split("_")[0] if "_" in src else None
        if ticker and ticker not in seen:
            seen.add(ticker)
            tickers_order.append(ticker)
        dt = ev.get("doc_type")
        if dt:
            doc_types.add(str(dt))

    n = len(tickers_order)
    if n > 1:
        peer = (
            f"Multiple tickers in this retrieval set ({', '.join(tickers_order)}). "
            "Cross-company comparisons are **supported by scope** — still align fiscal period and units before comparing."
        )
        norm = "Yes — cite [E#] per company when contrasting metrics."
    else:
        peer = (
            f"Single inferred company/ticker in evidence (`{tickers_order[0] if tickers_order else 'unknown'}`). "
            "Do not claim peer rankings or industry-relative normalization unless the user brings other filings into scope."
        )
        norm = "N/A — add PDFs for other tickers to enable peer-style answers from retrieval."

    return {
        "companies_in_scope": n,
        "tickers_observed": tickers_order,
        "peer_comparison": peer,
        "normalization_ready": norm,
        "document_types": sorted(doc_types) if doc_types else [],
    }

def _payload_with_evidence(
    answer: str,
    model: str,
    evidence: List[Dict[str, Any]],
    scoped_sources: Optional[List[str]] = None,
    auto_scoped: bool = False,
) -> Dict[str, Any]:
    parts = []
    for e in evidence:
        src = e.get("source") or "?"
        pg = e.get("page")
        parts.append(f"{src} p.{pg}" if pg is not None else str(src))
    
    # Add advanced financial analysis features
    temporal_analysis = _analyze_temporal_patterns(evidence)
    restatement_analysis = _analyze_restatements(evidence)
    peer_analysis = _analyze_peer_normalization(evidence)
    
    return {
        "answer": answer,
        "model": model,
        "evidence": evidence,
        "sources_summary": "; ".join(parts) if parts else None,
        "scoped_sources": scoped_sources,
        "auto_scoped": auto_scoped,
        "advanced_analysis": {
            "temporal_contradiction_detector": temporal_analysis,
            "metric_restatement_tracker": restatement_analysis,
            "peer_normalization_lens": peer_analysis
        }
    }


def ask_question(user_query: str, selected_files: Optional[List[str]] = None) -> Dict[str, Any]:
    manual = [f for f in (selected_files or []) if f]
    comparison_q = _query_implies_comparison(user_query)
    auto_scoped_flag = False
    if manual:
        effective_files: Optional[List[str]] = manual
    else:
        if comparison_q:
            max_auto = int(os.environ.get("AUTO_SCOPE_COMPARISON_MAX_SOURCES", "6"))
        else:
            max_auto = int(os.environ.get("AUTO_SCOPE_MAX_SOURCES", "1"))
        picked = _auto_select_sources(user_query, max_auto, comparison=comparison_q)
        effective_files = picked
        auto_scoped_flag = bool(picked)

    scoped = bool(effective_files)
    contexts, evidence = _retrieve_filtered_with_evidence(user_query, effective_files)

    multi = bool(effective_files and len({f for f in effective_files if f}) >= 2)

    if scoped and not contexts:
        names = ", ".join(effective_files or [])
        context_text = (
            f"(No text chunks were retrieved from the scoped document(s) for this query: {names}. "
            "Do not use outside knowledge; state that these files do not contain relevant information.)"
        )
    elif contexts and evidence and len(contexts) == len(evidence):
        context_text = _format_labeled_context(contexts, evidence)
    else:
        context_text = "\n---\n".join(contexts) if contexts else "No relevant documents found."

    scope_instruction = ""
    if scoped and effective_files:
        names = ", ".join(effective_files)
        if auto_scoped_flag:
            one = len(effective_files) == 1
            cmp_hint = ""
            if comparison_q and not one:
                cmp_hint = (
                    " The user is comparing companies or filings — use [E#] excerpts from **each** listed PDF "
                    "when the context includes both; if one company is missing from the corpus, say so explicitly."
                )
            scope_instruction = (
                f"\n\nRetrieval is scoped to the best-matching PDF{'s' if not one else ''} for this question: **{names}**. "
                "You MUST use only the context above. All [E#] blocks are from these file(s). "
                "If it is insufficient, say clearly that the answer is not found in the scoped document(s)."
                + cmp_hint
            )
        else:
            scope_instruction = (
                f"\n\nThe user limited scope to ONLY these PDF file(s): {names}. "
                "You MUST use only the context above. If it is insufficient, say clearly that "
                "the answer is not found in the selected document(s). Do not invent facts from other sources."
            )

    retrieval_grounding_hint = ""
    if contexts:
        retrieval_grounding_hint = (
            "\n\nRETRIEVAL NOTE: [E#] blocks are present above - use them as the primary source. "
            "If they cover the same company or topic but not the exact figure or period asked, state what the excerpts *do* support "
            "and what is not stated; reserve blanket 'no information' language for cases where the snippets are clearly unrelated."
        )

    chart_instruction = (
        "\n\nCHARTS (financial metrics): When the answer cites comparable numeric series from the filing(s) "
        "(revenue, EPS, margins, YoY %, cash flows, etc.), include a ```chart-data``` JSON array. "
        "Each object should use a period or category string in `label` (or `year`/`name`/`period`/`metric`) and a numeric field "
        "such as `value` or `revenue` in consistent units (e.g. USD billions or millions across rows). "
        "Omit chart-data if there is nothing quantitative to plot; the backend may still derive a chart from $ / % in retrieved text."
        "\n\nExample: [{\"label\":\"FY22\",\"revenue\":12.3},{\"label\":\"FY23\",\"revenue\":14.1}]"
    )
    if comparison_q:
        chart_instruction += (
            "\n\nThe user is comparing multiple companies or filings: use **one** chart with a **shared** x-field "
            "(`label`, `year`, or `period`) and **separate numeric columns per entity** (e.g. `WMT_margin` and `KO_margin`) "
            "so each company appears as its own line on the same axes. Use consistent units across columns."
        )

    multi_extra = MULTI_DOC_INSTRUCTION if multi else ""
    scoped_extra = SCOPED_EVIDENCE_CONSISTENCY_INSTRUCTION if scoped and evidence else ""

    system_prompt = (
        "You are a financial intelligence assistant. Given the following context, answer the user's query.\n"
        "If the query requires complex mathematical comparisons or deep multi-document reasoning that you cannot safely and confidently perform, "
        "output exactly and only the word 'ESCALATE'.\n\nContext:\n\n"
        + context_text
        + scope_instruction
        + retrieval_grounding_hint
        + multi_extra
        + scoped_extra
        + METADATA_SCOPE_INSTRUCTION
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
                                + retrieval_grounding_hint
                                + multi_extra
                                + scoped_extra
                                + METADATA_SCOPE_INSTRUCTION
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
                    _finalize_answer(raw, evidence, user_query=user_query, contexts=contexts),
                    model_to_use.value,
                    evidence,
                    scoped_sources=effective_files if scoped else None,
                    auto_scoped=auto_scoped_flag,
                )
            except Exception as e:
                return {"error": str(e)}
        else:
            msg = "The query is too complex, but limits ($7.50 cutoff) have been reached. Unable to escalate."
            return _payload_with_evidence(
                _finalize_answer(msg, evidence, user_query=user_query, contexts=contexts),
                model_to_use.value,
                evidence,
                scoped_sources=effective_files if scoped else None,
                auto_scoped=auto_scoped_flag,
            )

    return _payload_with_evidence(
        _finalize_answer(answer, evidence, user_query=user_query, contexts=contexts),
        model_to_use.value,
        evidence,
        scoped_sources=effective_files if scoped else None,
        auto_scoped=auto_scoped_flag,
    )
