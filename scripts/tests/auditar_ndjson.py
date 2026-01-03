"""
Auditoria simples 1:1 entre logs .txt e NDJSON gerado.

Fluxo:
    1) Identifica pares pelo nome base (output_json/*.json -> logs/*.txt).
    2) Compara linha a linha, via hash curto (lh) no NDJSON.
    3) Gera relatorio Markdown com resumo e amostras de erro.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from itertools import zip_longest
from pathlib import Path


@dataclass(slots=True)
class FileAuditResult:
    """Resumo da auditoria para um par txt/ndjson.

    Attributes:
        txt_path: Caminho do arquivo .txt de origem.
        json_path: Caminho do arquivo .json convertido.
        txt_lines: Total de linhas validas do .txt (sem vazias).
        json_lines: Total de linhas do NDJSON.
        compared: Total de pares comparados.
        matches: Total de pares com hash igual.
        mismatch: Total de pares com hash diferente.
        missing_lh: Total de eventos sem campo lh.
        parse_errors: Total de erros de parse no NDJSON.
        extra_txt: Linhas extras no .txt sem par no NDJSON.
        extra_json: Linhas extras no NDJSON sem par no .txt.
        error_samples: Amostras de divergencias/erros.
    """

    txt_path: Path
    json_path: Path
    txt_lines: int = 0
    json_lines: int = 0
    compared: int = 0
    matches: int = 0
    mismatch: int = 0
    missing_lh: int = 0
    parse_errors: int = 0
    extra_txt: int = 0
    extra_json: int = 0
    error_samples: list[str] | None = None


def _raw_line_hash(raw_line: str) -> str:
    """Calcula o hash curto da linha bruta.

    Args:
        raw_line: Linha do .txt sem CRLF.

    Returns:
        Hash hexadecimal com 8 caracteres (blake2s digest_size=4).
    """
    return hashlib.blake2s(raw_line.encode("utf-8", "replace"), digest_size=4).hexdigest()


def _read_txt_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Le linhas do .txt com o mesmo criterio do conversor.

    Args:
        path: Caminho do arquivo .txt.

    Yields:
        Tuplas (numero_da_linha, linha_sem_CRLF) para linhas nao vazias.
    """
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for idx, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if line:
                yield idx, line


def _read_ndjson_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Le linhas do NDJSON sem parse imediato.

    Args:
        path: Caminho do arquivo .json (NDJSON).

    Yields:
        Tuplas (numero_da_linha, linha_sem_CRLF) para cada linha.
    """
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for idx, raw_line in enumerate(handle, start=1):
            yield idx, raw_line.rstrip("\r\n")


def _audit_pair(
    txt_path: Path, json_path: Path, *, max_samples: int = 30
) -> FileAuditResult:
    """Audita um par .txt e NDJSON em lockstep.

    Args:
        txt_path: Caminho do arquivo .txt.
        json_path: Caminho do arquivo NDJSON.
        max_samples: Limite de exemplos de erro no relatorio.

    Returns:
        Resultado agregado da auditoria para o par.
    """
    result = FileAuditResult(txt_path=txt_path, json_path=json_path, error_samples=[])
    txt_iter = _read_txt_lines(txt_path)
    json_iter = _read_ndjson_lines(json_path)

    for txt_item, json_item in zip_longest(txt_iter, json_iter, fillvalue=None):
        if txt_item is None:
            _record_extra_json(result, json_item, max_samples)
            continue
        if json_item is None:
            _record_extra_txt(result, txt_item, max_samples)
            continue

        _compare_pair(result, txt_item, json_item, max_samples)

    return result


def _append_sample(result: FileAuditResult, msg: str, max_samples: int) -> None:
    """Adiciona uma amostra de erro se houver espaco.

    Args:
        result: Estrutura de auditoria do arquivo.
        msg: Mensagem de amostra.
        max_samples: Limite maximo de amostras.
    """
    if result.error_samples is not None and len(result.error_samples) < max_samples:
        result.error_samples.append(msg)


def _record_extra_json(
    result: FileAuditResult,
    json_item: tuple[int, str] | None,
    max_samples: int,
) -> None:
    """Registra linha extra no NDJSON.

    Args:
        result: Estrutura de auditoria do arquivo.
        json_item: Tupla (linha, conteudo) do NDJSON.
        max_samples: Limite maximo de amostras.
    """
    result.extra_json += 1
    result.json_lines += 1
    json_no, json_line = json_item  # type: ignore[misc]
    _append_sample(result, f"extra_ndjson: line_json={json_no} len={len(json_line)}", max_samples)


def _record_extra_txt(
    result: FileAuditResult,
    txt_item: tuple[int, str] | None,
    max_samples: int,
) -> None:
    """Registra linha extra no .txt.

    Args:
        result: Estrutura de auditoria do arquivo.
        txt_item: Tupla (linha, conteudo) do .txt.
        max_samples: Limite maximo de amostras.
    """
    result.extra_txt += 1
    result.txt_lines += 1
    txt_no, txt_line = txt_item  # type: ignore[misc]
    _append_sample(result, f"extra_txt: line_txt={txt_no} len={len(txt_line)}", max_samples)


def _parse_ndjson_payload(
    result: FileAuditResult,
    txt_no: int,
    json_no: int,
    json_line: str,
    max_samples: int,
) -> dict[str, object] | None:
    """Parseia uma linha NDJSON e valida se e um objeto.

    Args:
        result: Estrutura de auditoria do arquivo.
        txt_no: Numero da linha no .txt.
        json_no: Numero da linha no NDJSON.
        json_line: Conteudo bruto da linha NDJSON.
        max_samples: Limite maximo de amostras.

    Returns:
        Objeto dict parseado ou None em caso de erro.
    """
    if not json_line:
        result.parse_errors += 1
        _append_sample(result, f"ndjson_empty: line_txt={txt_no} line_json={json_no}", max_samples)
        return None
    try:
        payload = json.loads(json_line)
    except json.JSONDecodeError as exc:
        result.parse_errors += 1
        _append_sample(
            result,
            f"ndjson_invalid: line_txt={txt_no} line_json={json_no} err={exc}",
            max_samples,
        )
        return None
    if not isinstance(payload, dict):
        result.parse_errors += 1
        _append_sample(
            result, f"ndjson_not_object: line_txt={txt_no} line_json={json_no}", max_samples
        )
        return None
    return payload


def _compare_pair(
    result: FileAuditResult,
    txt_item: tuple[int, str],
    json_item: tuple[int, str],
    max_samples: int,
) -> None:
    """Compara um par de linhas .txt/NDJSON.

    Args:
        result: Estrutura de auditoria do arquivo.
        txt_item: Tupla (linha, conteudo) do .txt.
        json_item: Tupla (linha, conteudo) do NDJSON.
        max_samples: Limite maximo de amostras.
    """
    txt_no, txt_line = txt_item
    json_no, json_line = json_item
    result.txt_lines += 1
    result.json_lines += 1
    result.compared += 1

    payload = _parse_ndjson_payload(result, txt_no, json_no, json_line, max_samples)
    if payload is None:
        return

    lh = payload.get("lh")
    if not isinstance(lh, str):
        result.missing_lh += 1
        _append_sample(result, f"missing_lh: line_txt={txt_no} line_json={json_no}", max_samples)
        return

    expected = _raw_line_hash(txt_line)
    if lh != expected:
        result.mismatch += 1
        _append_sample(
            result,
            f"hash_mismatch: line_txt={txt_no} line_json={json_no} expected={expected} got={lh}",
            max_samples,
        )
        return

    result.matches += 1


def _collect_pairs(
    logs_dir: Path, output_dir: Path
) -> tuple[list[tuple[Path, Path]], list[Path], list[Path]]:
    """Monta pares a partir de output_json e valida existencia do .txt.

    Args:
        logs_dir: Diretorio com arquivos .txt.
        output_dir: Diretorio com arquivos NDJSON.

    Returns:
        Tupla (pares, missing_json, missing_txt). missing_json e vazio por design.
    """
    json_files = {p.stem: p for p in output_dir.glob("*.json")}
    pairs: list[tuple[Path, Path]] = []
    missing_txt: list[Path] = []
    for stem in sorted(json_files):
        json_path = json_files[stem]
        txt_path = logs_dir / f"{stem}.txt"
        if txt_path.exists():
            pairs.append((txt_path, json_path))
        else:
            missing_txt.append(json_path)
    missing_json: list[Path] = []
    return pairs, missing_json, missing_txt


def _has_issues(result: FileAuditResult) -> bool:
    """Indica se o arquivo tem algum problema detectado."""
    return any(
        (
            result.mismatch,
            result.missing_lh,
            result.parse_errors,
            result.extra_txt,
            result.extra_json,
        )
    )


def _issue_tags(result: FileAuditResult) -> str:
    """Gera a lista de tags de erro para um arquivo."""
    tags: list[str] = []
    if result.mismatch:
        tags.append("mismatch")
    if result.missing_lh:
        tags.append("missing_lh")
    if result.parse_errors:
        tags.append("parse_errors")
    if result.extra_txt:
        tags.append("extra_txt")
    if result.extra_json:
        tags.append("extra_ndjson")
    return ", ".join(tags)


def _format_int(value: int) -> str:
    """Formata inteiros com separador de milhar em ponto."""
    return f"{value:,}".replace(",", ".")


def _write_report(
    path: Path,
    results: Iterable[FileAuditResult],
    missing_json: list[Path],
    missing_txt: list[Path],
) -> None:
    """Gera relatorio Markdown consolidado.

    Args:
        path: Caminho de saida do relatorio.
        results: Resultados por arquivo.
        missing_json: Lista de .txt sem NDJSON (vazio nesta estrategia).
        missing_txt: Lista de NDJSON sem .txt correspondente.
    """
    now = datetime.now()
    results_list = list(results)
    total_files = 0
    total_mismatch = 0
    total_missing_lh = 0
    total_parse_errors = 0
    total_extra_txt = 0
    total_extra_json = 0
    total_compared = 0
    total_txt_lines = 0
    total_json_lines = 0
    issue_files: list[FileAuditResult] = []

    for r in results_list:
        total_files += 1
        total_mismatch += r.mismatch
        total_missing_lh += r.missing_lh
        total_parse_errors += r.parse_errors
        total_extra_txt += r.extra_txt
        total_extra_json += r.extra_json
        total_compared += r.compared
        total_txt_lines += r.txt_lines
        total_json_lines += r.json_lines
        if _has_issues(r):
            issue_files.append(r)

    issues_present = bool(issue_files or missing_json or missing_txt)
    total_problem_files = len(issue_files) + len(missing_json) + len(missing_txt)

    lines: list[str] = []
    lines.append(f"# Relat\u00f3rio de Auditoria \u2014 {now:%Y-%m-%d %H:%M:%S}")
    lines.append("")
    lines.append("## Resumo Geral")
    lines.append("")
    lines.append("| M\u00e9trica | Valor |")
    lines.append("|---|---:|")
    lines.append(f"| Eventos comparados | {_format_int(total_compared)} |")
    lines.append(f"| Arquivos auditados | {_format_int(total_files)} |")
    lines.append(f"| Linhas totais (TXT) | {_format_int(total_txt_lines)} |")
    lines.append(f"| Linhas totais (NDJSON) | {_format_int(total_json_lines)} |")
    lines.append(f"| Arquivos com problema | {_format_int(total_problem_files)} |")
    lines.append("")
    lines.append("### Problemas (contagem)")
    lines.append("")
    lines.append(
        "| mismatch | missing_lh | parse_errors | extra_txt | extra_ndjson | missing_txt | missing_ndjson |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(
        "| "
        f"{_format_int(total_mismatch)} | {_format_int(total_missing_lh)} | "
        f"{_format_int(total_parse_errors)} | {_format_int(total_extra_txt)} | "
        f"{_format_int(total_extra_json)} | {_format_int(len(missing_txt))} | "
        f"{_format_int(len(missing_json))} |"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    if issues_present:
        lines.append("## Detalhes por Arquivo")
        lines.append("")
        lines.append("> **Colunas**")
        lines.append("> - `arquivo`: nome do arquivo com problema")
        lines.append("> - `erro`: etiquetas do problema")
        lines.append("> - `txt/ndjson/comp`: linhas do TXT / NDJSON / comparadas")
        lines.append(
            "> - `ok/mm/m_lh/pe/e_txt/e_ndj`: ok / mismatch / missing_lh / parse_errors / extra_txt / extra_ndjson"
        )
        lines.append("")
        lines.append("| Arquivo | erro | txt/ndjson/comp | ok/mm/m_lh/pe/e_txt/e_ndj |")
        lines.append("|---|---|---:|---:|")
        lines.extend(
            (
                "| "
                f"`{r.txt_path.name}` | {_issue_tags(r)} | "
                f"{r.txt_lines} / {r.json_lines} / {r.compared} | "
                f"{r.matches} / {r.mismatch} / {r.missing_lh} / "
                f"{r.parse_errors} / {r.extra_txt} / {r.extra_json} |"
            )
            for r in issue_files
        )
        lines.extend(
            (
                "| "
                f"`{txt_path.name}` | missing_ndjson | - / - / - | - / - / - / - / - / - |"
            )
            for txt_path in missing_json
        )
        lines.extend(
            (
                "| "
                f"`{json_path.with_suffix('.txt').name}` | missing_txt | - / - / - | - / - / - / - / - / - |"
            )
            for json_path in missing_txt
        )

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Ponto de entrada: audita e grava o relatorio na pasta tests."""
    base_dir = Path(__file__).resolve().parents[2]
    logs_dir = base_dir / "logs"
    output_dir = base_dir / "output_json"
    pairs, missing_json, missing_txt = _collect_pairs(logs_dir, output_dir)

    results: list[FileAuditResult] = []
    for txt_path, json_path in pairs:
        results.append(_audit_pair(txt_path, json_path))

    now = datetime.now()
    report_name = (
        f"{now.day:02d}_{now.month:02d}_{now.year}_{now.microsecond // 1000:03d}"
        "_relatorio_auditoria.md"
    )
    report_path = Path(__file__).resolve().parent / report_name
    _write_report(report_path, results, missing_json, missing_txt)


if __name__ == "__main__":
    main()
