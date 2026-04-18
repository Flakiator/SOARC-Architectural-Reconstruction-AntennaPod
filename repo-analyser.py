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


def import_from_line(line):
    # Match Java import lines, including static 
    match = re.search(r"^\s*import\s+(?:static\s+)?([A-Za-z_][A-Za-z0-9_\.]*(?:\.\*)?)\s*;", line)
    if not match:
        return None

    return match.group(1)


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

        for each in imports_from_file(file_path):
            G.add_edge(module_name, each)

    return G

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

        for target_module in imports_from_file(file_path):

            G.add_edge(source_module, target_module)
    return G

def draw_graph(G, **args):
    plt.figure(figsize=(16, 12))
    pos = nx.spring_layout(G, seed=42, k=0.3)
    nx.draw_networkx_nodes(G, pos, node_size=45, alpha=0.85)
    nx.draw_networkx_edges(G, pos, alpha=0.25, arrows=G.is_directed(), arrowsize=8)
    nx.draw_networkx_labels(G, pos, font_size=6)
    plt.show()
DG = dependencies_digraph(code_root_folder)
draw_graph(DG)
print(DG.number_of_nodes())
print(DG.number_of_edges())
