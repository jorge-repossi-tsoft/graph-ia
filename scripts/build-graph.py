#!/usr/bin/env python3
"""
build-graph.py — indexador propio de GRAPH.

No depende de ninguna herramienta externa (nada de Reducto ni de ningún
otro indexador de terceros) — eso rompería el principio A (Agnostic).
Lee el repo con la librería estándar de Python únicamente y genera:

  .agents/graph/knowledge/nodes/<node>.json        (uno por archivo)
  .agents/graph/knowledge/communities/<comm>.json  (uno por carpeta de tope)
  .agents/graph/knowledge/index.json               (resumen + stats reales)

Método honesto (no es AST real, es heurística por extensión + regex):
  - node id = ruta relativa completa CON extensión (nunca solo el nombre
    base — ver GRAPH.md, principio G, "colisión de identidad").
  - community = primer segmento de carpeta desde la raíz del repo
    (heurística estructural simple, no community detection real tipo
    Louvain — se documenta así, sin pretender ser más de lo que es).
  - edges = imports/requires detectados por regex simple según extensión
    (JS/TS: import/require, Python: import/from, Go: import). Resueltos a
    nodos reales del repo cuando la ruta es relativa; si no se puede
    resolver, se guarda como referencia externa (no se inventa un nodo).

Uso: python3 build-graph.py <repo_root>
"""
import json
import os
import re
import sys
import time

IGNORE_DIRS = {
    ".git", "node_modules", "dist", "build", "__pycache__", "venv", ".venv",
    "target", "vendor", ".next", ".nuxt", "coverage", ".agents", ".cache",
    "out", ".turbo", ".pytest_cache", "reducto-out",
}
MAX_FILE_BYTES = 512_000  # no indexar archivos gigantes (assets, lockfiles, etc.)
TEXT_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".go", ".rb", ".php",
    ".java", ".kt", ".rs", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift",
    ".md", ".mdx", ".json", ".yml", ".yaml", ".css", ".scss", ".html",
    ".vue", ".svelte", ".sh", ".sql",
}

IMPORT_PATTERNS = [
    re.compile(r"""(?:import|from)\s+['"]([^'"]+)['"]"""),          # JS/TS ESM
    re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)"""),           # JS/TS CJS
    re.compile(r"""^\s*from\s+([\w\.]+)\s+import""", re.MULTILINE), # Python
    re.compile(r"""^\s*import\s+([\w\.]+)""", re.MULTILINE),        # Python
    re.compile(r"""^\s*import\s+\(?\s*"([^"]+)"\s*\)?""", re.MULTILINE),  # Go
]


def should_ignore(rel_dir_parts):
    return any(part in IGNORE_DIRS for part in rel_dir_parts)


def walk_repo(root):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        parts = [] if rel_dir == "." else rel_dir.split(os.sep)
        if should_ignore(parts):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for f in filenames:
            ext = os.path.splitext(f)[1].lower()
            if ext not in TEXT_EXTENSIONS:
                continue
            full = os.path.join(dirpath, f)
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            rel = os.path.relpath(full, root)
            files.append(rel.replace(os.sep, "/"))
    return sorted(files)


def read_text(root, rel_path):
    try:
        with open(os.path.join(root, rel_path), "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return ""


def extract_raw_refs(content):
    refs = []
    for pat in IMPORT_PATTERNS:
        refs.extend(pat.findall(content))
    return refs


def resolve_ref(root, from_node, raw_ref, all_nodes_set):
    """Intenta resolver un import/require a un nodo real del repo.
    Si no se puede (paquete externo, alias, etc.), devuelve None — nunca
    se inventa un nodo que no existe en el repo."""
    if raw_ref.startswith("."):
        base_dir = os.path.dirname(from_node)
        candidate = os.path.normpath(os.path.join(base_dir, raw_ref)).replace(os.sep, "/")
        for suffix in ["", ".js", ".jsx", ".ts", ".tsx", ".py", "/index.js", "/index.ts"]:
            probe = candidate + suffix
            if probe in all_nodes_set:
                return probe
        return None
    # Módulo Python tipo "paquete.submodulo" → intentar como paths con /
    py_guess = raw_ref.replace(".", "/") + ".py"
    if py_guess in all_nodes_set:
        return py_guess
    return None  # paquete externo (npm/pip/etc.) — no es un nodo del repo


def community_of(node_id):
    parts = node_id.split("/")
    return parts[0] if len(parts) > 1 else "_root"


def sanitize_filename(node_id):
    return node_id.replace("/", "__")


def main():
    if len(sys.argv) < 2:
        print("Uso: build-graph.py <repo_root>", file=sys.stderr)
        sys.exit(1)

    root = os.path.abspath(sys.argv[1])
    nodes_dir = os.path.join(root, ".agents", "graph", "knowledge", "nodes")
    communities_dir = os.path.join(root, ".agents", "graph", "knowledge", "communities")
    index_path = os.path.join(root, ".agents", "graph", "knowledge", "index.json")
    os.makedirs(nodes_dir, exist_ok=True)
    os.makedirs(communities_dir, exist_ok=True)

    all_nodes = walk_repo(root)
    all_nodes_set = set(all_nodes)

    references = {n: [] for n in all_nodes}
    for node in all_nodes:
        content = read_text(root, node)
        if not content:
            continue
        raw_refs = extract_raw_refs(content)
        resolved = []
        for raw in raw_refs:
            target = resolve_ref(root, node, raw, all_nodes_set)
            if target and target != node and target not in resolved:
                resolved.append(target)
        references[node] = resolved

    referenced_by = {n: [] for n in all_nodes}
    for node, refs in references.items():
        for target in refs:
            referenced_by[target].append(node)

    communities = {}
    for node in all_nodes:
        c = community_of(node)
        communities.setdefault(c, []).append(node)

    for node in all_nodes:
        node_doc = {
            "id": node,
            "community": community_of(node),
            "references": references[node],
            "referenced_by": referenced_by[node],
        }
        fname = sanitize_filename(node) + ".json"
        with open(os.path.join(nodes_dir, fname), "w", encoding="utf-8") as fh:
            json.dump(node_doc, fh, indent=2, ensure_ascii=False)

    for comm, members in communities.items():
        comm_doc = {"id": comm, "nodes": members}
        fname = sanitize_filename(comm) + ".json"
        with open(os.path.join(communities_dir, fname), "w", encoding="utf-8") as fh:
            json.dump(comm_doc, fh, indent=2, ensure_ascii=False)

    total_edges = sum(len(v) for v in references.values())
    index_doc = {
        "status": "indexed",
        "last_indexed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "method": "built-in structural indexer (regex-based imports, folder-based communities) — not full AST, not a third-party tool",
        "stats": {
            "nodes": len(all_nodes),
            "edges": total_edges,
            "communities": len(communities),
        },
    }
    with open(index_path, "w", encoding="utf-8") as fh:
        json.dump(index_doc, fh, indent=2, ensure_ascii=False)

    print(json.dumps(index_doc["stats"]))


if __name__ == "__main__":
    main()
