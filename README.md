# Houdini Python Panel

A VS Code-like Python editing and execution panel for Houdini, featuring syntax highlighting, code completion, and a clean dark theme interface.

(https://github.com/user-attachments/assets/90b7f907-da37-4e7b-95d4-0e953a7b7323)
)




## Features

- **Code Editor with Syntax Highlighting**: Python code highlighting with Monokai-inspired dark theme
- **Line Numbers**: Visual indication of line position in code
- **Auto-completion**: Context-aware code completion for Python and Houdini-specific objects
- **Bracket Matching**: Highlights matching brackets for better code navigation
- **File Management**: Open, save, and autosave capabilities
- **Tab System**: Multiple files open simultaneously with tabbed interface
- **Find & Replace**: Search through your code with Ctrl+F
- **Output Console**: View execution results and errors
- **Run Code**: Execute Python code directly in Houdini with Ctrl+Enter
- **Drag & Drop**: Support for dragging .py files into the editor

## Usage

### Basic Operation

- **Run Code**: Press Ctrl+Enter or click the Play button
- **New Tab**: Create a new editor tab
- **Open File**: Load a Python file into the editor
- **Save File**: Save your current work
- **Find/Replace**: Press Ctrl+F to toggle the find/replace panel
- **Clear Output**: Clear the output console

### Auto-completion

The panel provides completion suggestions for:
- Python keywords
- Common Houdini modules (hou, node, parm, etc.)
- Object properties and methods based on context

### Keyboard Shortcuts

- **Ctrl+Enter**: Execute code
- **Ctrl+F**: Toggle find/replace panel
- **Ctrl+S**: Save file (implied, not explicitly defined in code)

## Autosave

The panel automatically saves your work every 30 seconds if changes are detected. This helps prevent loss of work in case of unexpected issues.

## Customization

You can modify the source code to customize aspects like:
- Syntax highlighting colors
- Default editor font
- Theme colors
- Autosave interval

## Requirements

- Houdini (tested with Houdini 20.x)
- PySide2 (included with Houdini)

## Development

To contribute to this project:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

[MIT License](LICENSE)

## Acknowledgments

- Inspired by the VS Code interface
- Built on PySide2/Qt for UI components
