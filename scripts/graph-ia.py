#!/usr/bin/env python3
"""
graph-ia.py — bootstrapper standalone del patrón GRAPH.

Reimplementación determinística de commands/graph-ia.md (el comando que
usa el plugin de Claude Code), pero sin depender de ningún sistema de
plugins ni de que un agente de IA interprete instrucciones. Pensado para
herramientas sin plugin marketplace propio (Codex, Cursor, o directamente
sin ningún agente) — solo necesita Python 3, igual que build-graph.py.

Uso:
  python3 graph-ia.py [repo_root] --mode=greenfield|brownfield [--migrate]

repo_root por defecto es el directorio actual. Mismo contrato que la
versión de plugin:
  - nunca pisa un archivo que ya existe (safe copy)
  - brownfield corre el indexador propio (build-graph.py) y reconcilia
    el historial de git
  - deja AGENTS.md/CLAUDE.md listos en la raíz del repo objetivo

Límite honesto: los 3 hooks de enforcement (circuit breaker) solo se
activan solos cuando GRAPH se instala como plugin de Claude Code. Corrido
así, standalone, Circuit Breaker queda declarativo únicamente hasta que
conectes un adaptador para tu herramienta — ver
.agents/graph/enforcement/README.md.
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(SCRIPT_DIR, "..", "templates")
BRIDGE_MARKER = "<!-- graph-ia:bridge-block -->"
BRIDGE_END_MARKER = "<!-- /graph-ia:bridge-block -->"
LEGACY_LINE_PLACEHOLDER = "<!-- graph-ia:legacy-line -->"
LEGACY_LINE_TEXT = "- `.agents/graph/legacy-system.md` — sistema anterior migrado, consultalo también."

COPY_MAP = [
    ("graph/GRAPH.md", ".agents/graph/GRAPH.md"),
    ("graph/README.md", ".agents/graph/README.md"),
    ("graph/circuit-breaker.yml", ".agents/graph/circuit-breaker.yml"),
    ("graph/gates/policy.yml", ".agents/graph/gates/policy.yml"),
    ("roles/registry.yml", ".agents/roles/registry.yml"),
    ("roles/planner.md", ".agents/roles/planner.md"),
    ("roles/executor.md", ".agents/roles/executor.md"),
    ("roles/reviewer.md", ".agents/roles/reviewer.md"),
    ("graph/sessions/progress.md", ".agents/graph/sessions/progress.md"),
    ("graph/sessions/tasks.md", ".agents/graph/sessions/tasks.md"),
    ("graph/enforcement/README.md", ".agents/graph/enforcement/README.md"),
]

FOLDER_TREE = [
    ".agents/graph/knowledge/nodes",
    ".agents/graph/knowledge/communities",
    ".agents/graph/history",
    ".agents/graph/gates/pending",
    ".agents/graph/gates/approved",
    ".agents/graph/sessions",
    ".agents/graph/enforcement",
    ".agents/roles",
    ".agents/skills",
]

MIGRATE_MAP = [
    ("progress.md", "graph/sessions/progress.md"),
    ("tasks.md", "graph/sessions/tasks.md"),
    ("system.md", "graph/legacy-system.md"),
]

def log(msg=""):
    print(msg)


def safe_copy(src, dst, report):
    if os.path.exists(dst):
        report["skipped"].append(dst)
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    report["created"].append(dst)


def do_migration(root, report):
    for old_name, new_rel in MIGRATE_MAP:
        old_path = os.path.join(root, ".agents", old_name)
        if not os.path.isfile(old_path):
            continue
        new_path = os.path.join(root, ".agents", *new_rel.split("/"))
        if os.path.exists(new_path):
            report["migration_skipped"].append((old_path, new_path))
            continue
        today = datetime.date.today().isoformat()
        with open(old_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        with open(new_path, "w", encoding="utf-8") as fh:
            fh.write(f"<!-- Migrado automáticamente desde {old_name} el {today} -->\n\n{content}")
        # Migraci?n no destructiva: conservamos el archivo original del usuario.
        report["migrated"].append((old_path, new_path))


def create_folder_tree(root, report):
    for rel in FOLDER_TREE:
        path = os.path.join(root, *rel.split("/"))
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
            report["folders_created"].append(rel)


def init_index(root, mode, report):
    index_path = os.path.join(root, ".agents", "graph", "knowledge", "index.json")
    if os.path.exists(index_path):
        report["index_skipped"] = True
        return

    if mode == "greenfield":
        doc = {
            "status": "empty",
            "reason": "greenfield — se puebla en paralelo al código",
            "last_indexed": None,
        }
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, ensure_ascii=False)
        return

    # brownfield — bloqueante: index -> build-graph.py -> reconciliar git
    doc = {"status": "indexing", "reason": "brownfield — indexación inicial en curso", "last_indexed": None}
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)

    build_graph = os.path.join(SCRIPT_DIR, "build-graph.py")
    result = subprocess.run([sys.executable, build_graph, root], capture_output=True, text=True)
    if result.returncode != 0:
        log("El indexador (build-graph.py) falló:")
        log(result.stderr)
        sys.exit(1)
    report["index_stats"] = json.loads(result.stdout.strip().splitlines()[-1])

    reconcile_git_history(root, report)


def reconcile_git_history(root, report):
    history_dir = os.path.join(root, ".agents", "graph", "history")
    marker = os.path.join(history_dir, ".git-log-import-pending")
    out_path = os.path.join(history_dir, "pre-graph-commits.md")

    if os.path.exists(out_path):
        report["git_reconciled"] = "already"
        return
    if not os.path.isdir(os.path.join(root, ".git")):
        report["git_reconciled"] = "no-git-repo"
        return

    os.makedirs(history_dir, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as fh:
        fh.write("reconciliation in progress\n")

    result = subprocess.run(
        ["git", "-C", root, "log", "--pretty=format:%H|%ad|%s", "--date=short"],
        capture_output=True, text=True,
    )
    lines = ["# Historial pre-GRAPH", ""]
    commit_count = 0
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                sha, date, subject = parts
                lines.append(f"- `{sha[:10]}` ({date}) origen: pre-graph — {subject}")
                commit_count += 1
    else:
        lines.append("(no se pudo leer git log)")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    os.remove(marker)
    report["git_reconciled"] = commit_count


def copy_base_files(root, report):
    for rel_src, rel_dst in COPY_MAP:
        src = os.path.join(TEMPLATES_DIR, *rel_src.split("/"))
        dst = os.path.join(root, *rel_dst.split("/"))
        if os.path.isfile(src):
            safe_copy(src, dst, report)


def _canonical_block(filename, legacy_exists):
    """Lee el bloque administrado (entre marcadores, marcadores incluidos)
    directamente de templates/<filename> — esa es la única fuente de verdad,
    para que no se pueda desincronizar de lo que ve un install fresco."""
    src = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.isfile(src):
        return None
    with open(src, "r", encoding="utf-8") as fh:
        content = fh.read()
    start = content.find(BRIDGE_MARKER)
    end = content.find(BRIDGE_END_MARKER)
    if start == -1 or end == -1 or end < start:
        return None
    block = content[start:end + len(BRIDGE_END_MARKER)]
    if legacy_exists:
        block = block.replace(LEGACY_LINE_PLACEHOLDER, LEGACY_LINE_TEXT)
    else:
        # sacamos el placeholder y la línea en blanco que deja atrás
        block = "\n".join(
            line for line in block.split("\n") if line.strip() != LEGACY_LINE_PLACEHOLDER
        )
    return block


def _adapt_prefix(block, nested):
    """El bloque canónico asume que el archivo vive en la raíz del repo
    (paths con prefijo `.agents/`). Si en cambio ya vive adentro de
    `.agents/` (caso `nested`), esos paths son relativos y no llevan
    ese prefijo."""
    return block.replace(".agents/", "") if nested else block


def place_bridge(root, filename, report, legacy_exists, update=False):
    root_path = os.path.join(root, filename)
    agents_path = os.path.join(root, ".agents", filename)

    existing, nested = None, False
    if os.path.isfile(root_path):
        existing, nested = root_path, False
    elif os.path.isfile(agents_path):
        existing, nested = agents_path, True

    canonical = _canonical_block(filename, legacy_exists)

    if existing:
        with open(existing, "r", encoding="utf-8") as fh:
            content = fh.read()
        desired_block = _adapt_prefix(canonical, nested) if canonical else None
        start = content.find(BRIDGE_MARKER)
        end = content.find(BRIDGE_END_MARKER)

        if start != -1 and end != -1 and end > start:
            old_block = content[start:end + len(BRIDGE_END_MARKER)]
            if desired_block is None or old_block == desired_block:
                report["bridges_skipped"].append(existing)
                return
            if not update:
                report["bridges_stale"].append(existing)
                return
            new_content = content[:start] + desired_block + content[end + len(BRIDGE_END_MARKER):]
            with open(existing, "w", encoding="utf-8") as fh:
                fh.write(new_content)
            report["bridges_updated"].append(existing)
            return

        if start != -1:
            # formato viejo: tiene marcador de inicio pero no de cierre —
            # asumimos que el bloque viejo ocupaba desde ahí hasta el final
            # del archivo (así lo escribían las versiones anteriores).
            if desired_block is None:
                report["bridges_skipped"].append(existing)
                return
            if not update:
                report["bridges_stale"].append(existing)
                return
            new_content = content[:start] + desired_block + "\n"
            with open(existing, "w", encoding="utf-8") as fh:
                fh.write(new_content)
            report["bridges_updated"].append(existing)
            return

        # no hay marcador todavía — primera vez que se agrega el bridge
        if desired_block is None:
            return
        new_content = content.rstrip("\n") + "\n\n" + desired_block + "\n"
        with open(existing, "w", encoding="utf-8") as fh:
            fh.write(new_content)
        report["bridges_appended"].append(existing)
        return

    src = os.path.join(TEMPLATES_DIR, filename)
    if os.path.isfile(src):
        with open(src, "r", encoding="utf-8") as fh:
            content = fh.read()
        if legacy_exists:
            content = content.replace(LEGACY_LINE_PLACEHOLDER, LEGACY_LINE_TEXT)
        else:
            content = "\n".join(
                line for line in content.split("\n") if line.strip() != LEGACY_LINE_PLACEHOLDER
            )
        with open(root_path, "w", encoding="utf-8") as fh:
            fh.write(content)
        report["bridges_created"].append(root_path)


def stamp_mode(root, mode, report):
    tasks_path = os.path.join(root, ".agents", "graph", "sessions", "tasks.md")
    if tasks_path not in report["created"]:
        return  # migrado o ya existía — no tocar
    with open(tasks_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    content = content.replace(
        "Modo detectado: greenfield | brownfield",
        f"Modo detectado: {mode}",
    )
    with open(tasks_path, "w", encoding="utf-8") as fh:
        fh.write(content)


def print_summary(mode, migrate, root, report):
    log()
    log(f"=== graph-ia standalone — {root} — modo {mode} ===")
    if migrate:
        for old, new in report["migrated"]:
            log(f"  migrado: {old} -> {new}")
        for old, new in report["migration_skipped"]:
            log(f"  migración omitida (ya existe destino): {old} / {new} — ambos quedaron intactos")
    if report["folders_created"]:
        log(f"  carpetas nuevas: {len(report['folders_created'])}")
    if report["created"]:
        log(f"  archivos creados: {len(report['created'])}")
        for f in report["created"]:
            log(f"    + {f}")
    if report["skipped"]:
        log(f"  archivos ya existentes, no tocados: {len(report['skipped'])}")
        for f in report["skipped"]:
            log(f"    = {f}")
    for f in report["bridges_created"]:
        log(f"  bridge creado: {f}")
    for f in report["bridges_appended"]:
        log(f"  bridge agregado (append) a: {f}")
    for f in report["bridges_skipped"]:
        log(f"  bridge ya al día, no tocado: {f}")
    for f in report["bridges_updated"]:
        log(f"  bridge resincronizado (bloque administrado reemplazado, resto del archivo intacto): {f}")
    for f in report["bridges_stale"]:
        log(f"  bridge desactualizado, no tocado (corré con --update-docs para resincronizarlo): {f}")
    if report.get("index_stats"):
        s = report["index_stats"]
        log(f"  indexación: {s['nodes']} nodos, {s['edges']} edges, {s['communities']} comunidades")
    elif report.get("index_skipped"):
        log("  indexación: index.json ya existía, no se re-indexó (usá --reindex para forzarlo)")
    gr = report.get("git_reconciled")
    if isinstance(gr, int):
        log(f"  historial git reconciliado: {gr} commits marcados origen: pre-graph")
    elif gr == "no-git-repo":
        log("  historial git: no se encontró .git en la raíz, se omitió la reconciliación")
    elif gr == "already":
        log("  historial git: ya estaba reconciliado (pre-graph-commits.md existente)")
    if report["docs_updated"]:
        log(f"  documentación actualizada: {len(report['docs_updated'])}")
        for f in report["docs_updated"]:
            log(f"    ~ {f}")
        for f in report["docs_backed_up"]:
            log(f"    (backup guardado en {f})")
    log()
    log("Nota: los 3 hooks de enforcement (circuit breaker) solo se activan solos")
    log("cuando GRAPH se instala como plugin de Claude Code o Codex CLI. Corriendo")
    log("standalone, Circuit Breaker queda declarativo únicamente — ver")
    log(".agents/graph/enforcement/README.md para agregar un adaptador a tu herramienta.")


def reindex_only(root, report):
    """Vuelve a correr el indexador y la reconciliación de git aunque
    knowledge/index.json ya exista. No toca templates ni config — solo
    knowledge/ y history/."""
    if not os.path.isdir(os.path.join(root, ".agents", "graph")):
        log("No hay .agents/graph/ en este repo — corré graph-ia.py con --mode primero.")
        sys.exit(1)

    build_graph = os.path.join(SCRIPT_DIR, "build-graph.py")
    result = subprocess.run([sys.executable, build_graph, root], capture_output=True, text=True)
    if result.returncode != 0:
        log("El indexador (build-graph.py) falló:")
        log(result.stderr)
        sys.exit(1)
    report["index_stats"] = json.loads(result.stdout.strip().splitlines()[-1])
    report["index_skipped"] = False

    # La reconciliación de git usa su propio marcador de "ya hecho"
    # (pre-graph-commits.md) — si querés forzarla de nuevo, borrá ese
    # archivo antes de correr --reindex.
    reconcile_git_history(root, report)


# Solo documentación del patrón — nunca config ni datos de sesión del usuario.
DOC_ONLY_MAP = [
    ("graph/GRAPH.md", ".agents/graph/GRAPH.md"),
    ("graph/README.md", ".agents/graph/README.md"),
    ("roles/planner.md", ".agents/roles/planner.md"),
    ("roles/executor.md", ".agents/roles/executor.md"),
    ("roles/reviewer.md", ".agents/roles/reviewer.md"),
]


def update_docs(root, report):
    """Sobreescribe SOLO la documentación genérica del patrón (GRAPH.md,
    graph/README.md, roles/*.md) con la versión actual del plugin, y
    resincroniza el bloque administrado de AGENTS.md/CLAUDE.md (idempotente,
    preserva todo lo que el usuario haya escrito fuera del bloque). Hace un
    .bak del archivo viejo antes de tocar los docs. Deliberadamente NO toca:
    circuit-breaker.yml, gates/policy.yml, roles/registry.yml (puede tener
    roles custom), progress.md, tasks.md — esos son estado o config del
    proyecto, no documentación genérica del patrón."""
    if not os.path.isdir(os.path.join(root, ".agents", "graph")):
        log("No hay .agents/graph/ en este repo — corré graph-ia.py con --mode primero.")
        sys.exit(1)

    for rel_src, rel_dst in DOC_ONLY_MAP:
        src = os.path.join(TEMPLATES_DIR, *rel_src.split("/"))
        dst = os.path.join(root, *rel_dst.split("/"))
        if not os.path.isfile(src):
            continue
        if os.path.isfile(dst):
            with open(src, "rb") as f1, open(dst, "rb") as f2:
                if f1.read() == f2.read():
                    continue  # ya está igual, no hace falta ni backup
            bak_path = dst + ".bak"
            shutil.copyfile(dst, bak_path)
            report["docs_backed_up"].append(bak_path)
        shutil.copyfile(src, dst)
        report["docs_updated"].append(dst)

    legacy_exists = os.path.isfile(os.path.join(root, ".agents", "graph", "legacy-system.md"))
    place_bridge(root, "AGENTS.md", report, legacy_exists, update=True)
    place_bridge(root, "CLAUDE.md", report, legacy_exists, update=True)


def main():
    parser = argparse.ArgumentParser(description="Bootstrap standalone del patrón GRAPH (sin plugin system).")
    parser.add_argument("repo_root", nargs="?", default=".", help="raíz del proyecto donde instalar GRAPH")
    parser.add_argument("--mode", choices=["greenfield", "brownfield"], help="requerido salvo con --reindex/--update-docs solos")
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--reindex", action="store_true",
                         help="Vuelve a correr build-graph.py y reconciliar git, aunque knowledge/index.json ya exista. No toca nada más.")
    parser.add_argument("--update-docs", action="store_true",
                         help="Sobreescribe GRAPH.md, graph/README.md y roles/*.md con la versión actual del plugin "
                              "(hace .bak del archivo viejo antes), y resincroniza el bloque administrado de "
                              "AGENTS.md/CLAUDE.md de forma idempotente (reemplaza solo lo que está entre "
                              "los marcadores graph-ia:bridge-block, preserva el resto del archivo tal cual). "
                              "NUNCA toca circuit-breaker.yml, gates/policy.yml, progress.md ni tasks.md — esos son tuyos.")
    args = parser.parse_args()

    root = os.path.abspath(args.repo_root)
    if not os.path.isdir(root):
        log(f"No existe el directorio: {root}")
        sys.exit(1)

    report = {
        "created": [], "skipped": [], "migrated": [], "migration_skipped": [],
        "folders_created": [], "bridges_created": [], "bridges_appended": [], "bridges_skipped": [],
        "bridges_updated": [], "bridges_stale": [],
        "index_stats": None, "index_skipped": False, "git_reconciled": None,
        "docs_updated": [], "docs_backed_up": [],
    }

    # --reindex y --update-docs pueden correr solos (o combinados), sin
    # --mode, sobre un proyecto que ya tiene GRAPH instalado.
    if not args.mode and (args.reindex or args.update_docs):
        if args.reindex:
            reindex_only(root, report)
        if args.update_docs:
            update_docs(root, report)
        if args.reindex and args.update_docs:
            summary_mode = "reindex+update-docs"
        elif args.reindex:
            summary_mode = "reindex-only"
        else:
            summary_mode = "update-docs-only"
        print_summary(summary_mode, False, root, report)
        return

    if not args.mode:
        log("Falta --mode=greenfield o --mode=brownfield (o usá --reindex / --update-docs solo).")
        sys.exit(1)

    if args.migrate:
        do_migration(root, report)

    create_folder_tree(root, report)
    init_index(root, args.mode, report)
    copy_base_files(root, report)

    legacy_exists = os.path.isfile(os.path.join(root, ".agents", "graph", "legacy-system.md"))
    place_bridge(root, "AGENTS.md", report, legacy_exists)
    place_bridge(root, "CLAUDE.md", report, legacy_exists)

    stamp_mode(root, args.mode, report)

    if args.reindex:
        reindex_only(root, report)
    if args.update_docs:
        update_docs(root, report)

    print_summary(args.mode, args.migrate, root, report)


if __name__ == "__main__":
    main()


