# Houdini Python Code Editor

A VS Code-inspired Python code editor for writing and executing Houdini-specific Python code directly within Houdini. This panel provides a comfortable coding environment for Houdini technical artists and TDs.

![code](https://github.com/user-attachments/assets/ad4c38a9-1bcc-475e-a7b1-fc2ffd91e837)

## Overview

This tool provides a dedicated environment for writing Python code that interacts with Houdini. It allows you to write, test, and execute Python scripts that manipulate Houdini scenes, nodes, and parameters without leaving the Houdini interface.

## Features

- **Python Code Editor**: Write Houdini Python code with syntax highlighting in a dark theme environment
- **Immediate Execution**: Run your Houdini Python code instantly with Ctrl+Enter
- **Houdini Integration**: Direct access to the `hou` module and Houdini objects
- **Code Completion**: Suggestions for Python keywords and Houdini-specific objects and methods
- **Output Console**: View execution results, print statements, and errors
- **Multiple Files**: Work with multiple scripts through the tabbed interface
- **File Management**: Open, save, and autosave your Houdini Python scripts
- **Editor Features**: Line numbers, bracket matching, syntax highlighting, and find/replace

## Usage

### Working with Houdini Python

```python
# Example: Create a sphere in Houdini
node = hou.node('/obj').createNode('geo', 'my_sphere')
sphere = node.createNode('sphere')
sphere.parm('radx').set(2.0)
```

### Editor Controls

- **Run Code**: Press Ctrl+Enter or click the Play button to execute your code in Houdini
- **File Operations**: Open, save, and create new Python script tabs
- **Find/Replace**: Press Ctrl+F to toggle the find/replace panel
- **Clear Output**: Clear the output console to remove previous execution results

### Auto-completion

The editor provides intelligent code completion for:
- Python keywords and functions
- Houdini-specific modules (hou, node, parm, etc.)
- Object methods based on context

## Autosave

Your work is automatically saved every 30 seconds if changes are detected, helping prevent loss of work.

## Requirements

- Houdini (this is a Houdini panel and requires Houdini to run)
- PySide2 (included with Houdini)

## Customization

You can modify the source code to adjust:
- Editor appearance
- Syntax highlighting colors
- Autosave behavior

## License

[MIT License](LICENSE)
