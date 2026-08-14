#!/usr/bin/env python3
"""
graph-prompt.py - gestor de backlog prompt-driven para el patron GRAPH.

Uso:
  python3 scripts/graph-prompt.py [repo_root] "#task <descripcion>"
  python3 scripts/graph-prompt.py [repo_root] "#run"
  python3 scripts/graph-prompt.py [repo_root] "#run 2: resultado breve"
  python3 scripts/graph-prompt.py [repo_root] "#run T-20260807-002: resultado breve"
  python3 scripts/graph-prompt.py [repo_root] "#run-all: cierre de sprint"
  python3 scripts/graph-prompt.py [repo_root] "#done 2: ya estaba resuelta"
  python3 scripts/graph-prompt.py [repo_root] "#skip 3: fuera de alcance"
  python3 scripts/graph-prompt.py [repo_root] "#note 1: falta definir el endpoint"

Comandos soportados sobre el backlog del proyecto:
  #task     agrega una tarea nueva a `Tareas pendientes` con un ID estable
            (`T-YYYYMMDD-NNN`, contador por dia) guardado como metadata.
  #run      ejecuta (marca completada) la siguiente pendiente, `#run N`
            (posicion entre pendientes) o `#run T-YYYYMMDD-NNN` (ID estable).
  #run-all  ejecuta todas las pendientes (alias de `#run all`).
  #done     marca una tarea como completada sin pasar por ejecucion. Acepta
            posicion o ID, igual que `#run`.
  #skip     saltea una tarea (posicion o ID): sale de pendientes y queda
            registrada aparte.
  #note     agrega una nota fechada debajo de una tarea pendiente (posicion
            o ID).

El ID es la referencia estable: no cambia si se completan, saltean o
agregan tareas antes. La posicion (`N`) es solo un atajo de conveniencia
sobre el estado actual de `Tareas pendientes` y puede correrse de tarea al
modificarse el backlog.

Este script materializa esas ordenes en archivos persistentes:
`.agents/graph/sessions/tasks.md` y `.agents/graph/sessions/progress.md`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

TASKS_FILE_REL = Path(".agents") / "graph" / "sessions" / "tasks.md"
PROGRESS_FILE_REL = Path(".agents") / "graph" / "sessions" / "progress.md"

TASKS_SKELETON = """# Tasks

> Archivo de backlog para GRAPH.
>
> `#task` agrega tareas nuevas aqui. `#run` / `#run-all` / `#done` marcan
> tareas como completadas y actualizan `progress.md`. `#skip` saltea una
> tarea dejando registro, y `#note` agrega una nota fechada a una tarea.

## Instalacion del patron (marcar al hacer graph-ia)
- [ ] Modo detectado: greenfield | brownfield
- [ ] Arbol de carpetas creado
- [ ] (brownfield only) Indexacion inicial completa - bloqueante, ningun agente opera antes de esto
- [ ] (brownfield only) Reconciliacion de historial via git log completada, commits marcados `origen: pre-graph`
- [ ] circuit-breaker.yml revisado y ajustado a este proyecto (los defaults son conservadores)
- [ ] policy.yml revisado - las severidades por defecto tienen sentido para este proyecto?
- [ ] roles/registry.yml - que roles se activan en este proyecto? (no todos son obligatorios)

## Backlog del proyecto
### Tareas pendientes

### Tareas en curso

### Tareas completadas (referenciar en `progress.md`)

### Tareas salteadas (con motivo)

## Backlog Execution Policy
El backlog se interpreta como un grafo dirigido de dependencias, no como una lista plana.
Antes de ejecutar, validar `depends_on`, `blocked_by`, `requires`, `parent` y `prerequisite`.
Si una dependencia no esta completed, frenar y registrar el bloqueo en `progress.md`.
"""

PROGRESS_SKELETON = """# Progress

> Este archivo es la memoria persistente entre sesiones (principio P).
> Cada sesion de trabajo debe actualizar esto antes de cerrar - no confiar
> en que el contexto de la conversacion sobreviva.

## Estado actual
- Instalacion: <greenfield | brownfield> - completada el <fecha>
- Indexacion inicial: <pendiente | completa>
- Reconciliacion de historial (solo brownfield): <n/a | importado via git log | omitido>
- Backlog activo: <numero de tareas pendientes>
- Ultima ejecucion de `#run`: <fecha o n/a>

## Ultima sesion
- Fecha:
- Que se hizo:
- Tareas completadas:
  - [x] <tarea 1> - nota breve
- Tareas pendientes que siguen en `tasks.md`:
  - [ ] <tarea 2>
- Por que (si algo se corto por circuit breaker, referenciar el evento en `graph/history/circuit-breaker-events.jsonl`):
  - <detalle>

## Proxima sesion deberia
- <que se espera avanzar a continuacion>

## Notas adicionales
- <observaciones relevantes, decisiones, riesgos, bloqueos>

## Historial de ejecuciones
"""

SECTION_PENDING = "### Tareas pendientes"
SECTION_COMPLETED_HEADER = "### Tareas completadas (referenciar en `progress.md`)"
SECTION_SKIPPED_HEADER = "### Tareas salteadas (con motivo)"
SECTION_HISTORY_HEADER = "## Historial de ejecuciones"

TASK_ID_RE = r"T-\d{8}-\d+"
TASK_ID_PATTERN = re.compile(TASK_ID_RE, re.IGNORECASE)
_TARGET_RE = rf"\d+|all|{TASK_ID_RE}"

TASK_PATTERN = re.compile(r"^\s*#task\s+(.+)$", re.IGNORECASE | re.DOTALL)
RUN_ALL_PATTERN = re.compile(r"^\s*#run-all(?:\s*[:\-]\s*(.+))?\s*$", re.IGNORECASE)
RUN_PATTERN = re.compile(rf"^\s*#run(?:\s+({_TARGET_RE}))?(?:\s*[:\-]\s*(.+))?\s*$", re.IGNORECASE)
DONE_PATTERN = re.compile(rf"^\s*#done(?:\s+({_TARGET_RE}))?(?:\s*[:\-]\s*(.+))?\s*$", re.IGNORECASE)
SKIP_PATTERN = re.compile(rf"^\s*#skip(?:\s+(\d+|{TASK_ID_RE}))?(?:\s*[:\-]\s*(.+))?\s*$", re.IGNORECASE)
NOTE_PATTERN = re.compile(rf"^\s*#note(?:\s+(\d+|{TASK_ID_RE})(?=\s|[:\-]))?\s*[:\-]?\s*(.+)$", re.IGNORECASE | re.DOTALL)
METADATA_PATTERN = re.compile(r"(?P<key>[a-zA-Z_][\w\-]*):(?P<value>\"[^\"]+\"|[^\s]+)")
METADATA_LINE_PATTERN = re.compile(r"^\s{4,}-\s+(?P<key>[a-zA-Z_][\w\-]*):\s*(?P<value>\"[^\"]+\"|.+)$")
DEPENDENCY_FIELDS = {"depends_on", "blocked_by", "requires", "parent", "prerequisite"}


@dataclass
class TaskEntry:
    start_index: int
    end_index: int
    text: str
    done: bool
    metadata: Dict[str, str]
    status: str = "pending"


class DependencyBlockedError(ValueError):
    def __init__(self, message: str, task: str, dependency: str, state: str) -> None:
        super().__init__(message)
        self.task = task
        self.dependency = dependency
        self.state = state


def ensure_file(path: Path, content: str) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def write_lines(path: Path, lines: List[str]) -> None:
    path.write_text("".join(lines), encoding="utf-8")


def find_section(lines: List[str], header: str) -> Optional[int]:
    for index, line in enumerate(lines):
        if line.strip() == header:
            return index
    return None


def find_section_end(lines: List[str], start: int) -> int:
    def heading_level(text: str) -> int:
        stripped = text.lstrip()
        if not stripped.startswith("#"):
            return 0
        return len(stripped) - len(stripped.lstrip("#"))

    start_level = heading_level(lines[start])
    index = start + 1
    while index < len(lines):
        current_level = heading_level(lines[index])
        if current_level and current_level <= start_level:
            break
        index += 1
    return index


def normalize_task_text(text: str) -> str:
    return " ".join(line.strip() for line in text.strip().splitlines())


def parse_task_prompt(prompt: str) -> Tuple[str, Dict[str, str]]:
    text = normalize_task_text(prompt)
    metadata: Dict[str, str] = {}

    for match in METADATA_PATTERN.finditer(text):
        key = match.group("key")
        value = match.group("value")
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        metadata[key] = value

    title = normalize_task_text(METADATA_PATTERN.sub("", text))
    if not title:
        raise ValueError("La tarea necesita un titulo valido.")

    return title, metadata


def format_task_metadata(metadata: Dict[str, str]) -> str:
    items = [f"{key}:{value}" for key, value in metadata.items()]
    return " " + " ".join(items) if items else ""


def format_task_metadata_block(metadata: Dict[str, str]) -> List[str]:
    lines: List[str] = []
    for key, value in metadata.items():
        lines.append(f"    - {key}: {value}\n")
    return lines


def task_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def today_iso() -> str:
    return date.today().isoformat()


def next_stable_task_id(lines: List[str]) -> str:
    """ID estable con formato T-YYYYMMDD-NNN, contador por dia. Escanea todo
    el archivo (pendientes, en curso, completadas, salteadas) para no repetir
    numero aunque la tarea con ese ID ya se haya movido de seccion."""
    day = date.today().strftime("%Y%m%d")
    max_n = 0
    for line in lines:
        for match in TASK_ID_PATTERN.finditer(line):
            found = match.group(0).upper()
            if found.startswith(f"T-{day}-"):
                max_n = max(max_n, int(found.rsplit("-", 1)[1]))
    return f"T-{day}-{max_n + 1:03d}"


def find_task_by_id(entries: List["TaskEntry"], task_id_value: str) -> Optional["TaskEntry"]:
    normalized = task_id_value.upper()
    for entry in entries:
        if entry.metadata.get("id", "").upper() == normalized:
            return entry
    return None


def dependency_ids(task: TaskEntry) -> List[str]:
    deps: List[str] = []
    for field in DEPENDENCY_FIELDS:
        value = task.metadata.get(field)
        if not value:
            continue
        found = [match.group(0).upper() for match in TASK_ID_PATTERN.finditer(value)]
        if not found:
            raise ValueError(
                f"La tarea {task.metadata.get('id', task.text)} declara {field} pero no usa un ID estable T-YYYYMMDD-NNN."
            )
        deps.extend(found)
    return list(dict.fromkeys(deps))


def task_identity(task: TaskEntry) -> str:
    return task.metadata.get("id") or task.text


def build_task_index(lines: List[str]) -> Dict[str, TaskEntry]:
    index: Dict[str, TaskEntry] = {}
    for task in parse_tasks_with_metadata(lines):
        task_id_value = task.metadata.get("id", "").upper()
        if task_id_value:
            index[task_id_value] = task
    return index


def validate_task_dependencies(
    task: TaskEntry,
    task_index: Dict[str, TaskEntry],
    stack: Optional[Set[str]] = None,
) -> None:
    stack = set(stack or set())
    current_id = task.metadata.get("id", "").upper()
    if current_id:
        if current_id in stack:
            raise ValueError(f"Dependencia ciclica detectada en {current_id}.")
        stack.add(current_id)

    for dep_id in dependency_ids(task):
        dependency = task_index.get(dep_id)
        if dependency is None:
            raise DependencyBlockedError(
                f"No se puede ejecutar {task_identity(task)}: la dependencia {dep_id} no existe en el backlog.",
                task_identity(task),
                dep_id,
                "missing",
            )
        if dependency.status == "skipped":
            raise DependencyBlockedError(
                f"No se puede ejecutar {task_identity(task)}: la dependencia {dep_id} fue salteada y requiere re-planificacion.",
                task_identity(task),
                dep_id,
                "skipped",
            )
        if dependency.status != "completed":
            raise DependencyBlockedError(
                f"No se puede ejecutar {task_identity(task)}: la dependencia {dep_id} esta {dependency.status}, no completed.",
                task_identity(task),
                dep_id,
                dependency.status,
            )
        validate_task_dependencies(dependency, task_index, stack)


def sanitize_filename(node_id: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_]+", "__", node_id)
    return sanitized.strip("_") or "node"


def should_create_node(metadata: Dict[str, str]) -> bool:
    if "path" in metadata or "file" in metadata:
        return True
    return metadata.get("type", "").lower() in {"component", "page", "layout", "route", "service"}


def normalize_node_id(title: str, metadata: Dict[str, str]) -> str:
    if "path" in metadata:
        return metadata["path"].replace("\\", "/").strip("/")
    if "file" in metadata:
        return metadata["file"].replace("\\", "/").strip("/")
    base = title.lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_\/]+", "", base)


def update_community(root: str, community: str, node_id: str) -> None:
    communities_dir = Path(root) / ".agents" / "graph" / "knowledge" / "communities"
    communities_dir.mkdir(parents=True, exist_ok=True)
    community_path = communities_dir / (sanitize_filename(community) + ".json")
    if community_path.exists():
        data = json.loads(community_path.read_text(encoding="utf-8"))
    else:
        data = {"id": community, "nodes": []}

    if node_id not in data.get("nodes", []):
        data.setdefault("nodes", []).append(node_id)

    community_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def sync_index_counts(root: str) -> None:
    index_path = Path(root) / ".agents" / "graph" / "knowledge" / "index.json"
    nodes_dir = Path(root) / ".agents" / "graph" / "knowledge" / "nodes"
    communities_dir = Path(root) / ".agents" / "graph" / "knowledge" / "communities"
    index_path.parent.mkdir(parents=True, exist_ok=True)

    if index_path.exists():
        index_data = json.loads(index_path.read_text(encoding="utf-8"))
    else:
        index_data = {"status": "generated", "last_indexed": None, "stats": {}}

    try:
        nodes = [f for f in nodes_dir.iterdir() if f.is_file() and f.suffix == ".json"]
        communities = [f for f in communities_dir.iterdir() if f.is_file() and f.suffix == ".json"]
    except OSError:
        return

    index_data.setdefault("stats", {})["nodes"] = len(nodes)
    index_data.setdefault("stats", {})["communities"] = len(communities)
    index_path.write_text(json.dumps(index_data, indent=2, ensure_ascii=False), encoding="utf-8")


def create_knowledge_node(root: str, title: str, metadata: Dict[str, str]) -> Optional[str]:
    if not should_create_node(metadata):
        return None

    node_id = normalize_node_id(title, metadata)
    if not node_id:
        node_id = f"task/{task_id()}"

    nodes_dir = Path(root) / ".agents" / "graph" / "knowledge" / "nodes"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    node_path = nodes_dir / (sanitize_filename(node_id) + ".json")

    node_doc = {
        "id": node_id,
        "community": metadata.get("community", "_root"),
        "type": metadata.get("type", "task"),
        "title": title,
        "description": metadata.get("description", ""),
        "references": [],
        "referenced_by": [],
        "origin": "task",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "task_prompt": title + format_task_metadata(metadata),
    }

    if not node_path.exists():
        node_path.write_text(json.dumps(node_doc, indent=2, ensure_ascii=False), encoding="utf-8")

    update_community(root, node_doc["community"], node_id)
    sync_index_counts(root)
    return str(node_path)


def append_pending_task(lines: List[str], task_text: str, metadata: Dict[str, str]) -> Tuple[List[str], str]:
    task_line = f"- [ ] {task_text}\n"
    metadata_lines = format_task_metadata_block(metadata)
    section_start = find_section(lines, SECTION_PENDING)
    if section_start is None:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(SECTION_PENDING + "\n")
        lines.append("\n")
        lines.append(task_line)
        lines.extend(metadata_lines)
        return lines, task_line.strip()

    insert_at = find_section_end(lines, section_start)
    lines.insert(insert_at, task_line)
    for offset, metadata_line in enumerate(metadata_lines, start=1):
        lines.insert(insert_at + offset, metadata_line)
    return lines, task_line.strip()


def parse_tasks_with_metadata(lines: List[str], offset: int = 0) -> List[TaskEntry]:
    entries: List[TaskEntry] = []
    current: Optional[TaskEntry] = None

    for index, line in enumerate(lines, start=offset):
        stripped = line.strip()
        if stripped.startswith("- [ ] ") or stripped.startswith("- [x] ") or stripped.startswith("- [-] "):
            if stripped.startswith("- [x] "):
                status = "completed"
            elif stripped.startswith("- [-] "):
                status = "skipped"
            else:
                status = "pending"
            done = status == "completed"
            text = stripped[6:]
            if current is not None:
                current.end_index = index
                entries.append(current)
            current = TaskEntry(start_index=index, end_index=index + 1, text=text, done=done, metadata={}, status=status)
            continue

        if current is not None:
            meta_match = METADATA_LINE_PATTERN.match(line)
            if meta_match:
                key = meta_match.group("key")
                value = meta_match.group("value").strip()
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                current.metadata[key] = value
                current.end_index = index + 1
                continue

        if current is not None and line.strip():
            current.end_index = index
            entries.append(current)
            current = None

    if current is not None:
        entries.append(current)

    return entries


def get_section_task_lines(lines: List[str], section_header: str) -> List[TaskEntry]:
    section_start = find_section(lines, section_header)
    if section_start is None:
        return []
    end = find_section_end(lines, section_start)
    return parse_tasks_with_metadata(lines[section_start:end], offset=section_start)


def resolve_run_target(pending_tasks: List[TaskEntry], target: Optional[str]) -> List[TaskEntry]:
    if not pending_tasks:
        raise ValueError("No hay tareas pendientes para ejecutar.")
    if target is None:
        return [pending_tasks[0]]
    if target.lower() == "all":
        return list(pending_tasks)
    if target.isdigit():
        ordinal = int(target)
        if ordinal < 1 or ordinal > len(pending_tasks):
            raise ValueError(f"Numero de tarea invalido: {ordinal}. Hay {len(pending_tasks)} tareas pendientes.")
        return [pending_tasks[ordinal - 1]]
    if TASK_ID_PATTERN.fullmatch(target):
        match = find_task_by_id(pending_tasks, target)
        if match is None:
            raise ValueError(f"No hay ninguna tarea pendiente con ID {target.upper()}.")
        return [match]
    raise ValueError(f"Formato de #run invalido: {target}")


def parse_prompt(prompt: str) -> Tuple[str, Optional[str], Dict[str, str], Optional[str]]:
    task_match = TASK_PATTERN.match(prompt)
    if task_match:
        task_text = task_match.group(1)
        title, metadata = parse_task_prompt(task_text)
        return "task", title, metadata, None

    run_all_match = RUN_ALL_PATTERN.match(prompt)
    if run_all_match:
        return "run", "all", {}, normalize_task_text(run_all_match.group(1) or "")

    run_match = RUN_PATTERN.match(prompt)
    if run_match:
        return "run", run_match.group(1), {}, normalize_task_text(run_match.group(2) or "")

    done_match = DONE_PATTERN.match(prompt)
    if done_match:
        return "done", done_match.group(1), {}, normalize_task_text(done_match.group(2) or "")

    skip_match = SKIP_PATTERN.match(prompt)
    if skip_match:
        return "skip", skip_match.group(1), {}, normalize_task_text(skip_match.group(2) or "")

    note_match = NOTE_PATTERN.match(prompt)
    if note_match:
        note_text = normalize_task_text(note_match.group(2) or "")
        if not note_text or (note_match.group(1) is None and note_text.isdigit()):
            raise ValueError("La nota necesita texto: '#note [N]: <texto>'.")
        return "note", note_match.group(1), {}, note_text

    raise ValueError(
        "El prompt debe empezar con '#task', '#run', '#run-all', '#done', '#skip' o '#note'."
    )


def update_progress_metadata(lines: List[str], backlog_count: int, run_date: str) -> List[str]:
    updated: List[str] = []
    backlog_updated = False
    last_run_updated = False
    for line in lines:
        if line.startswith("- Backlog activo:"):
            updated.append(f"- Backlog activo: {backlog_count}\n")
            backlog_updated = True
        elif line.startswith("- Ultima ejecucion de `#run`:"):
            updated.append(f"- Ultima ejecucion de `#run`: {run_date}\n")
            last_run_updated = True
        else:
            updated.append(line)
    if not backlog_updated:
        updated.append(f"- Backlog activo: {backlog_count}\n")
    if not last_run_updated:
        updated.append(f"- Ultima ejecucion de `#run`: {run_date}\n")
    return updated


def replace_section(lines: List[str], header: str, body: List[str]) -> List[str]:
    section_start = find_section(lines, header)
    section_lines = [header + "\n", "\n"] + body
    if not body or not body[-1].endswith("\n"):
        section_lines.append("\n")

    if section_start is None:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.extend(section_lines)
        return lines

    section_end = find_section_end(lines, section_start)
    return lines[:section_start] + section_lines + lines[section_end:]


def render_last_session(run_date: str, summary: str, completed_tasks: List[str], pending_tasks: List[TaskEntry]) -> List[str]:
    lines = [
        f"- Fecha: {run_date}\n",
        f"- Que se hizo: {summary or 'Ejecucion de `#run`'}\n",
        "- Tareas completadas:\n",
    ]
    if completed_tasks:
        for text in completed_tasks:
            lines.append(f"  - [x] {text}\n")
    else:
        lines.append("  - [x] <ninguna>\n")
    lines.append("- Tareas pendientes que siguen en `tasks.md`:\n")
    if pending_tasks:
        for entry in pending_tasks:
            lines.append(f"  - [ ] {entry.text}\n")
    else:
        lines.append("  - [ ] <ninguna>\n")
    lines.append("- Por que (si algo se corto por circuit breaker, referenciar el evento en `graph/history/circuit-breaker-events.jsonl`):\n")
    lines.append("  - <detalle>\n")
    return lines


def render_next_session(pending_tasks: List[TaskEntry]) -> List[str]:
    if pending_tasks:
        return [f"- Siguiente foco: `{pending_tasks[0].text}`\n"]
    return ["- Siguiente foco: definir la proxima `#task`\n"]


def append_completed_record(lines: List[str], completed_line: str) -> List[str]:
    section_start = find_section(lines, SECTION_COMPLETED_HEADER)
    if section_start is None:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(SECTION_COMPLETED_HEADER + "\n")
        lines.append("\n")
        lines.append(f"- [x] {completed_line}\n")
        return lines

    insert_at = find_section_end(lines, section_start)
    lines.insert(insert_at, f"- [x] {completed_line}\n")
    return lines


def append_run_history(
    lines: List[str],
    run_target: str,
    completed_tasks: List[str],
    backlog_count: int,
    run_date: str,
    label: str = "Tareas completadas",
    marker: str = "x",
) -> List[str]:
    section_start = find_section(lines, SECTION_HISTORY_HEADER)
    if section_start is None:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(SECTION_HISTORY_HEADER + "\n")
        lines.append("\n")
        section_start = len(lines) - 2

    insert_at = find_section_end(lines, section_start)
    history_entry = [
        f"### {run_date}\n",
        f"- Comando: `{run_target}`\n",
        f"- Backlog restante: {backlog_count}\n",
        f"- {label}:\n",
    ]
    for text in completed_tasks:
        history_entry.append(f"  - [{marker}] {text}\n")
    history_entry.append("\n")
    lines[insert_at:insert_at] = history_entry
    return lines


def append_dependency_stop_history(
    lines: List[str],
    run_target: str,
    error: DependencyBlockedError,
    backlog_count: int,
    run_date: str,
    branch_stop: bool,
) -> List[str]:
    section_start = find_section(lines, SECTION_HISTORY_HEADER)
    if section_start is None:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(SECTION_HISTORY_HEADER + "\n")
        lines.append("\n")
        section_start = len(lines) - 2

    insert_at = find_section_end(lines, section_start)
    scope = "rama de dependencias" if branch_stop else "una tarea"
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    history_entry = [
        f"### {run_date}\n",
        f"- Comando: `{run_target}`\n",
        "- Stop: dependency-block\n",
        f"- Tarea intentada: {error.task}\n",
        f"- Prerrequisito: {error.dependency}\n",
        f"- Estado del prerrequisito: {error.state}\n",
        f"- Motivo: {error}\n",
        f"- Alcance: {scope}\n",
        f"- Timestamp: {timestamp}\n",
        f"- Backlog restante: {backlog_count}\n",
        "\n",
    ]
    lines[insert_at:insert_at] = history_entry
    return lines


def complete_tasks(root: str, run_target: Optional[str], summary: str, command: str = "#run") -> List[str]:
    tasks_path = Path(root) / TASKS_FILE_REL
    progress_path = Path(root) / PROGRESS_FILE_REL
    ensure_file(tasks_path, TASKS_SKELETON)
    ensure_file(progress_path, PROGRESS_SKELETON)

    lines = read_lines(tasks_path)
    pending = [entry for entry in get_section_task_lines(lines, SECTION_PENDING) if not entry.done]
    task_index = build_task_index(lines)
    targets = resolve_run_target(pending, run_target)
    completed_texts: List[str] = []

    for task in targets:
        try:
            validate_task_dependencies(task, task_index)
        except DependencyBlockedError as exc:
            pending_count = len([entry for entry in get_section_task_lines(lines, SECTION_PENDING) if not entry.done])
            progress_lines = read_lines(progress_path)
            run_date = today_iso()
            progress_lines = update_progress_metadata(progress_lines, pending_count, run_date)
            progress_lines = append_dependency_stop_history(
                progress_lines,
                f"{command} {run_target or ''}".strip(),
                exc,
                pending_count,
                run_date,
                len(targets) > 1,
            )
            write_lines(progress_path, progress_lines)
            raise
        line_idx = task.start_index
        lines[line_idx] = lines[line_idx].replace("- [ ]", "- [x]", 1)
        task.status = "completed"
        task.done = True
        task_id_value = task.metadata.get("id", "").upper()
        if task_id_value:
            task_index[task_id_value] = task
        completed_texts.append(task.text)

    for text in completed_texts:
        completed_line = text
        if summary:
            completed_line = f"{text} - {summary}"
        lines = append_completed_record(lines, completed_line)

    write_lines(tasks_path, lines)

    pending_tasks = [entry for entry in get_section_task_lines(lines, SECTION_PENDING) if not entry.done]
    pending_count = len(pending_tasks)
    progress_lines = read_lines(progress_path)
    run_date = today_iso()
    progress_lines = update_progress_metadata(progress_lines, pending_count, run_date)
    progress_lines = append_run_history(progress_lines, f"{command} {run_target or ''}".strip(), completed_texts, pending_count, run_date)
    progress_lines = replace_section(progress_lines, "## Ultima sesion", render_last_session(run_date, summary, completed_texts, pending_tasks))
    progress_lines = replace_section(progress_lines, "## Proxima sesion deberia", render_next_session(pending_tasks))
    write_lines(progress_path, progress_lines)

    return completed_texts


def resolve_single_target(pending_tasks: List[TaskEntry], target: Optional[str], command: str) -> TaskEntry:
    if not pending_tasks:
        raise ValueError(f"No hay tareas pendientes para {command}.")
    if target is None:
        return pending_tasks[0]
    if TASK_ID_PATTERN.fullmatch(target):
        match = find_task_by_id(pending_tasks, target)
        if match is None:
            raise ValueError(f"No hay ninguna tarea pendiente con ID {target.upper()}.")
        return match
    ordinal = int(target)
    if ordinal < 1 or ordinal > len(pending_tasks):
        raise ValueError(f"Numero de tarea invalido: {ordinal}. Hay {len(pending_tasks)} tareas pendientes.")
    return pending_tasks[ordinal - 1]


def append_skipped_record(lines: List[str], entry_lines: List[str]) -> List[str]:
    section_start = find_section(lines, SECTION_SKIPPED_HEADER)
    if section_start is None:
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(SECTION_SKIPPED_HEADER + "\n")
        lines.append("\n")
        lines.extend(entry_lines)
        return lines

    insert_at = find_section_end(lines, section_start)
    lines[insert_at:insert_at] = entry_lines
    return lines


def skip_task(root: str, target: Optional[str], reason: str) -> str:
    tasks_path = Path(root) / TASKS_FILE_REL
    progress_path = Path(root) / PROGRESS_FILE_REL
    ensure_file(tasks_path, TASKS_SKELETON)
    ensure_file(progress_path, PROGRESS_SKELETON)

    lines = read_lines(tasks_path)
    pending = [entry for entry in get_section_task_lines(lines, SECTION_PENDING) if not entry.done]
    task = resolve_single_target(pending, target, "#skip")

    skipped_line = f"- [-] {task.text} - motivo: {reason or 'sin motivo registrado'} ({today_iso()})\n"
    entry_lines = [skipped_line] + format_task_metadata_block(task.metadata)

    del lines[task.start_index:task.end_index]
    lines = append_skipped_record(lines, entry_lines)
    write_lines(tasks_path, lines)

    pending_after = [entry for entry in get_section_task_lines(lines, SECTION_PENDING) if not entry.done]
    run_date = today_iso()
    progress_lines = read_lines(progress_path)
    progress_lines = update_progress_metadata(progress_lines, len(pending_after), run_date)
    progress_lines = append_run_history(
        progress_lines,
        f"#skip {target or ''}".strip(),
        [f"{task.text} - motivo: {reason or 'sin motivo registrado'}"],
        len(pending_after),
        run_date,
        label="Tareas salteadas",
        marker="-",
    )
    write_lines(progress_path, progress_lines)

    return task.text


def add_note(root: str, target: Optional[str], note: str) -> str:
    tasks_path = Path(root) / TASKS_FILE_REL
    ensure_file(tasks_path, TASKS_SKELETON)

    lines = read_lines(tasks_path)
    pending = [entry for entry in get_section_task_lines(lines, SECTION_PENDING) if not entry.done]
    task = resolve_single_target(pending, target, "#note")

    lines.insert(task.end_index, f"    - note: {note} ({today_iso()})\n")
    write_lines(tasks_path, lines)
    return task.text


def create_task(root: str, task_text: str, metadata: Dict[str, str]) -> Tuple[str, Optional[str]]:
    tasks_path = Path(root) / TASKS_FILE_REL
    ensure_file(tasks_path, TASKS_SKELETON)

    lines = read_lines(tasks_path)
    # El ID es la referencia estable de la tarea (no cambia si se completan,
    # saltean o agregan otras antes) - se genera siempre en el servidor, no
    # se toma de metadata del usuario, para garantizar unicidad.
    stable_id = next_stable_task_id(lines)
    metadata_with_id = {"id": stable_id, **{k: v for k, v in metadata.items() if k != "id"}}

    lines, inserted_line = append_pending_task(lines, task_text, metadata_with_id)
    write_lines(tasks_path, lines)

    node_path = create_knowledge_node(root, task_text, metadata_with_id)
    return inserted_line, node_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Gestor prompt-driven de tasks/progress para GRAPH.")
    parser.add_argument("repo_root", nargs="?", default=".", help="Raiz del proyecto con .agents/graph")
    parser.add_argument("prompt", help="Prompt que empieza con #task, #run, #run-all, #done, #skip o #note")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    if not root.is_dir():
        print(f"Error: no existe el directorio {root}", file=sys.stderr)
        return 1

    try:
        action, target, metadata, summary = parse_prompt(args.prompt)
        if action == "task":
            inserted, node_path = create_task(root, target, metadata)
            print(f"Tarea agregada: {inserted}")
            tasks_path = root / TASKS_FILE_REL
            pending = get_section_task_lines(read_lines(tasks_path), SECTION_PENDING)
            created_entry = next((e for e in reversed(pending) if e.text == target.strip() and e.metadata.get("id")), None)
            if created_entry:
                print(f"ID estable: {created_entry.metadata['id']} (referencialo con #run/#done/#skip/#note)")
            if node_path:
                print(f"Nodo de conocimiento creado: {node_path}")
        elif action == "run":
            completed = complete_tasks(root, target, summary or "completada")
            print("Tareas ejecutadas:")
            for text in completed:
                print(f"- {text}")
        elif action == "done":
            completed = complete_tasks(root, target, summary or "marcada como completada", command="#done")
            print("Tareas marcadas como completadas:")
            for text in completed:
                print(f"- {text}")
        elif action == "skip":
            skipped = skip_task(root, target, summary or "")
            print(f"Tarea salteada: {skipped}")
        else:
            noted = add_note(root, target, summary or "")
            print(f"Nota agregada a: {noted}")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
