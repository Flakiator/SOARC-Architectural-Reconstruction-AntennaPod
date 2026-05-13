# SOARC-Architectural-Reconstruction-AntennaPod
# How to run
Make sure to have the desired java repository cloned to your machine and check that the `code_root_folder` in `arch_recovery.py` aligns with the path to where you have the repo stored on your machine.

run the program with:
`python arch_recovery.py <max_abstraction_depth>`

Try out different integer values for `max_abstraction_depth` to get a view that suits your system.

## Beware!
The getting the churn score/package_activity can take a long time to run (more than 3 minutes) depending on the size and lifetime of the project so to make testing different abstraction depths faster, commment out line 302:
`package_activity = get_package_activity(depth)`
# Cloc output
![alt text](images/cloc_output.png)

# Naive view (all files with all depndencies)
![alt text](images/initial_naive_view.png)

# Filtered tests, external dependencies and AST parsing
![alt text](images/no_external_dependencies_simple_view.png)

# Initial abstacted module view
![alt text](images/abstract_simple.png)

# Abstacted module view with weight scaled edges and churn scaled nodes
![alt text](images/abstract_scaled.png)

# Prefix stripped modules and filtered weak dependencies
![alt text](images/stripped_prefixes.png)

# Bubble diagram from gittruck (green instensity: churn, node-size: file size)
![alt text](images/bubble_truck.png)

# Gradle dependency view generated with plugin
https://github.com/vanniktech/gradle-dependency-graph-generator-plugin
![alt text](images/GRADLE_generated_dependencies.png)
