# RepoPilot AI - VS Code Extension

**Repository-grounded AI coding assistant that provides answers, generates code, and writes tests only when supported by evidence from your codebase.**

![RepoPilot](media/icon.png)

## 🚀 Key Features

*   **Side-panel Chat**: Copilot-like chat interface with persistent history.
*   **Auto-Indexing**: Automatically indexes your workspace to understand your code.
*   **Grounded Answers**: Every answer is backed by citations (files & line numbers).
*   **Code Generation**: Generates code edits with diff previews and PyTest validation files.
*   **Right-Click Actions**: "Ask RepoPilot" or "Explain Selection" directly from the editor.
*   **Backend Launcher**: Built-in command to start the local inference server.
*   **Export Chat**: Save your conversation history to Markdown.
*   **Professional UI**: sleek, modern interface with dark/light mode support.

## 📦 Installation

1.  **Download the VSIX**: Get the `repopilot-1.0.0.vsix` file.
2.  **Install in VS Code**:
    *   Go to **Extensions** sidebar.
    *   Click the **... (More Actions)** menu.
    *   Select **Install from VSIX...**
    *   Choose the file.

## 📋 Prerequisites

**RepoPilot requires a local backend server.**

1.  **Start the Backend**:
    *   Run `RepoPilot: Start Backend` from the Command Palette (`Ctrl+Shift+P`).
    *   *Or* run `python run.py` in the backend folder manually.
2.  **Verify Connection**:
    *   The status dot in the chat panel should turn **Green (Ready)**.

## 🎯 Usage Manual

### Chat Interface
*   **Ask**: Type queries like "How does the auth middleware work?"
*   **Generate**: Prefix with `/generate` (e.g., `/generate Add a reset password route`).
*   **History**: Chat persists across reloads.
*   **Export**: Click the download icon in the header to save chat logs.

### Context Actions
*   **Code Lens**: Click "Ask RepoPilot" appearing above functions/classes.
*   **Context Menu**: Highlight code -> Right Click -> "Ask RepoPilot About Selection".

### Commands
*   `RepoPilot: Open Chat` (`Ctrl+Shift+R`)
*   `RepoPilot: Index Workspace` - Force re-indexing.
*   `RepoPilot: Start Backend` - Launch the local server.
*   `RepoPilot: Export Chat History` - Save conversation.

## ⚙️ Configuration

*   `repopilot.backendUrl`: URL of your local backend (Default: `http://localhost:8000`).
*   `repopilot.autoIndexOnOpen`: Enable/disable auto-indexing (Default: `true`).

---

**Empower your coding with Grounded AI.**


- **Side-panel Chat Interface** - Copilot-like chat in your VS Code sidebar
- **Auto-Indexing** - Automatically indexes your workspace on opening
- **Grounded Answers** - All responses are backed by citations from your code
- **Code Generation** - Generate code with diffs and PyTest files
- **Right-Click Actions** - Ask RepoPilot about selected code
- **Clickable Citations** - Jump directly to referenced files
- **PS2-Compliant Responses** - Judge-proof 8-section response format

## 📋 Prerequisites

1. **Backend Server Running**:
   ```bash
   cd ../backend
   python run.py
   ```
   Backend should be running at `http://localhost:8000`

2. **Node.js** installed (for development)

## 🛠️ Setup for Development

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Compile the extension**:
   ```bash
   npm run compile
   ```

3. **Run the extension**:
   - Open this folder in VS Code
   - Press **F5** to launch Extension Development Host
   - A new VS Code window will open with the extension loaded

## 🎯 Usage

### First Time Setup
1. Make sure the backend is running
2. Open a workspace/folder in VS Code
3. Click the RepoPilot icon in the activity bar (sidebar)
4. The extension will automatically index your workspace

### Chat Interface
- **Ask Questions**: Type your question and click Send or press Enter
- **Generate Code**: Prefix your message with `/generate` or click the Generate button
- **Re-index**: Click the Index button to re-index your workspace

### Right-Click Actions
1. Select some code in any file
2. Right-click to open context menu
3. Choose "Ask RepoPilot About Selection" or "Explain Selection"

### Commands (Ctrl+Shift+P)
- `RepoPilot: Open Chat` - Open the chat panel
- `RepoPilot: Index Workspace` - Index the current workspace
- `RepoPilot: Ask About Selection` - Ask about selected code
- `RepoPilot: Explain Selection` - Get detailed explanation
- `RepoPilot: Generate Code` - Generate code from a prompt

## ⚙️ Settings

Configure in VS Code Settings (File → Preferences → Settings → RepoPilot):

- **Backend URL** (`repopilot.backendUrl`)
  - Default: `http://localhost:8000`
  - Change this if your backend runs on a different URL/port

- **Auto Index on Open** (`repopilot.autoIndexOnOpen`)
  - Default: `true`
  - Automatically index workspace when opening a folder

## 📦 Packaging for Distribution

1. **Install vsce**:
   ```bash
   npm install -g @vscode/vsce
   ```

2. **Package the extension**:
   ```bash
   vsce package
   ```

3. **Install the .vsix file**:
   - In VS Code: Extensions → ⋯ Menu → Install from VSIX
   - Select `repopilot-0.1.0.vsix`

## 🧪 Manual Test Checklist

| # | Test | Expected Result |
|---|------|-----------------|
| 1 | Extension activates | No errors in debug console |
| 2 | Chat opens in sidebar | RepoPilot panel appears |
| 3 | Backend offline warning | Error message with instructions |
| 4 | Auto-indexing on open | Status: Loading → Indexing → Ready |
| 5 | Ask question | Formatted response with citations |
| 6 | Click citation | File opens at correct line |
| 7 | Right-click selection | "Ask RepoPilot" in menu |
| 8 | Generate code | Response shows diffs + PyTests |
| 9 | Safe refusal trigger | "I can't safely..." message |
| 10 | Reload VS Code | State persists, repo_id restored |

## 📐 Architecture

### File Structure
```
vscode-extension/
├── src/
│   ├── extension.ts        # Entry point, activation, auto-index
│   ├── chatPanel.ts        # Side-panel webview provider
│   ├── apiClient.ts        # Backend API wrapper
│   ├── commands.ts         # VS Code command handlers
│   ├── codeActions.ts      # Right-click selection actions
│   ├── fileOpener.ts       # Open citations in editor
│   ├── responseFormatter.ts# PS2 judge-proof formatting
│   ├── storage.ts          # State persistence
│   └── types.ts            # TypeScript interfaces
├── media/
│   ├── chat.css            # Webview styles
│   ├── chat.js             # Webview UI logic
│   └── icon.svg            # Activity bar icon
└── package.json            # Extension manifest
```

### Backend API Endpoints (No Changes Required)
- `GET /health` - Health check
- `POST /repo/load` - Load repository
- `GET /repo/status` - Get indexing status
- `POST /repo/index` - Index repository
- `POST /chat/ask` - Grounded Q&A
- `POST /chat/generate` - Code generation

## 🎨 PS2 Judge-Proof Response Format

Every response includes these 8 sections:
1. 🧩 **Query Decomposition** - Sub-questions breakdown
2. 📌 **Evidence** - Repo-grounded citations
3. ✅ **Answer** - Grounded summary
4. 🧠 **Pattern Consistency Check** - Pattern analysis
5. 🧪 **Tests** - PyTest files (generation only)
6. 🔧 **Changes** - File diffs (generation only)
7. ⚠️ **Missing Info / Risks** - Uncertainty notes
8. ✅ **Assumptions & Limitations** - Explicit assumptions

### Safe Refusal
When evidence is missing or conflicting:
- "I can't safely answer this because..."
- "I need: [list of missing files/confirmations]"

## 🐛 Troubleshooting

**Backend not connecting**
- Ensure backend is running: `python backend/run.py`
- Check the backend URL in settings
- Look for errors in VS Code Developer Tools (Help → Toggle Developer Tools)

**Indexing fails**
- Check that the workspace folder exists
- Verify backend logs for errors
- Try manual re-index via the Index button

**Citations not opening files**
- Ensure files exist in the workspace
- Check that paths are relative to workspace root

## 📝 License

Part of the RepoPilot AI project.
