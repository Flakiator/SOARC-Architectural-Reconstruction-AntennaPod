import sys
import os
import pathlib
import re
import jast
from pathlib import Path
import networkx as nx
from pyvis.network import Network
import matplotlib.pyplot as plt
# Get curent working directory
#print(os.getcwd())
code_root_folder = "/Users/niklaschristensen/Desktop/antenna"
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


def normalize_static_import(import_path):
    # Map static member imports to the owning type.
    # Example: com.example.Utils.someMethod -> com.example.Utils
    if import_path.endswith(".*"):
        return import_path[:-2]

    parts = import_path.split(".")
    if len(parts) > 1:
        return ".".join(parts[:-1])
    return import_path


def import_from_line(line):
    # Match Java import lines, including static 
    match = re.search(r"^\s*import\s+(static\s+)?([A-Za-z_][A-Za-z0-9_\.]*(?:\.\*)?)\s*;", line)
    if not match:
        return None

    is_static = bool(match.group(1))
    import_path = match.group(2)
    is_wildcard = import_path.endswith(".*")

    if is_static:
        import_path = normalize_static_import(import_path)

    return (import_path, is_static, is_wildcard)


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

def relevant_module(module_name): 
    # Exclude only explicit test package segments (e.g. .test. or .tests.).
    excluded_segments = {"test", "tests", "androidtest", "androidtests"}
    segments = [segment.lower() for segment in module_name.split(".") if segment]
    return not any(segment in excluded_segments for segment in segments)

def dependencies_graph(code_root_folder):
    files = Path(code_root_folder).rglob("*.java")

    G = nx.Graph()

    for file in files:
        file_path = str(file)

        module_name = module_name_from_file_path(file_path)

        if module_name not in G.nodes:
            G.add_node(module_name)

        for target_module, _, is_wildcard in imports_from_file(file_path):
            if is_wildcard:
                continue
            G.add_edge(module_name, target_module)

    return G

def top_level_packages(module_name, depth=1):
    components = module_name.split(".")
    return ".".join(components[:depth]) if len(components) >= depth else module_name

def dependencies_digraph(code_root_folder):
    files = Path(code_root_folder).rglob("*.java")

    G = nx.DiGraph()

    for file in files:
        file_path = str(file)

        source_module = module_name_from_file_path(file_path)
        if not relevant_module(source_module):
          continue
        if source_module not in G.nodes:
            G.add_node(source_module)

        for target_module, _, is_wildcard in imports_from_file(file_path):
            if is_wildcard:
                continue
            G.add_edge(source_module, target_module)
    return G

def abstracted_to_top_level(G, depth=1):
    aG = nx.DiGraph()
    for source, target in G.edges:
        src = top_level_packages(source, depth)
        dst = top_level_packages(target, depth)

        if src != dst:
            aG.add_edge(src, dst)
    return aG

def draw_graph(G, **args):
    plt.figure(figsize=(16, 12))
    pos = nx.spring_layout(G, seed=42, k=0.3)
    nx.draw_networkx_nodes(G, pos, node_size=45, alpha=0.85)
    nx.draw_networkx_edges(G, pos, alpha=0.25, arrows=G.is_directed(), arrowsize=8)
    nx.draw_networkx_labels(G, pos, font_size=6)
    plt.show()
dG = dependencies_digraph(code_root_folder)
print(dG.number_of_nodes())
print(dG.number_of_edges())
aG = abstracted_to_top_level(dG, depth=3)
draw_graph(aG)