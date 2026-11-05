# Using Text2SQL2Chart with uv

Complete guide for using text2sql2chart with the `uv` package manager.

---

## What is uv?

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver, written in Rust. It's:
- ⚡ **10-100x faster** than pip
- 🔒 **More reliable** dependency resolution
- 📦 **Better caching** for faster installs
- 🎯 **Drop-in replacement** for pip

---

## Installation

### 1. Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or with pip
pip install uv
```

### 2. Install text2sql2chart

```bash
# Clone the repository
git clone https://github.com/yourusername/text2sql2chart.git
cd text2sql2chart

# Install with uv
uv pip install -e .
```

---

## Usage

### Running CLI Commands

Use `uv run` to execute commands in the virtual environment:

```bash
# Check version
uv run text2sql2chart --version

# Quick start
uv run text2sql2chart grafana quick

# Check status
uv run text2sql2chart grafana status

# Stop services
uv run text2sql2chart grafana stop
```

### Running Python Scripts

```bash
# Run demo script
uv run python examples/demo_grafana.py

# Run module directly
uv run python -m text2sql2chart.cli.commands grafana quick
```

### Running with Environment Variables

```bash
# Set env vars inline
OPENAI_API_KEY=sk-xxx uv run text2sql2chart grafana quick

# Or use .env file
cp .env.example .env
# Edit .env with your API key
uv run text2sql2chart grafana quick
```

---

## Development

### Install Development Dependencies

```bash
# Install with dev extras
uv pip install -e ".[dev]"
```

### Run Tests

```bash
# Run pytest
uv run pytest

# Run with coverage
uv run pytest --cov=src/text2sql2chart
```

### Code Formatting

```bash
# Format code with black
uv run black src/

# Lint with ruff
uv run ruff check src/

# Type check with mypy
uv run mypy src/
```

---

## Docker with uv

The project's Docker setup already uses uv for faster builds:

```dockerfile
# Dockerfile uses uv for installation
FROM python:3.11-slim
RUN pip install uv
RUN uv pip install --no-cache-dir -r requirements.txt
```

---

## Performance Comparison

### Installation Speed

```bash
# pip (traditional)
pip install -e .  # ~30-60 seconds

# uv (fast)
uv pip install -e .  # ~5-10 seconds
```

### Dependency Resolution

```bash
# pip (slow on conflicts)
pip install package  # Can take minutes on conflicts

# uv (fast conflict resolution)
uv pip install package  # Resolves in seconds
```

---

## Common Commands

### Package Management

```bash
# Install package
uv pip install package-name

# Install from requirements.txt
uv pip install -r requirements.txt

# Install with extras
uv pip install -e ".[dev,test]"

# Uninstall package
uv pip uninstall package-name

# List installed packages
uv pip list

# Show package details
uv pip show package-name
```

### Environment Management

```bash
# Create virtual environment
uv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Run command in venv (without activation)
uv run python script.py
uv run text2sql2chart grafana quick
```

### Lock Files

```bash
# Generate lock file
uv pip compile pyproject.toml -o requirements.txt

# Install from lock file
uv pip sync requirements.txt
```

---

## Troubleshooting

### Command Not Found

```bash
# Make sure uv is installed
uv --version

# Reinstall the package
uv pip install -e .

# Use full path if needed
uv run python -m text2sql2chart.cli.commands grafana quick
```

### Permission Errors

```bash
# Use --user flag for user installation
uv pip install --user -e .

# Or use virtual environment
uv venv
source .venv/bin/activate
uv pip install -e .
```

### Cache Issues

```bash
# Clear uv cache
uv clean

# Install with --no-cache
uv pip install --no-cache -e .
```

---

## Migration from pip

If you're currently using pip, switching to uv is simple:

### Before (pip)
```bash
pip install -e .
python -m text2sql2chart.cli.commands grafana quick
```

### After (uv)
```bash
uv pip install -e .
uv run text2sql2chart grafana quick
```

### Both Work
You can use both pip and uv interchangeably. The package works with either.

---

## Best Practices

### 1. Use Virtual Environments

```bash
# Create venv with uv
uv venv

# Activate it
source .venv/bin/activate

# Now you can run without 'uv run'
text2sql2chart grafana quick
```

### 2. Pin Dependencies

```bash
# Generate lock file
uv pip freeze > requirements.lock

# Install exact versions
uv pip install -r requirements.lock
```

### 3. Use .env Files

```bash
# Create .env file
cp .env.example .env

# uv automatically loads .env
uv run text2sql2chart grafana quick
```

### 4. Separate Dev Dependencies

```bash
# Install only production deps
uv pip install -e .

# Install with development tools
uv pip install -e ".[dev]"
```

---

## Complete Workflow Example

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and setup project
git clone https://github.com/yourusername/text2sql2chart.git
cd text2sql2chart

# 3. Create virtual environment
uv venv

# 4. Install package
uv pip install -e .

# 5. Configure
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

# 6. Run
uv run text2sql2chart grafana quick

# 7. Access
open http://localhost:3000
```

---

## Why Use uv?

### Speed
- ⚡ 10-100x faster than pip
- Parallel downloads
- Better caching

### Reliability
- 🔒 Better dependency resolution
- Deterministic installs
- Conflict detection

### Modern
- 🦀 Written in Rust
- Active development
- Growing ecosystem

### Compatible
- 📦 Drop-in pip replacement
- Works with existing tools
- Supports all pip features

---

## Resources

- **uv Documentation**: https://github.com/astral-sh/uv
- **Installation Guide**: https://astral.sh/uv
- **PyPI Package**: https://pypi.org/project/uv/

---

**Using uv with text2sql2chart is recommended for the best experience!** ⚡
