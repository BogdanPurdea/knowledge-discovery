# JIRA Formal Concept Analysis (FCA) Project

## Dataset
Link: https://zenodo.org/records/14253918
DOI: https://doi.org/10.5281/zenodo.14253918


## Contents

### mongo_export_filtered/: Contains filtered collections by year 2024 in .json format. Larger than Github's recommended max size, so the directory is not included in the repository. 

### data_extraction/
*   `build_issues.py`: Python script to parse and filter `issues_2024.json` and save the new dataset in `issues.csv`.

### data_analysis/
*   `data_analysis.ipynb`: Jupyter notebook for visualizing dataset distributions.
*   `multi_plots/`: Saved distributions diagrams.

### scaling/
*   `issues.csx`: Scales saved from Elba.
*   `issues.sql`: SQL database table setup used as input for Elba.
*   `scale_diagrams/`: Exported scale diagrams from Elba.
*   `scale_combinations/`: Exported nested diagrams from ToscanaJ.

### attribute_exploration/
*   `extract_kafka_cxt.py`: Script to generate the dyadic context in `kafka_context.cxt`.
*   `kafka_concept_lattice.json`: Concept lattice exported from FCA Tools Bundle.

### triadic/
*   `build_triadic_context.py`: Build a new context using the same scales from `./scaling/issues.csx` and outputs the triadic context in `project_triadic_context.csv`.
*   `mine_triadic_rules.py`: CLI script to mine conditional implications and partial association rules and optionally save in JSON format (`project_triconcepts.json`).

### temporal/
*   `extract_tca_dataset.py`: Creates status transition dataset for KAFKA issues from events and issues collections. Outputs results in `tca_dataset.csv`.
*   `tca_dataset.sql`: SQL database schema for JIRA granules. Used as input for Elba.
*   `tca_context.csx`: Elba scale file for JIRA TCA.
*   `scale_tca_context.py`: Uses `tca_context.csx` to scale `tca_dataset.csv` into `tca_scaled_context.csv`.
*   `extract_tca_transitions.py`: Computes the state-transitions from the `tca_scaled_context.csv` context into `tca_state_transitions.json` and builds the Graphviz DOT file `tca_transition_graph.dot`.
*   `tca_transition_graph.png`: Diagram of transition graph.
*   `transition_ord.png`: Transition ordinal scale image.
*   `dot -Tpdf tca_transition_graph.dot -o transition_graph.pdf`: Console command to convert the transition graph from DOT to PDF.
### Utilities
*   `csv_to_sql.py`: Python script to convert from CSV to SQL.
