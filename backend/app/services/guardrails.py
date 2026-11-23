import re
from collections import Counter

from langchain_core.documents import Document

from app.core.config import settings


class GuardrailError(ValueError):
    """Conteúdo recusado pela política de ingestão."""


# ---------- PII ----------

_CPF = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# Telefone BR só com DDD entre parenteses ou prefixo +55, para não pegar numeros soltos
_PHONE = re.compile(r"(?<!\d)(?:\+55\s?\(?\d{2}\)?|\(\d{2}\))\s?9?\d{4}-?\d{4}(?!\d)")


def is_valid_cpf(raw: str) -> bool:
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for size in (9, 10):
        total = sum(int(d) * w for d, w in zip(digits[:size], range(size + 1, 1, -1)))
        check = (total * 10) % 11 % 10
        if check != int(digits[size]):
            return False
    return True


def _email_allowed(email: str) -> bool:
    email = email.lower()
    for item in settings.pii_allowlist:
        if email == item or (item.startswith("@") and email.endswith(item)):
            return True
    return False


def _mask(text: str, counts: Counter) -> str:
    types = settings.pii_type_list

    if "cpf" in types:

        def cpf(m: re.Match) -> str:
            if not is_valid_cpf(m.group()):
                return m.group()
            counts["cpf"] += 1
            return "[CPF]"

        text = _CPF.sub(cpf, text)

    if "email" in types:

        def email(m: re.Match) -> str:
            if _email_allowed(m.group()):
                return m.group()
            counts["email"] += 1
            return "[EMAIL]"

        text = _EMAIL.sub(email, text)

    if "phone" in types:

        def phone(m: re.Match) -> str:
            counts["phone"] += 1
            return "[TELEFONE]"

        text = _PHONE.sub(phone, text)

    return text


def mask_pii(text: str) -> tuple[str, dict[str, int]]:
    counts: Counter = Counter()
    return _mask(text, counts), dict(counts)


def redact(text: str) -> str:
    """Mascara PII em textos que vao para log, historico e analytics."""
    if settings.pii_mode == "off":
        return text
    return mask_pii(text)[0]


# ---------- Prompt injection ----------

_INJECTION_PATTERNS: dict[str, re.Pattern] = {
    name: re.compile(pattern, re.IGNORECASE)
    for name, pattern in {
        "ignorar_instrucoes_pt": r"\b(ignore|ignorar|ignorem|desconsidere|esque[cç]a)\b[^.\n]{0,40}\b(instru[cç][õo]es|regras|ordens|prompt)\b",
        "ignore_instructions_en": r"\b(ignore|disregard|forget)\b[^.\n]{0,40}\b(instructions|rules|prompts?)\b",
        "novo_papel": r"\b(from now on|a partir de agora)\b[^.\n]{0,20}\b(you|voc[eê]|vc)\b",
        "revelar_prompt": r"\b(reveal|show|print|repeat|mostre|revele|exiba|repita)\b[^.\n]{0,30}\b(system prompt|prompt do sistema|instru[cç][õo]es do sistema)\b",
        "tags_de_papel": r"<\s*/?\s*(system|assistant)\s*>|\[/?INST\]",
        "jailbreak": r"\bjailbreak\b|\bDAN mode\b|\bmodo DAN\b",
    }.items()
}


def detect_injection(text: str) -> list[str]:
    return [name for name, rx in _INJECTION_PATTERNS.items() if rx.search(text)]


# ---------- Aplicação na ingestão ----------


def mask_documents(docs: list[Document]) -> tuple[list[Document], dict[str, int]]:
    """Aplica a política de PII antes do chunking."""
    if settings.pii_mode == "off":
        return docs, {}

    total: Counter = Counter()
    out = []
    for doc in docs:
        found: Counter = Counter()
        masked = _mask(doc.page_content, found)
        total.update(found)
        out.append(Document(page_content=masked, metadata=doc.metadata))

    if total and settings.pii_mode == "block":
        kinds = ", ".join(f"{k}: {v}" for k, v in total.items())
        raise GuardrailError(f"Documento recusado: contém dados pessoais ({kinds}).")
    return out, dict(total)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def _strip_injection(text: str) -> tuple[str, int]:
    """Remove só as frases suspeitas e mantém o resto do trecho. Retorna (texto, frases removidas)."""
    kept: list[str] = []
    removed = 0
    for sentence in _SENTENCE_SPLIT.split(text):
        if sentence.strip() and detect_injection(sentence):
            removed += 1
        elif sentence.strip():
            kept.append(sentence.strip())
    return "\n".join(kept), removed


def filter_chunks(chunks: list[Document]) -> tuple[list[Document], list[dict]]:
    """
    Aplica a política de prompt injection depois do chunking.
    drop: remove as frases suspeitas (o resto do trecho continua indexado)
    flag: indexa tudo e apenas reporta
    block: recusa o documento
    """
    mode = settings.injection_mode
    if mode == "off":
        return chunks, []

    kept: list[Document] = []
    flagged: list[dict] = []
    for i, chunk in enumerate(chunks):
        hits = detect_injection(chunk.page_content)
        if not hits:
            kept.append(chunk)
            continue

        entry = {"chunk": i, "patterns": hits, "page": chunk.metadata.get("page")}
        if mode == "drop":
            cleaned, removed = _strip_injection(chunk.page_content)
            entry["sentences_removed"] = removed
            if cleaned.strip():
                kept.append(Document(page_content=cleaned, metadata=chunk.metadata))
        else:
            kept.append(chunk)
        flagged.append(entry)

    if flagged and mode == "block":
        raise GuardrailError(f"Documento recusado: {len(flagged)} trecho(s) com padrão de prompt injection.")
    if not kept:
        raise GuardrailError("Todo o conteúdo foi removido pelo filtro de prompt injection.")
    return kept, flagged
