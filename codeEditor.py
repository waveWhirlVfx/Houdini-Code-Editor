import hou
import os
import sys
import io
import time
import traceback
import code
import re
from PySide2 import QtCore, QtWidgets, QtGui
import webbrowser

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
# Python Code Editor with Enhanced Auto-Completion
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

        # Always use dark theme.
        self.setStyleSheet("background-color: #272822; color: #f8f8f2;")
        PythonHighlighter(self.document())

        # Static completions: Python keywords and Houdini-related names.
        self.static_completions = [
            "and", "as", "assert", "break", "class", "continue", "def", "del",
            "elif", "else", "except", "False", "finally", "for", "from", "global",
            "if", "import", "in", "is", "lambda", "None", "nonlocal", "not", "or",
            "pass", "raise", "return", "True", "try", "while", "with", "yield",
            "hou", "node", "parm", "geometry", "obj", "sop", "networkEditor", "ui"
        ]
        self.completer = QtWidgets.QCompleter(self.static_completions, self)
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
        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()
            lineColor = QtGui.QColor("#49483e")
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
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

    # --- Code Completion with Dynamic Introspection ---
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

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Return and (event.modifiers() & QtCore.Qt.ControlModifier):
            self.run_requested.emit()
            return

        if self.completer.popup() and self.completer.popup().isVisible():
            if event.key() in (QtCore.Qt.Key_Enter, QtCore.Qt.Key_Return,
                               QtCore.Qt.Key_Escape, QtCore.Qt.Key_Tab, QtCore.Qt.Key_Backtab):
                event.ignore()
                return

        super(PythonCodeEditor, self).keyPressEvent(event)

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

        cursor = self.textCursor()
        cursor.select(QtGui.QTextCursor.LineUnderCursor)
        line_text = cursor.selectedText()
        col = self.textCursor().positionInBlock()
        prefix_expr = line_text[:col]

        match = re.search(r'(.+)\.(\w*)$', prefix_expr)
        if match:
            expr = match.group(1).strip()
            self.completion_prefix = match.group(2)
            suggestions = []
            try:
                evaluated = eval(expr, globals())
                suggestions = [attr for attr in dir(evaluated) if not attr.startswith("_")]
            except Exception:
                suggestions = []
            if suggestions:
                self.completer.model().setStringList(suggestions)
            else:
                self.completer.model().setStringList(self.static_completions)
        else:
            completionPrefix = self.textUnderCursor()
            self.completion_prefix = completionPrefix
            self.completer.model().setStringList(self.static_completions)

        if len(self.completion_prefix) >= 1:
            self.completer.setCompletionPrefix(self.completion_prefix)
            cr = self.cursorRect()
            cr.setWidth(self.completer.popup().sizeHintForColumn(0) +
                        self.completer.popup().verticalScrollBar().sizeHint().width())
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
# Main Panel with Improved Layout, Toolbar, and Find/Replace
# -------------------------------
class VSCodeLikePanel(QtWidgets.QWidget):
    AUTOSAVE_INTERVAL = 30000  # 30 seconds

    def __init__(self, parent=None):
        super(VSCodeLikePanel, self).__init__(parent)
        self.setWindowTitle("Houdini Python Panel")
        self.resize(1200, 900)
        
        # Always use dark theme.
        self.setStyleSheet("""
            QWidget { background-color: #2b2b2b; color: #f8f8f2; font-family: Consolas, monospace; }
            QToolBar { background-color: #333333; spacing: 8px; }
            QToolButton { background: none; border: none; color: #f8f8f2; }
            QTabWidget::pane { border: 1px solid #555555; }
            QLineEdit { background-color: #3c3c3c; border: 1px solid #555555; padding: 3px; color: #f8f8f2; }
        """)
        self.recent_files = []
        self.file_history = {}

        self._createToolBar()
        self._createFindReplaceWidget()
        self._createCentralWidgets()
        self._createStatusBar()

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        main_layout.addWidget(self.toolBar)
        main_layout.addWidget(self.findReplaceWidget)
        main_layout.addWidget(self.centralSplitter)
        main_layout.addWidget(self.statusBar)
        self.setLayout(main_layout)

        # Shortcut for toggling find/replace panel.
        QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, activated=self.toggleFindReplace)

        self.autosave_timer = QtCore.QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(self.AUTOSAVE_INTERVAL)

        self.current_file = None

    def _createToolBar(self):
        self.toolBar = QtWidgets.QToolBar()
        style = self.style()
        
        runAction = QtWidgets.QAction(style.standardIcon(QtWidgets.QStyle.SP_MediaPlay), "Run (Ctrl+Enter)", self)
        runAction.triggered.connect(self.run_code)
        openAction = QtWidgets.QAction(style.standardIcon(QtWidgets.QStyle.SP_DialogOpenButton), "Open", self)
        openAction.triggered.connect(self.open_file)
        saveAction = QtWidgets.QAction(style.standardIcon(QtWidgets.QStyle.SP_DialogSaveButton), "Save", self)
        saveAction.triggered.connect(self.save_file)
        newTabAction = QtWidgets.QAction(style.standardIcon(QtWidgets.QStyle.SP_FileIcon), "New Tab", self)
        newTabAction.triggered.connect(self.newTab)
        clearAction = QtWidgets.QAction("Clear Output", self)
        clearAction.triggered.connect(self.clear_output)
        # Houdini Help button removed as per request.

        self.toolBar.addAction(runAction)
        self.toolBar.addAction(openAction)
        self.toolBar.addAction(saveAction)
        self.toolBar.addAction(newTabAction)
        self.toolBar.addAction(clearAction)

    def _createFindReplaceWidget(self):
        # A widget that allows find and replace; initially hidden.
        self.findReplaceWidget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(self.findReplaceWidget)
        layout.setContentsMargins(4, 4, 4, 4)
        self.findEdit = QtWidgets.QLineEdit()
        self.findEdit.setPlaceholderText("Find")
        self.replaceEdit = QtWidgets.QLineEdit()
        self.replaceEdit.setPlaceholderText("Replace")
        self.findNextBtn = QtWidgets.QPushButton("Find Next")
        self.findNextBtn.clicked.connect(self.find_text)
        self.replaceBtn = QtWidgets.QPushButton("Replace")
        self.replaceBtn.clicked.connect(self.replace_text)
        layout.addWidget(self.findEdit)
        layout.addWidget(self.replaceEdit)
        layout.addWidget(self.findNextBtn)
        layout.addWidget(self.replaceBtn)
        self.findReplaceWidget.setLayout(layout)
        self.findReplaceWidget.setVisible(False)

    def toggleFindReplace(self):
        # Toggle visibility of the find/replace widget.
        visible = self.findReplaceWidget.isVisible()
        self.findReplaceWidget.setVisible(not visible)

    def _createCentralWidgets(self):
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.closeTab)
        self.newTab()  # Start with one tab.

        self.output_console = OutputConsole()

        self.centralSplitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.centralSplitter.addWidget(self.tab_widget)
        self.centralSplitter.addWidget(self.output_console)
        self.centralSplitter.setSizes([700, 300])

    def _createStatusBar(self):
        self.statusBar = QtWidgets.QStatusBar()
        self.statusBar.showMessage("Ready")

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

    # --- Code Execution ---
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
            self.statusBar.showMessage(f"Execution finished in {elapsed:.3f} seconds", 5000)

    def clear_output(self):
        self.output_console.clear()

    # --- File Open/Save ---
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

    # --- Find & Replace Functions ---
    def find_text(self):
        search_text = self.findEdit.text()
        if search_text:
            editor = self.currentEditor()
            if not editor.find(search_text):
                cursor = editor.textCursor()
                cursor.movePosition(QtGui.QTextCursor.Start)
                editor.setTextCursor(cursor)
                editor.find(search_text)

    def replace_text(self):
        find_str = self.findEdit.text()
        replace_str = self.replaceEdit.text()
        if find_str:
            editor = self.currentEditor()
            content = editor.toPlainText()
            new_content = content.replace(find_str, replace_str)
            editor.setPlainText(new_content)
            self.output_console.write(f"[INFO] Replaced all occurrences of '{find_str}' with '{replace_str}'")

    # --- Autosave ---
    def autosave(self):
        if self.current_file:
            current_text = self.currentEditor().toPlainText()
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
