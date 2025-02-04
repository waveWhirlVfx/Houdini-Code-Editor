import hou
import os
import sys
import io
import time
import traceback
import code
from PySide2 import QtCore, QtWidgets, QtGui

# -------------------------------
# Syntax Highlighting
# -------------------------------
class PythonHighlighter(QtGui.QSyntaxHighlighter):
    def __init__(self, document):
        super(PythonHighlighter, self).__init__(document)
        self.highlightingRules = []

        # Keywords
        keywordFormat = QtGui.QTextCharFormat()
        keywordFormat.setForeground(QtGui.QColor("#66d9ef"))
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del", "elif",
            "else", "except", "False", "finally", "for", "from", "global", "if",
            "import", "in", "is", "lambda", "None", "nonlocal", "not", "or", "pass",
            "raise", "return", "True", "try", "while", "with", "yield"
        ]
        for word in keywords:
            pattern = QtCore.QRegExp(r'\b' + word + r'\b')
            self.highlightingRules.append((pattern, keywordFormat))

        # Strings
        stringFormat = QtGui.QTextCharFormat()
        stringFormat.setForeground(QtGui.QColor("#e6db74"))
        self.highlightingRules.append((QtCore.QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), stringFormat))
        self.highlightingRules.append((QtCore.QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), stringFormat))

        # Comments
        commentFormat = QtGui.QTextCharFormat()
        commentFormat.setForeground(QtGui.QColor("#75715e"))
        self.highlightingRules.append((QtCore.QRegExp(r"#[^\n]*"), commentFormat))

    def highlightBlock(self, text):
        for pattern, fmt in self.highlightingRules:
            index = pattern.indexIn(text)
            while index >= 0:
                length = pattern.matchedLength()
                self.setFormat(index, length, fmt)
                index = pattern.indexIn(text, index + length)

# -------------------------------
# Line Number Area
# -------------------------------
class LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor):
        super(LineNumberArea, self).__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QtCore.QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

# -------------------------------
# Python Code Editor with Enhancements
# -------------------------------
class PythonCodeEditor(QtWidgets.QPlainTextEdit):
    run_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super(PythonCodeEditor, self).__init__(parent)
        self.setAcceptDrops(True)
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)

        # Set base style and highlighter
        self.setStyleSheet("background-color: #272822; color: #f8f8f2;")
        PythonHighlighter(self.document())

        # Code completion
        self.completion_prefix = ''
        keywords = [
            "and", "as", "assert", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "False", "finally", "for", "from", "global",
            "if", "import", "in", "is", "lambda", "None", "nonlocal", "not", "or",
            "pass", "raise", "return", "True", "try", "while", "with", "yield",
            # Sample Houdini module names:
            "hou", "node", "parm", "geometry", "obj", "sop"
        ]
        self.completer = QtWidgets.QCompleter(keywords, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self.completer.activated.connect(self.insertCompletion)

        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    # --- Drag & Drop ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().endswith('.py'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            if filepath.endswith('.py'):
                with open(filepath, 'r') as f:
                    self.setPlainText(f.read())
                # Emit info to the parent console if needed.
        event.acceptProposedAction()

    # --- Line Numbers ---
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
                painter.drawText(0, top, self.lineNumberArea.width()-2,
                                 self.fontMetrics().height(), QtCore.Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    # --- Current Line & Bracket Matching ---
    def highlightCurrentLine(self):
        extraSelections = []

        # Current line highlight
        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()
            lineColor = QtGui.QColor("#49483e")
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)

        # Bracket matching
        cursor = self.textCursor()
        prev_char = self.document().characterAt(cursor.position() - 1)
        next_char = self.document().characterAt(cursor.position())
        bracket_positions = []
        for char, pos in ((prev_char, cursor.position()-1), (next_char, cursor.position())):
            if char in "([{":
                match = self.findMatchingBracket(pos, forward=True)
                if match is not None:
                    bracket_positions.append(pos)
                    bracket_positions.append(match)
            elif char in ")]}":
                match = self.findMatchingBracket(pos, forward=False)
                if match is not None:
                    bracket_positions.append(pos)
                    bracket_positions.append(match)
        for pos in bracket_positions:
            sel = QtWidgets.QTextEdit.ExtraSelection()
            fmt = QtGui.QTextCharFormat()
            fmt.setBackground(QtGui.QColor("#3e3d3e"))
            sel.format = fmt
            sel.cursor = self.textCursor()
            sel.cursor.setPosition(pos)
            sel.cursor.movePosition(QtGui.QTextCursor.NextCharacter, QtGui.QTextCursor.KeepAnchor)
            extraSelections.append(sel)

        self.setExtraSelections(extraSelections)

    def findMatchingBracket(self, pos, forward=True):
        text = self.toPlainText()
        brackets = {"(":")", "[":"]", "{":"}", ")":"(", "]":"[", "}":"{"}
        current = text[pos]
        match = brackets.get(current)
        if not match:
            return None
        depth = 0
        if forward:
            for i in range(pos, len(text)):
                if text[i] == current:
                    depth += 1
                elif text[i] == match:
                    depth -= 1
                    if depth == 0:
                        return i
        else:
            for i in range(pos, -1, -1):
                if text[i] == current:
                    depth += 1
                elif text[i] == match:
                    depth -= 1
                    if depth == 0:
                        return i
        return None

    # --- Code Completion ---
    def insertCompletion(self, completion):
        tc = self.textCursor()
        extra = len(completion) - len(self.completion_prefix)
        tc.movePosition(QtGui.QTextCursor.Left, QtGui.QTextCursor.KeepAnchor, len(self.completion_prefix))
        tc.insertText(completion)
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QtGui.QTextCursor.WordUnderCursor)
        return tc.selectedText()

    # --- Auto-Indentation and Key Handling ---
    def keyPressEvent(self, event):
        # Check for Ctrl+Enter to run code
        if event.key() == QtCore.Qt.Key_Return and (event.modifiers() & QtCore.Qt.ControlModifier):
            self.run_requested.emit()
            return

        # Auto-completion trigger (if the completion popup is visible, let it handle navigation)
        if self.completer.popup() and self.completer.popup().isVisible():
            if event.key() in (QtCore.Qt.Key_Enter, QtCore.Qt.Key_Return, QtCore.Qt.Key_Escape,
                               QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab):
                event.ignore()
                return

        super(PythonCodeEditor, self).keyPressEvent(event)

        # Auto-indent if Return is pressed
        if event.key() == QtCore.Qt.Key_Return:
            cursor = self.textCursor()
            blockText = cursor.block().previous().text()
            indent = ""
            for ch in blockText:
                if ch in " \t":
                    indent += ch
                else:
                    break
            cursor.insertText(indent)
            self.setTextCursor(cursor)

        # Handle completion: show the completer when a dot or a letter is typed
        completionPrefix = self.textUnderCursor()
        if len(completionPrefix) >= 1:
            self.completion_prefix = completionPrefix
            self.completer.setCompletionPrefix(completionPrefix)
            cr = self.cursorRect()
            cr.setWidth(self.completer.popup().sizeHintForColumn(0)
                        + self.completer.popup().verticalScrollBar().sizeHint().width())
            self.completer.complete(cr)
        else:
            self.completer.popup().hide()

# -------------------------------
# Output Console
# -------------------------------
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

# -------------------------------
# Main Panel with Tabs, Find/Replace, Themes, Autosave, etc.
# -------------------------------
class VSCodeLikePanel(QtWidgets.QWidget):
    AUTOSAVE_INTERVAL = 30000  # 30 seconds

    def __init__(self, parent=None):
        super(VSCodeLikePanel, self).__init__(parent)
        self.setWindowTitle("Houdini Python Panel")
        self.resize(1200, 900)
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #f8f8f2; font-family: Consolas, monospace; }
            QPushButton { background-color: #444444; border: 1px solid #555555; padding: 5px; color: #f8f8f2; }
            QPushButton:hover { background-color: #555555; }
            QLineEdit { background-color: #3c3c3c; border: 1px solid #555555; padding: 3px; color: #f8f8f2; }
            QTabWidget::pane { border: 1px solid #555555; }
        """)

        # Initialize recent files list and file history
        self.recent_files = []
        self.file_history = {}

        # Create Tab Widget for multiple editors
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.closeTab)
        self.newTab()  # Start with one tab

        # Create output console
        self.output_console = OutputConsole()

        # Buttons
        self.run_button = QtWidgets.QPushButton("Run (Ctrl+Enter)")
        self.run_button.clicked.connect(self.run_code)

        self.clear_output_button = QtWidgets.QPushButton("Clear Output")
        self.clear_output_button.clicked.connect(self.clear_output)

        self.open_button = QtWidgets.QPushButton("Open")
        self.open_button.clicked.connect(self.open_file)

        self.save_button = QtWidgets.QPushButton("Save")
        self.save_button.clicked.connect(self.save_file)

        self.new_tab_button = QtWidgets.QPushButton("New Tab")
        self.new_tab_button.clicked.connect(self.newTab)

        # Find/Replace panel
        self.find_line = QtWidgets.QLineEdit()
        self.find_line.setPlaceholderText("Find")
        self.replace_line = QtWidgets.QLineEdit()
        self.replace_line.setPlaceholderText("Replace")
        self.find_button = QtWidgets.QPushButton("Find Next")
        self.find_button.clicked.connect(self.find_text)
        self.replace_button = QtWidgets.QPushButton("Replace")
        self.replace_button.clicked.connect(self.replace_text)

        find_layout = QtWidgets.QHBoxLayout()
        find_layout.addWidget(self.find_line)
        find_layout.addWidget(self.replace_line)
        find_layout.addWidget(self.find_button)
        find_layout.addWidget(self.replace_button)

        # Theme selector
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        self.theme_combo.currentTextChanged.connect(self.change_theme)

        # Button layout
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.clear_output_button)
        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.new_tab_button)
        button_layout.addWidget(QtWidgets.QLabel("Theme:"))
        button_layout.addWidget(self.theme_combo)

        # Splitter for editor tabs and output console
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(self.tab_widget)
        splitter.addWidget(self.output_console)
        splitter.setSizes([700, 300])

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(button_layout)
        layout.addLayout(find_layout)
        layout.addWidget(splitter)
        self.setLayout(layout)

        # Autosave timer
        self.autosave_timer = QtCore.QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(self.AUTOSAVE_INTERVAL)

        self.current_file = None

    # --- Tab Management ---
    def newTab(self):
        editor = PythonCodeEditor()
        editor.run_requested.connect(self.run_code)
        index = self.tab_widget.addTab(editor, "Untitled")
        self.tab_widget.setCurrentIndex(index)

    def closeTab(self, index):
        widget = self.tab_widget.widget(index)
        if widget:
            self.tab_widget.removeTab(index)
            widget.deleteLater()

    def currentEditor(self):
        return self.tab_widget.currentWidget()

    # --- Run Code with Execution Timer ---
    def run_code(self):
        self.output_console.clear()
        start_time = time.time()

        class MultiWriter:
            def __init__(self, output_console):
                self.console = output_console
                self.buffer = io.StringIO()
            def write(self, text):
                self.buffer.write(text)
                self.console.write(text)
            def flush(self):
                self.buffer.flush()

        old_stdout, old_stderr = sys.stdout, sys.stderr
        multi_stdout = MultiWriter(self.output_console)
        sys.stdout = multi_stdout
        sys.stderr = multi_stdout

        try:
            code_text = self.currentEditor().toPlainText().strip()
            interpreter = code.InteractiveInterpreter(globals())
            try:
                result = eval(code_text)
                if result is not None:
                    print(result)
            except (SyntaxError, TypeError):
                interpreter.runcode(compile(code_text, '<string>', 'exec'))
        except Exception as e:
            traceback_str = traceback.format_exc()
            self.output_console.write(f"[ERROR]\n{traceback_str}")
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            elapsed = time.time() - start_time
            self.output_console.write(f"[INFO] Execution time: {elapsed:.3f} seconds")

    def clear_output(self):
        self.output_console.clear()

    # --- File Open/Save and Recent Files ---
    def open_file(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Python File", "", "Python Files (*.py);;All Files (*)")
        if filename:
            with open(filename, 'r') as f:
                self.currentEditor().setPlainText(f.read())
            self.current_file = filename
            self.tab_widget.setTabText(self.tab_widget.currentIndex(), os.path.basename(filename))
            self.output_console.write(f"[INFO] Opened file: {filename}")
            if filename not in self.recent_files:
                self.recent_files.append(filename)
            self.file_history[filename] = self.currentEditor().toPlainText()

    def save_file(self):
        if not self.current_file:
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Python File", "", "Python Files (*.py);;All Files (*)")
            if filename:
                self.current_file = filename
                self.tab_widget.setTabText(self.tab_widget.currentIndex(), os.path.basename(filename))
        if self.current_file:
            with open(self.current_file, 'w') as f:
                f.write(self.currentEditor().toPlainText())
            self.output_console.write(f"[INFO] Saved file: {self.current_file}")
            self.file_history[self.current_file] = self.currentEditor().toPlainText()

    # --- Find & Replace ---
    def find_text(self):
        text = self.find_line.text()
        if text:
            editor = self.currentEditor()
            if not editor.find(text):
                # if not found, restart from top
                cursor = editor.textCursor()
                cursor.movePosition(QtGui.QTextCursor.Start)
                editor.setTextCursor(cursor)
                editor.find(text)

    def replace_text(self):
        find_str = self.find_line.text()
        replace_str = self.replace_line.text()
        if find_str:
            editor = self.currentEditor()
            content = editor.toPlainText()
            new_content = content.replace(find_str, replace_str)
            editor.setPlainText(new_content)
            self.output_console.write(f"[INFO] Replaced all occurrences of '{find_str}' with '{replace_str}'")

    # --- Theme Switching ---
    def change_theme(self, theme):
        if theme == "Dark":
            self.setStyleSheet("""
                QWidget { background-color: #2b2b2b; color: #f8f8f2; font-family: Consolas, monospace; }
                QPushButton { background-color: #444444; border: 1px solid #555555; padding: 5px; color: #f8f8f2; }
                QLineEdit { background-color: #3c3c3c; border: 1px solid #555555; padding: 3px; color: #f8f8f2; }
                QTabWidget::pane { border: 1px solid #555555; }
            """)
            for i in range(self.tab_widget.count()):
                editor = self.tab_widget.widget(i)
                editor.setStyleSheet("background-color: #272822; color: #f8f8f2;")
            self.output_console.setStyleSheet("""
                background-color: #1e1e1e; 
                color: #e6e6e6; 
                font-family: Consolas, monospace;
                border: 1px solid #333;
                padding: 5px;
            """)
        elif theme == "Light":
            self.setStyleSheet("""
                QWidget { background-color: #f0f0f0; color: #000; font-family: Consolas, monospace; }
                QPushButton { background-color: #ddd; border: 1px solid #aaa; padding: 5px; color: #000; }
                QLineEdit { background-color: #fff; border: 1px solid #aaa; padding: 3px; color: #000; }
                QTabWidget::pane { border: 1px solid #aaa; }
            """)
            for i in range(self.tab_widget.count()):
                editor = self.tab_widget.widget(i)
                editor.setStyleSheet("background-color: #fff; color: #000;")
            self.output_console.setStyleSheet("""
                background-color: #eee; 
                color: #000; 
                font-family: Consolas, monospace;
                border: 1px solid #aaa;
                padding: 5px;
            """)

    # --- Autosave ---
    def autosave(self):
        if self.current_file:
            current_text = self.currentEditor().toPlainText()
            # Save only if the text has changed from the last saved version
            if self.file_history.get(self.current_file, "") != current_text:
                with open(self.current_file, 'w') as f:
                    f.write(current_text)
                self.file_history[self.current_file] = current_text
                self.output_console.write(f"[INFO] Autosaved file: {self.current_file}")

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

# For testing outside Houdini, uncomment the following lines:
# if __name__ == "__main__":
#     app = QtWidgets.QApplication(sys.argv)
#     interface = createInterface()
#     interface.show()
#     sys.exit(app.exec_())
