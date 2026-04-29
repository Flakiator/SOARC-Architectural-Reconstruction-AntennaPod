from collections import defaultdict
import sys
import math
import re
from pathlib import Path
import networkx as nx
import javalang
from pyvis.network import Network
from pydriller import Repository, ModificationType

REPO_DIR = "https://github.com/AntennaPod/AntennaPod"
code_root_folder = "/Users/niklaschristensen/Desktop/antenna/AntennaPod"

# Map file paths to module names based on common Java project structures. And normalize path separators for cross-platform compatibility (i.e Windows fix).
def module_name_from_file_path(full_path):
    # Example: /repo/src/main/java/com/example/App.java -> com.example.App
    normalized_path = str(full_path).replace("\\", "/")
    root_prefix = code_root_folder.rstrip("/") + "/"

    if normalized_path.startswith(root_prefix):
        rel_path = normalized_path[len(root_prefix):]
    else:
        rel_path = normalized_path

    if rel_path.startswith("/"):
        rel_path = rel_path[1:]

    source_roots = [
        "src/main/java/",
        "src/test/java/",
        "app/src/main/java/",
        "app/src/test/java/",
        "java/",
    ]

    for root in source_roots:
        idx = rel_path.find(root)
        if idx != -1:
            rel_path = rel_path[idx + len(root):]
            break

    if rel_path.endswith(".java"):
        rel_path = rel_path[: -len(".java")]

    return rel_path.replace("/", ".")


def normalize_static_import(import_path):
    # Map static member imports to the owning type.
    # com.example.Utils.someMethod -> com.example.Utils
    if import_path.endswith(".*"):
        return import_path[:-2]

    parts = import_path.split(".")
    if len(parts) > 1:
        return ".".join(parts[:-1])
    return import_path


def import_from_line(line):
    match = re.search(r"^\s*import\s+(static\s+)?([A-Za-z_][A-Za-z0-9_\.]*(?:\.\*)?)\s*;", line)
    if not match:
        return None

    is_static = bool(match.group(1))
    import_path = match.group(2)
    is_wildcard = import_path.endswith(".*")

    if is_static:
        import_path = normalize_static_import(import_path)

    return (import_path, is_static, is_wildcard)


def imports_from_file_regex(file_path):
    all_imports = []

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            imp = import_from_line(line)
            if imp:
                all_imports.append(imp)

    return all_imports


def imports_from_file_ast(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        source = f.read()
    try:
        tree = javalang.parse.parse(source)
    except Exception:
        return None

    all_imports = []
    for imp in tree.imports:
        import_path = imp.path
        is_static = bool(imp.static)
        is_wildcard = bool(imp.wildcard)

        if is_static:
            import_path = normalize_static_import(import_path)

        all_imports.append((import_path, is_static, is_wildcard))

    return all_imports


def imports_from_file(file_path):
    # Barebones AST pass: read imports directly from parsed tree.
    ast_imports = imports_from_file_ast(file_path)
    if ast_imports is not None:
        return ast_imports

    return imports_from_file_regex(file_path)


def relevant_module(module_name):
    excluded_segments = {"test", "tests", "androidtest", "androidtests"}
    segments = [segment.lower() for segment in module_name.split(".") if segment]
    return not any(segment in excluded_segments for segment in segments)


def top_level_packages(module_name, depth=1):
    components = module_name.split(".")
    return ".".join(components[:depth]) if len(components) >= depth else module_name


def dependencies_digraph(code_root_folder):
    files = list(Path(code_root_folder).rglob("*.java"))
    graph = nx.DiGraph()
    internal_modules = set()
    # First pass: identify all internal modules to ensure they are included as nodes even if they have no outgoing edges.
    for file in files:
        file_path = str(file)
        source_module = module_name_from_file_path(file_path)
        if not relevant_module(source_module):
            continue
        internal_modules.add(source_module)
    
    for file in files:
        file_path = str(file)
        source_module = module_name_from_file_path(file_path)
        if not relevant_module(source_module):
            continue
        if source_module not in graph.nodes:
            graph.add_node(source_module)

        for target_module, _, is_wildcard in imports_from_file(file_path):
            if is_wildcard:
                continue
            if target_module in internal_modules:
                graph.add_edge(source_module, target_module)

    return graph


def abstracted_to_top_level(graph, depth=1):
    abstract_graph = nx.DiGraph()
    for source, target in graph.edges:
        src = top_level_packages(source, depth)
        dst = top_level_packages(target, depth)

        if src != dst:
            if abstract_graph.has_edge(src, dst):
                abstract_graph[src][dst]["weight"] += 1
            else:
                abstract_graph.add_edge(src, dst, weight=1)
    return abstract_graph


def draw_graph(graph, output_html="no_externals2.html", package_activity=None):
    net = Network(height="900px", width="100%", directed=graph.is_directed())
    net.barnes_hut()

    for node in graph.nodes:
        churn = 0
        if package_activity is not None:
            churn = int(package_activity.get(node, 0))

        churn_scale = math.log2(churn + 1)
        font_size = int(14 + 3.4 * churn_scale)
        min_width = int(80 + 12 * churn_scale)
        box_margin = int(8 + churn_scale)
        net.add_node(
            node,
            label=str(node),
            title=f"{node} | churn: {churn}",
            shape="box",
            value=churn,
            widthConstraint={"minimum": min_width},
            margin={"top": box_margin, "right": box_margin, "bottom": box_margin, "left": box_margin},
            font={"size": font_size, "color": "#111111"},
            color={"background": "#ffffff"},
        )

    for source, target, data in graph.edges(data=True):
        weight = int(data.get("weight", 1))
        net.add_edge(
            source,
            target,
            label=str(weight),
            width=2 * math.log2(weight + 1),  # gentle scaling
            title=f"{source} -> {target}: {weight}",
            font={"size": 50, "color": "#000000", "align": "top"},
        )
    net.show(output_html, notebook=False)
    print(f"Saved interactive graph to {output_html}")

def get_package_activity(depth=2):
    # Only look at default branch, no merges and only .java commits
    repo = Repository(
        code_root_folder,
        only_in_branch="develop",
        only_no_merge=True,
        )
    
    commit_counts = defaultdict(int)

    for commit in repo.traverse_commits():
        for modification in commit.modified_files:
            new_path = modification.new_path
            old_path = modification.old_path

            if modification.change_type == ModificationType.RENAME:
                previous_count = commit_counts.pop(old_path, 0)
                if new_path:
                    commit_counts[new_path] = previous_count + 1
                    
            elif modification.change_type == ModificationType.DELETE:
                if old_path:
                    commit_counts.pop(old_path, None)
                    
            elif modification.change_type == ModificationType.ADD:
                if new_path:
                    commit_counts[new_path] += 1

            else:
                current_path = new_path or old_path
                if current_path:
                    commit_counts[current_path] += 1

    package_activity = defaultdict(int)

    for path, count in commit_counts.items():
        if not path or not str(path).endswith(".java"):
            continue

        full_path = str(Path(code_root_folder) / path)
        grouped_module = top_level_packages(module_name_from_file_path(full_path), depth)
        if grouped_module:
            package_activity[grouped_module] += count

    sorted_sizes = sorted(package_activity.items(), key=lambda x: x[1], reverse=True)
    print(sorted_sizes)
    return package_activity

def main():
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    dg = dependencies_digraph(code_root_folder)
    print(dg.number_of_nodes())
    print(dg.number_of_edges())
    package_activity = get_package_activity(depth)
    ag = abstracted_to_top_level(dg, depth)
    draw_graph(ag, package_activity=package_activity)


if __name__ == "__main__":
    main()
    
# Look at filtering out external dependencies (e.g androidx, java.utils, com.google, etc) and see how that changes the graph.