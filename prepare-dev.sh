#!/bin/bash -e

virtualenv venv
source venv/bin/activate
pip install mypy aqt 'python-language-server[all]'
