# RepoPilot VS Code Extension - Testing Guide

## ✅ Pre-Test Setup Checklist

- [x] Backend running at http://localhost:8000
- [ ] VS Code installed (version 1.85.0 or higher)
- [ ] Extension compiled (`npm run compile` in vscode-extension folder)

## 🧪 Manual Test Procedure

### Test 1: Extension Activation
**Steps:**
1. Open `vscode-extension` folder in VS Code
2. Press **F5**
3. New Extension Development Host window opens

**Expected:**
- No errors in debug console
- Extension activates successfully

### Test 2: Chat Panel Opens
**Steps:**
1. In the Extension Development Host window, open a workspace folder
2. Click RepoPilot icon in the activity bar (left sidebar)

**Expected:**
- Chat panel opens in sidebar
- Shows welcome message

### Test 3: Backend Health Check
**Steps:**
1. Stop the backend (`Ctrl+C` in backend terminal)
2. Reload the Extension Development Host window

**Expected:**
- Status shows "⚠️ Backend not connected"
- Warning message: "RepoPilot backend is not running..."

**Cleanup:** Restart backend

### Test 4: Auto-Indexing
**Steps:**
1. With backend running, reload Extension Development Host
2. Open a workspace folder
3. Watch the status bar in RepoPilot panel

**Expected:**
- Status changes: "⏳ Loading..." → "🔄 Indexing..." → "✅ Ready"
- System messages appear in chat showing progress

### Test 5: Ask Question
**Steps:**
1. After indexing completes, type a question in the input box:
   ```
   What does this codebase do?
   ```
2. Click Send (or press Enter)

**Expected:**
- User message appears in chat
- Loading indicator shows briefly
- Assistant response appears with 8 sections:
  - 🧩 Query Decomposition
  - 📌 Evidence (with citations)
  - ✅ Answer
  - 🧠 Pattern Consistency Check
  - ⚠️ Missing Info / Risks
  - ✅ Assumptions & Limitations
- Citations appear as clickable buttons

### Test 6: Click Citation
**Steps:**
1. In the previous response, click any citation button

**Expected:**
- File opens in editor
- Cursor jumps to the cited line range
- Line range is highlighted

### Test 7: Right-Click Selection
**Steps:**
1. Open any code file in the workspace
2. Select a few lines of code
3. Right-click to open context menu
4. Click "Ask RepoPilot About Selection"

**Expected:**
- Chat panel focuses
- Question appears with selected code embedded
- Response explains the selected code

### Test 8: Generate Code
**Steps:**
1. Type in chat input:
   ```
   /generate Add a function to calculate factorial
   ```
2. Click Send

**Expected:**
- Response includes additional sections:
  - 🧪 Tests (PyTest code)
  - 🔧 Changes (file diffs)
- Diffs show code changes in diff format

### Test 9: Safe Refusal
**Steps:**
1. Ask a question about something not in the codebase:
   ```
   How does the Mars rover navigation system work?
   ```
2. Click Send

**Expected:**
- Response shows low confidence
- "⚠️ Missing Info / Risks" section explains limitations
- May show safe refusal message

### Test 10: State Persistence
**Steps:**
1. With workspace indexed, reload Extension Development Host window
2. Check status in RepoPilot panel

**Expected:**
- Status immediately shows "✅ Ready" (with repo name)
- No re-indexing occurs
- State restored from previous session

## 🎯 Additional Manual Tests

### Test: Index Button
**Steps:** Click "📁 Index" button in chat

**Expected:** Re-indexes workspace, updates status

### Test: Generate Button
**Steps:** Type a request, click "⚡ Generate" button

**Expected:** Treats request as generation (adds `/generate` prefix)

### Test: Explain Selection Command
**Steps:** Select code → right-click → "Explain Selection"

**Expected:** More detailed explanation than "Ask About Selection"

### Test: Configuration Change
**Steps:**
1. Open VS Code Settings
2. Search for "RepoPilot"
3. Change "Backend URL" to `http://localhost:9999`
4. Try clicking Index

**Expected:** Error because backend not at new URL

**Cleanup:** Change back to `http://localhost:8000`

## 📊 Test Results Template

```
Date: _____________
Tester: _____________

| Test # | Status | Notes |
|--------|--------|-------|
| 1      | ☐ Pass ☐ Fail | |
| 2      | ☐ Pass ☐ Fail | |
| 3      | ☐ Pass ☐ Fail | |
| 4      | ☐ Pass ☐ Fail | |
| 5      | ☐ Pass ☐ Fail | |
| 6      | ☐ Pass ☐ Fail | |
| 7      | ☐ Pass ☐ Fail | |
| 8      | ☐ Pass ☐ Fail | |
| 9      | ☐ Pass ☐ Fail | |
| 10     | ☐ Pass ☐ Fail | |
```

## 🐛 Known Issues to Watch For

- [ ] Citations with absolute paths may not open correctly
- [ ] Large codebases may take a long time to index
- [ ] Network timeout if backend is slow
- [ ] Webview may not refresh after code changes (reload window)

## 💡 Debugging Tips

**View Extension Logs:**
- In Extension Development Host: Help → Toggle Developer Tools
- Look for console errors in red

**View Backend Logs:**
- Check the terminal running `python backend/run.py`
- Look for API call logs and errors

**Rebuild Extension:**
```bash
cd vscode-extension
npm run compile
```
Then reload Extension Development Host window
