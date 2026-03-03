"""
OpenPipeFlow — PyInstaller build script.

Usage (from the openpipeflow/ root):
    python build/build_exe.py

Output: dist/OpenPipeFlow.exe (~80-130 MB)
Runs on Windows 10/11 x64 with no Python installation.
"""

import os
import sys

# Ensure we run from the project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

import PyInstaller.__main__

PyInstaller.__main__.run([
    "main.py",
    "--onefile",
    "--windowed",                   # no console window
    "--name=OpenPipeFlow",
    # "--icon=resources/icons/app.ico",  # uncomment once icon exists
    "--add-data=resources;resources",

    # pandapipes hidden imports
    "--hidden-import=pandapipes",
    "--hidden-import=pandapipes.networks",
    "--hidden-import=pandapipes.component_models",
    "--hidden-import=pandapipes.component_models.fluid_models",
    "--hidden-import=pandapipes.properties",
    "--hidden-import=pandapipes.properties.fluids",
    "--hidden-import=pandapipes.pipeflow_setup",
    "--hidden-import=pandapipes.pf_variables",

    # scipy/numpy hidden imports
    "--hidden-import=scipy.sparse.linalg",
    "--hidden-import=scipy._lib.messagestream",
    "--hidden-import=scipy.sparse._sparsetools",
    "--hidden-import=scipy.special._ufuncs_cxx",
    "--hidden-import=scipy.linalg.blas",
    "--hidden-import=numpy",
    "--hidden-import=numpy.core",

    # PyQt6
    "--hidden-import=PyQt6",
    "--hidden-import=PyQt6.QtCore",
    "--hidden-import=PyQt6.QtGui",
    "--hidden-import=PyQt6.QtWidgets",

    "--collect-all=pandapipes",
    "--collect-all=pandapower",   # pandapipes depends on pandapower

    "--clean",
    "--noconfirm",
])
