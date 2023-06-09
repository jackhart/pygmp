import os
import sys
from dataclasses import is_dataclass

sys.path.insert(0, os.path.abspath('..'))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'pygmp'
copyright = '2023, Jack Hart'
author = 'Jack Hart'
release = '0.0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon']
napoleon_attr_annotations = True

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------

html_theme = 'furo'
html_title = 'pygmp'
html_static_path = ['_static']

autodoc_typehints = "description"
autodoc_class_signature = "separated"
autoclass_content = "class"


def skip(app, what, name, obj, would_skip, options):
    if name == "__init__":
        return True
    return would_skip


def setup(app):
    print("setup is run")
    app.connect("autodoc-skip-member", skip)

html_theme_options = {
    "announcement": "<b>This project is under active development. The API is subject to change.</b>",
    "source_repository": "https://github.com/jackhart/pygmp",
    "source_branch": "main",
    "source_directory": "docs/"
}