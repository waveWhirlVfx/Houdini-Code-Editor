import hou
import os
import sys
import io
import textwrap
import traceback
import code
from PySide2 import QtCore, QtWidgets, QtGui

class LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor):
        super(LineNumberArea, self).__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QtCore.QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class PythonCodeEditor(QtWidgets.QPlainTextEdit):
    run_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super(PythonCodeEditor, self).__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        
        self.setStyleSheet("background-color: #272822; color: #f8f8f2;")
        
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    def lineNumberAreaWidth(self):
        digits = len(str(self.blockCount()))
        space = 3 + self.fontMetrics().width('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super(PythonCodeEditor, self).resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QtCore.QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QtGui.QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QtGui.QColor("#3e3d32"))
        
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QtGui.QColor("#75715e"))
                painter.drawText(0, top, self.lineNumberArea.width()-2, self.fontMetrics().height(),
                                 QtCore.Qt.AlignRight, number)
            
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()
            lineColor = QtGui.QColor("#49483e")
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def keyPressEvent(self, event):
        # Check for Ctrl+Enter
        if event.key() == QtCore.Qt.Key_Return and (event.modifiers() & QtCore.Qt.ControlModifier):
            self.run_requested.emit()
        else:
            super().keyPressEvent(event)

class OutputConsole(QtWidgets.QTextEdit):
    def __init__(self, parent=None):
        super(OutputConsole, self).__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            background-color: #1e1e1e; 
            color: #e6e6e6; 
            font-family: Consolas, monospace;
            border: 1px solid #333;
            padding: 5px;
        """)

    def write(self, text):
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(text + '\n')
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

class VSCodeLikePanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(VSCodeLikePanel, self).__init__(parent)
        self.setWindowTitle("Houdini Python Panel")
        self.resize(1200, 900)
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #f8f8f2; font-family: Consolas, monospace; }
            QPushButton { background-color: #444444; border: 1px solid #555555; padding: 5px; color: #f8f8f2; }
            QPushButton:hover { background-color: #555555; }
            QLineEdit { background-color: #3c3c3c; border: 1px solid #555555; padding: 3px; color: #f8f8f2; }
        """)

        # Create custom editor that emits run signal and has line numbers
        self.editor = PythonCodeEditor()
        
        # Create output console
        self.output_console = OutputConsole()

        # Connect Ctrl+Enter to run method
        self.editor.run_requested.connect(self.run_code)

        # Buttons
        self.run_button = QtWidgets.QPushButton("Run (Ctrl+Enter)")
        self.run_button.clicked.connect(self.run_code)

        self.clear_output_button = QtWidgets.QPushButton("Clear Output")
        self.clear_output_button.clicked.connect(self.clear_output)

        self.open_button = QtWidgets.QPushButton("Open")
        self.open_button.clicked.connect(self.open_file)

        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self.save_file)

        # Button layout
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.clear_output_button)
        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.save_button)

        # Split the main layout to include editor and output console
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.output_console)
        
        # Set initial sizes for splitter
        splitter.setSizes([700, 300])

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(button_layout)
        layout.addWidget(splitter)
        self.setLayout(layout)
        
        self.current_file = None

    def run_code(self):
        # Clear previous output
        self.output_console.clear()

        # Create a custom stream that writes to both the capture buffer and the output console
        class MultiWriter:
            def __init__(self, output_console):
                self.console = output_console
                self.buffer = io.StringIO()

            def write(self, text):
                self.buffer.write(text)
                self.console.write(text)

            def flush(self):
                self.buffer.flush()

        # Redirect stdout and stderr
        old_stdout, old_stderr = sys.stdout, sys.stderr
        multi_stdout = MultiWriter(self.output_console)
        sys.stdout = multi_stdout
        sys.stderr = multi_stdout

        try:
            # Get the code to run
            code_text = self.editor.toPlainText().strip()

            # Create a custom interpreter
            interpreter = code.InteractiveInterpreter(globals())

            # Special handling for simple expressions
            try:
                # Try to evaluate the expression
                result = eval(code_text)
                # If successful, print the result
                print(result)
            except (SyntaxError, TypeError):
                # If not a simple expression, try to execute as code
                interpreter.runcode(compile(code_text, '<string>', 'exec'))

        except Exception as e:
            # Display any execution errors
            traceback_str = traceback.format_exc()
            self.output_console.write(f"[ERROR]\n{traceback_str}")
        
        finally:
            # Restore original stdout and stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def clear_output(self):
        self.output_console.clear()

    def open_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Python File", "", "Python Files (*.py);;All Files (*)")
        if filename:
            with open(filename, 'r') as f:
                self.editor.setPlainText(f.read())
            self.current_file = filename
            self.output_console.write(f"[INFO] Opened file: {filename}")

    def save_file(self):
        if not self.current_file:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Python File", "", "Python Files (*.py);;All Files (*)")
            if filename:
                self.current_file = filename
        
        if self.current_file:
            with open(self.current_file, 'w') as f:
                f.write(self.editor.toPlainText())
            self.output_console.write(f"[INFO] Saved file: {self.current_file}")

_instance = None

def createInterface():
    global _instance
    if _instance is None:
        _instance = VSCodeLikePanel()
    return _instance

def destroyInterface():
    global _instance
    if _instance is not None:
        _instance.deleteLater()
        _instance = None