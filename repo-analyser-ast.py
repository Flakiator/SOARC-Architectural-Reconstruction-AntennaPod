import re
from pathlib import Path
import javalang
import networkx as nx
import matplotlib.pyplot as plt
# Get curent working directory
#print(os.getcwd())
code_root_folder = "/Users/niklaschristensen/Desktop/antenna"

class JavaFileDeps:
    def __init__(self, module_name, package_name, imports, type_refs):
        self.module_name = module_name
        self.package_name = package_name
        self.imports = imports
        self.type_refs = type_refs

def file_path(file_name):
    return code_root_folder+file_name

def module_name_from_file_path(full_path):
    # Example: /repo/src/main/java/com/example/App.java -> com.example.App

    rel_path = full_path[len(code_root_folder):]
    if rel_path.startswith("/"):
        rel_path = rel_path[1:]
    # Define common Java source root directories to strip from the path
    source_roots = [
        "src/main/java/",
        "src/test/java/",
        "app/src/main/java/",
        "app/src/test/java/",
        "java/"
    ]
    # Remove the source root prefix to get the package path
    for root in source_roots:
        idx = rel_path.find(root)
        if idx != -1:
            rel_path = rel_path[idx + len(root):]
            break
    # Cut off the .java extension
    if rel_path.endswith(".java"):
        rel_path = rel_path[:-len(".java")]

    return rel_path.replace("/", ".")


def import_from_line(line):
    # Match Java import lines, including static 
    match = re.search(r"^\s*import\s+(static\s+)?([A-Za-z_][A-Za-z0-9_\.]*(?:\.\*)?)\s*;", line)
    if not match:
        return None

    path = match.group(2)
    is_static = bool(match.group(1))
    is_wildcard = path.endswith(".*")
    path = normalize_import_path(path, is_static, is_wildcard)

    return (path, is_static, is_wildcard)


# Extract all imported modules/types from a Java source file.
def imports_from_file(file):

    all_imports = []
    
    with open(file, "r", encoding="utf-8", errors="ignore") as f:
        lines = [line for line in f]

    for line in lines:
        imp = import_from_line(line)

        if imp:
            all_imports.append(imp)

    return all_imports

# use ast parsing to get more accurate dependencies
def parse_with_ast(file_path, module_name):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        source_text = f.read()
        try:
            tree = javalang.parse.parse(source_text)
        except Exception:
            return None

        package_name = tree.package.name if tree.package else None
        imports = [
            (normalize_import_path(imp.path, imp.static, imp.wildcard), imp.static, imp.wildcard)
            for imp in tree.imports
        ]

        type_refs = set()

        for _, node in tree.filter(javalang.tree.ReferenceType):
            if node.name:
                type_refs.add(node.name)

        for _, node in tree.filter(javalang.tree.Annotation):
            if node.name:
                type_refs.add(node.name)

        for _, node in tree.filter(javalang.tree.ClassCreator):
            if node.type and getattr(node.type, "name", None):
                type_refs.add(node.type.name)

        return JavaFileDeps(module_name, package_name, imports, type_refs)

def relevant_module(module_name): 
    # Exclude only explicit test package segments (e.g. .test. or .tests.).
    excluded_segments = {"test", "tests", "androidtest", "androidtests"}
    segments = [segment.lower() for segment in module_name.split(".") if segment]
    return not any(segment in excluded_segments for segment in segments)

def normalize_static_import(import_path):
    # For static imports, we want to keep the class name but ignore the member.
    # Example: import static com.example.Utils.someMethod; -> com.example.Utils
    if import_path.endswith(".*"):
        return import_path[:-2]
    else:
        parts = import_path.split(".")
        if len(parts) > 1:
            return ".".join(parts[:-1])
        else:
            return import_path

def normalize_import_path(path, is_static, is_wildcard):
    # Keep wildcard paths without trailing .* for consistent AST/regex behavior.
    normalized = path[:-2] if is_wildcard and path.endswith(".*") else path

    # For non-static imports, we want to keep the full path as it is.
    if not is_static:
        return normalized
    
    # For static imports, we want to normalize to the class level, ignoring specific members.
    if is_wildcard:
        return normalized
    return normalize_static_import(normalized)
        
def resolve_name(raw_name, file_deps, all_internal_modules):
    if not raw_name:
        return None
    # Strip wildcards
    name = raw_name[:-2] if raw_name.endswith(".*") else raw_name

    # Already fully qualified and internal.
    if name in all_internal_modules:
        return name

    # Check non-wildcard imports first.
    for import_path, _, is_wildcard in file_deps.imports:
        if is_wildcard:
            continue

        if import_path.split(".")[-1] == name and import_path in all_internal_modules:
            return import_path

    # Same-package reference.
    if file_deps.package_name:
        same_package_candidate = f"{file_deps.package_name}.{name}"
        if same_package_candidate in all_internal_modules:
            return same_package_candidate

    # Wildcard imports.
    for import_path, is_static, is_wildcard in file_deps.imports:
        if not is_wildcard or is_static:
            continue

        wildcard_candidate = f"{import_path}.{name}"
        if wildcard_candidate in all_internal_modules:
            return wildcard_candidate
        
    return None


def dependencies_digraph(code_root_folder, include_external=False):
    files = Path(code_root_folder).rglob("*.java")

    G = nx.DiGraph()
    parsed_files = []
    internal_modules = set()

    for file in files:
        file_path = str(file)
        source_module = module_name_from_file_path(file_path)
        # Skip test related modules
        if not relevant_module(source_module):
          continue
        # parse with ast
        file_deps = parse_with_ast(file_path, source_module)
        if file_deps is None:
            # Fall back to regex import parsing if AST parse fails.
            file_deps = JavaFileDeps(source_module, None, imports_from_file(file_path), set())
        parsed_files.append(file_deps)
        internal_modules.add(source_module)
            
    # Add the source module as a node in the graph if it doesn't exist
    for file_dep in parsed_files:
        source_module = file_dep.module_name
        if source_module not in G.nodes:
            G.add_node(source_module)
        # Resolve imports
        for import_path, _, is_wildcard in file_dep.imports:
            if is_wildcard:
                continue
            resolved = resolve_name(import_path.split(".")[-1], file_dep, internal_modules)
            # Avoid self loops 
            if resolved != source_module and resolved:
                G.add_edge(source_module, resolved)
            elif include_external:
                G.add_edge(source_module, import_path)
        
        # Resolve AST type references
        for type_ref in file_deps.type_refs:
            resolved = resolve_name(type_ref, file_deps, internal_modules)
            if resolved and resolved != source_module:
                G.add_edge(source_module, resolved)
    return G

def draw_graph(G, **args):
    plt.figure(figsize=(16, 12))
    pos = nx.spring_layout(G, seed=42, k=0.3)
    nx.draw_networkx_nodes(G, pos, node_size=45, alpha=0.85)
    nx.draw_networkx_edges(G, pos, alpha=0.25, arrows=G.is_directed(), arrowsize=8)
    nx.draw_networkx_labels(G, pos, font_size=6)
    plt.show()
DG = dependencies_digraph(code_root_folder, True)
print(DG.number_of_nodes())
print(DG.number_of_edges())
draw_graph(DG)