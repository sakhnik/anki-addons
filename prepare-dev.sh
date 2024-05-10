#!/bin/bash -e

virtualenv /tmp/venv
source /tmp/venv/bin/activate
pip install mypy aqt 'python-lsp-server[all]'
