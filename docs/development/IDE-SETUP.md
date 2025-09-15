# IDE Setup Guide for Zuban LSP Integration

This guide helps you configure your IDE to work with Crackerjack's ultra-fast Zuban LSP server for real-time type checking.

## VS Code Configuration

### 1. Install Python Extension

Ensure you have the official Python extension installed.

### 2. Configure settings.json

Add to your VS Code `settings.json`:

```json
{
  "python.analysis.typeCheckingMode": "off",
  "python.linting.enabled": false,
  "python.languageServer": "None",
  "python.analysis.autoImportCompletions": true,

  // Zuban LSP Configuration
  "languageServerExample.trace.server": "verbose",
  "files.associations": {
    "*.py": "python"
  }
}
```

### 3. Manual LSP Client Setup (Advanced)

For direct Zuban LSP integration, create a VS Code extension or use a generic LSP client:

```json
{
  "languageServer": {
    "zuban": {
      "command": "uv",
      "args": ["run", "zuban", "lsp"],
      "filetypes": ["python"],
      "settings": {
        "zuban": {
          "strict": true,
          "mypy_compatibility": true
        }
      }
    }
  }
}
```

## PyCharm Configuration

### 1. Disable Built-in Type Checking

1. Go to **File → Settings → Editor → Inspections**
1. Disable **Python → Type checker** inspections
1. Keep **Python → General** inspections enabled

### 2. Configure External Tools

1. Go to **File → Settings → Tools → External Tools**
1. Add new tool:
   - **Name**: Zuban Type Check
   - **Program**: `uv`
   - **Arguments**: `run zuban check $FilePath$`
   - **Working Directory**: `$ProjectFileDir$`

### 3. File Watchers (Optional)

1. Install **File Watchers** plugin
1. Add watcher for `.py` files:
   - **File Type**: Python
   - **Scope**: Current File
   - **Program**: `uv`
   - **Arguments**: `run zuban check $FilePath$`

## Neovim/Vim Configuration

### With built-in LSP (Neovim 0.5+)

```lua
-- init.lua
local lspconfig = require('lspconfig')

-- Configure Zuban LSP
lspconfig.zuban = {
  default_config = {
    cmd = { 'uv', 'run', 'zuban', 'lsp' },
    filetypes = { 'python' },
    root_dir = function(fname)
      return lspconfig.util.root_pattern('pyproject.toml', '.git')(fname) or
             lspconfig.util.path.dirname(fname)
    end,
    settings = {
      zuban = {
        strict = true,
        mypy_compatibility = true
      }
    }
  }
}

-- Start Zuban LSP for Python files
lspconfig.zuban.setup{}
```

### With CoC (Vim)

Add to your `coc-settings.json`:

```json
{
  "languageserver": {
    "zuban": {
      "command": "uv",
      "args": ["run", "zuban", "lsp"],
      "filetypes": ["python"],
      "rootPatterns": ["pyproject.toml", ".git/"],
      "settings": {
        "zuban": {
          "strict": true,
          "mypy_compatibility": true
        }
      }
    }
  }
}
```

## Sublime Text Configuration

### LSP Package

1. Install **LSP** package via Package Control
1. Add to LSP settings:

```json
{
  "clients": {
    "zuban": {
      "enabled": true,
      "command": ["uv", "run", "zuban", "lsp"],
      "selector": "source.python",
      "settings": {
        "zuban": {
          "strict": true,
          "mypy_compatibility": true
        }
      }
    }
  }
}
```

## Emacs Configuration

### With lsp-mode

```elisp
;; Add to your init.el
(use-package lsp-mode
  :config
  (add-to-list 'lsp-language-id-configuration '(python-mode . "python"))

  (lsp-register-client
   (make-lsp-client
    :new-connection (lsp-stdio-connection '("uv" "run" "zuban" "lsp"))
    :major-modes '(python-mode)
    :server-id 'zuban
    :initialization-options '((settings . ((zuban . ((strict . t)
                                                     (mypy_compatibility . t)))))))))

(add-hook 'python-mode-hook #'lsp)
```

## Troubleshooting

### Common Issues

**LSP server not starting**:

```bash
# Check if Zuban is installed
uv run zuban --version

# Test LSP server manually
uv run zuban lsp --help
```

**Performance issues**:

- Increase timeout in `pyproject.toml`:

```toml
[tool.zuban.lsp]
timeout = 20.0
```

**Connection refused**:

- Check if port 8677 is available
- Try different port in configuration

### Verification

Test your setup:

```bash
# Start Crackerjack with LSP enabled
python -m crackerjack --enable-lsp-hooks

# Check LSP integration in logs
python -m crackerjack --ai-debug --run-tests
```

## Benefits

With proper IDE integration, you get:

- **Real-time type checking** 20-200x faster than pyright
- **Instant error feedback** without running tools manually
- **Seamless fallback** to CLI when LSP unavailable
- **Zero configuration** for basic use cases
- **Full mypy compatibility** for existing projects

## Support

For IDE-specific issues:

1. Check Crackerjack logs with `--ai-debug`
1. Verify LSP server with `uv run zuban lsp --test`
1. File issues at [GitHub repository](https://github.com/lesleslie/crackerjack/issues)
