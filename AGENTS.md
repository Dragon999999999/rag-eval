# AGENTS.md

# Project Development Guidelines

This file defines the authoritative coding, documentation, testing, architecture,
and development conventions for this repository.

All AI coding agents and human contributors should follow these guidelines when
creating, modifying, reviewing, or documenting code.

Unless a task explicitly requires otherwise, preserve the conventions defined
here.

---

## 1. General Principles

Code in this project should prioritize:

1. Correctness
2. Clarity
3. Maintainability
4. Reproducibility
5. Testability
6. Explicit behavior
7. Minimal unnecessary complexity

Prefer simple, explicit implementations over clever or overly abstract ones.

Do not introduce abstractions, dependencies, architectural layers, or design
patterns unless they provide a concrete benefit.

When modifying existing code:

- Understand the surrounding implementation before making changes.
- Preserve existing behavior unless the task explicitly requires changing it.
- Avoid unrelated refactoring.
- Keep changes focused on the requested task.
- Update tests and documentation when behavior changes.
- Follow the existing architecture unless there is a clear reason to change it.

---

## 2. Python

Python is the primary programming language of this project.

### 2.1 Python style

Follow:

- PEP 8 for general Python style.
- PEP 257 for docstrings.
- Modern Python best practices.
- Google-style docstrings.

Prefer readable Python over unnecessarily compact Python.

### 2.2 Modern Python syntax

Use modern Python syntax supported by the project's configured Python version.

Prefer:

```python
list[str]
dict[str, int]
tuple[str, ...]
```

instead of:

```python
List[str]
Dict[str, int]
Tuple[str, ...]
```

unless compatibility requirements make the older syntax necessary.

Prefer:

```python
str | None
```

instead of:

```python
Optional[str]
```

when supported by the project's Python version.

### 2.3 Type hints

Use type hints for:

- Function parameters
- Function return values
- Public attributes where useful
- Complex local variables when inference is not obvious

Example:

```python
def extract_text(path: Path) -> str: ...
```

Avoid unnecessary type annotations when the type is completely obvious from the
assignment.

Type hints describe types. Docstrings should describe semantics.

Do not redundantly repeat type information in docstrings.

Prefer:

```python
Args:
    path: Path to the PDF file.
```

rather than:

```python
Args:
    path (Path): Path to the PDF file.
```

### 2.4 Paths

Prefer `pathlib.Path` over raw string manipulation for filesystem paths.

Prefer:

```python
from pathlib import Path

output_path = base_dir / "results" / "output.json"
```

instead of manual path concatenation.

### 2.5 String formatting

Prefer f-strings for ordinary string interpolation.

Example:

```python
message = f"Processed {count} documents."
```

### 2.6 Comprehensions

Use comprehensions when they remain easy to read.

Avoid deeply nested or complicated comprehensions.

If a comprehension requires significant reasoning to understand, use an
explicit loop instead.

### 2.7 Functions

Functions should generally:

- Perform one coherent task.
- Have clear inputs and outputs.
- Avoid hidden side effects.
- Remain reasonably small.
- Use descriptive names.

Do not split functions merely to reduce line count. Extract functions when the
resulting abstraction improves clarity, reuse, testing, or separation of
responsibilities.

---

## 3. Naming Conventions

Use standard Python naming conventions.

### Variables and functions

Use `snake_case`.

```python
paper_content
extract_pdf_text
resolve_api_key
```

### Classes

Use `PascalCase`.

```python
ExtractionResult
DocumentProcessor
```

### Constants

Use `UPPER_SNAKE_CASE`.

```python
DEFAULT_MODEL
MAX_RETRIES
PROMPT_VERSION
```

### Private implementation details

Prefix internal implementation details with `_` when appropriate.

```python
_normalize_text
_parse_response
```

### Naming quality

Names should communicate meaning.

Avoid vague names such as:

```python
data
thing
obj
tmp
result2
value1
```

when a more specific name is reasonably available.

Short conventional names are acceptable where their meaning is obvious, such as
`i`, `j`, `x`, or `y` in appropriate mathematical or local contexts.

---

## 4. Documentation Standard

Documentation should explain the software's behavior, semantics, assumptions,
constraints, and design decisions.

The goal is not maximum documentation volume. The goal is useful and accurate
documentation.

Follow PEP 257 and Google-style docstrings.

---

## 5. Docstrings

### 5.1 What must be documented

Provide docstrings for:

- Public modules
- Public classes
- Public functions
- Public methods
- Nontrivial private functions
- Nontrivial private methods

A private function should generally have a docstring when it involves:

- Complex behavior
- Important assumptions
- I/O
- Network access
- LLM calls
- Data transformation
- Parsing
- Caching
- State mutation
- Domain-specific logic
- Non-obvious algorithms
- Important error conditions

Tiny, completely self-explanatory private helpers do not necessarily require
full docstrings.

Example:

```python
def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())
```

A docstring would be optional here.

### 5.2 One-line docstrings

Use a one-line docstring for simple functions whose behavior is obvious.

Example:

```python
def create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
```

### 5.3 Full function docstrings

Use the following structure when applicable:

```python
def process_document(
    path: Path,
    threshold: float,
) -> ProcessingResult:
    """Process a document and extract structured information.

    Describe important behavior, assumptions, or implementation semantics here
    when they are not obvious from the function name and signature.

    Args:
        path: Path to the input document.
        threshold: Decision threshold in the range [0, 1].

    Returns:
        Structured processing result for the document.

    Raises:
        FileNotFoundError: If the input document does not exist.
        ValueError: If `threshold` is outside the supported range.
    """
```

Use sections only when they are relevant.

Common sections include:

- `Args:`
- `Returns:`
- `Yields:`
- `Raises:`
- `Examples:`
- `Note:`
- `Warning:`

Do not add empty or meaningless sections.

### 5.4 Summary line

Start docstrings with a concise description of the object's purpose.

Good:

```python
"""Extract text from a PDF using positional block ordering."""
```

Weak:

```python
"""This function is used to extract text."""
```

Avoid repeating the function name without adding useful information.

### 5.5 Parameter documentation

Document:

- Semantic meaning
- Constraints
- Units
- Accepted forms
- Important defaults
- Special behavior

Do not merely repeat the parameter name or type.

Good:

```python
Args:
    temperature: Sampling temperature in the range [0, 2].
```

Weak:

```python
Args:
    temperature: The temperature.
```

### 5.6 Return documentation

Describe what the returned value means.

Good:

```python
Returns:
    Extracted text in approximate reading order.
```

Weak:

```python
Returns:
    A string.
```

The type annotation already communicates that it is a string.

### 5.7 Exceptions

Document exceptions that are meaningful parts of the function's behavior.

Example:

```python
Raises:
    FileNotFoundError: If the configured input file does not exist.
    ValueError: If the configuration contains an unsupported model name.
```

Do not document every theoretically possible internal Python exception.

### 5.8 Side effects

Document meaningful externally observable side effects, including:

- File creation or modification
- Network requests
- Database changes
- Global state mutation
- Cache modification
- Environment changes

### 5.9 Assumptions and limitations

Explicitly document important assumptions.

Do not claim guarantees stronger than the implementation provides.

For example, if PDF reading order is heuristic, write:

```python
"""Extract PDF text using a position-based reading-order heuristic.

The heuristic generally improves ordering for structured documents but does
not guarantee correct reading order for arbitrary multi-column layouts.
"""
```

Do not write:

```python
"""Extract PDF text in correct reading order."""
```

unless correctness is actually guaranteed.

### 5.10 Keep documentation synchronized

Documentation must describe the current implementation.

When implementation behavior changes:

- Update relevant docstrings.
- Update comments.
- Update README or architecture documentation when necessary.
- Update prompt documentation when LLM behavior changes.
- Update examples when interfaces change.

Stale documentation should be treated as a defect.

---

## 6. Module Documentation

Every significant Python module should begin with a module-level docstring.

The module docstring should explain:

- The responsibility of the module
- Its role in the system
- Important assumptions or constraints when relevant

Example:

```python
"""Utilities for extracting structured information from research papers.

This module handles PDF text extraction, prompt construction, LLM invocation,
and validation of structured extraction results.
"""
```

Do not use the module docstring to document every function individually.

---

## 7. Class Documentation

Classes should have docstrings describing:

- Their responsibility
- Important state
- Lifecycle expectations
- Important invariants
- Non-obvious behavior

Example:

```python
class PaperExtractor:
    """Extract structured metadata from scientific papers.

    The extractor coordinates document parsing, prompt construction, and LLM
    execution. Instances are configured for a specific model and extraction
    schema.
    """
```

Avoid documentation that merely says:

```python
"""Paper extractor class."""
```

---

## 8. Comments

Comments should primarily explain **why**, not **what**.

Good:

```python
# Group nearby vertical coordinates because PDF text blocks from the same
# visual line frequently differ by several floating-point units.
row = int(y_position // 10)
```

Weak:

```python
# Divide y_position by 10.
row = int(y_position // 10)
```

Useful comments include explanations of:

- Non-obvious design decisions
- Workarounds
- Compatibility constraints
- Algorithmic reasoning
- Numerical assumptions
- Security decisions
- Performance trade-offs
- External API peculiarities
- Known limitations

Remove comments that simply translate obvious Python code into English.

---

## 9. LLM-Specific Development Guidelines

LLM behavior is part of the software system and must be treated as such.

Prompts, models, schemas, and evaluation procedures should be explicit and
reproducible wherever practical.

### 9.1 Prompt design

Prompts should clearly define:

- Task
- Input
- Expected output
- Constraints
- Relevant definitions
- Required reasoning or extraction behavior
- Unsupported behavior to avoid

Avoid vague prompts when precise behavior is required.

### 9.2 Prompt organization

Important prompts should not become large anonymous strings scattered
throughout application code.

As the project grows, prefer a dedicated prompt structure such as:

```text
prompts/
├── paper_extraction/
│   ├── system.md
│   ├── user.md
│   └── README.md
└── grounding/
    ├── system.md
    └── user.md
```

Small, highly local prompts may remain in Python when separating them would make
the implementation harder to understand.

### 9.3 Prompt versioning

Prompts used in experiments or evaluations should be versioned when changes can
affect results.

Example:

```python
PAPER_EXTRACTION_PROMPT_VERSION = "1.2"
```

When practical, experiment records should make it possible to identify:

- Code version
- Prompt version
- Model
- Model configuration
- Input
- Output schema
- Relevant evaluation configuration

### 9.4 Prompt documentation

For important prompts, document:

- Prompt identifier
- Purpose
- Expected input
- Expected output
- Output schema
- Important constraints
- Important assumptions
- Version
- Evaluation relationship where applicable

Example:

```text
Prompt ID: paper-extraction
Version: 1.2

Purpose:
Extract representative keywords and a concise summary from a scientific paper.

Inputs:
- paper_content

Expected output:
- ExtractionResult

Constraints:
- Use information supported by the input document.
- Prefer terminology used by the source paper.
- Return only data represented by the structured output schema.
```

### 9.5 Structured output

Prefer structured LLM output when downstream code depends on predictable data.

Use explicit schemas rather than manually parsing loosely formatted text when
practical.

### 9.6 Pydantic models

When Pydantic is used for LLM output or application data:

- Give significant models useful docstrings.
- Use precise field names.
- Define validation constraints where appropriate.
- Give fields meaningful descriptions when semantics are not obvious.

Example:

```python
class ExtractionResult(BaseModel):
    """Structured metadata extracted from a scientific paper."""

    keywords: list[str] = Field(
        min_length=5,
        max_length=8,
        description="Representative technical keywords or short phrases.",
    )

    summary: str = Field(
        description="Concise summary of the paper's main contribution.",
    )
```

Do not use vague descriptions such as:

```python
description = "Keywords"
```

when more precise semantics matter.

### 9.7 LLM nondeterminism

Do not assume LLM output is deterministic unless the underlying system actually
guarantees it.

Tests involving LLM behavior should distinguish between:

- Deterministic application logic
- Schema validation
- Prompt formatting
- External model behavior
- Evaluation quality

### 9.8 Grounding

When the task requires grounded output:

- Preserve provenance where practical.
- Do not silently introduce unsupported information.
- Keep retrieved evidence distinguishable from generated interpretation.
- Make transformations traceable where required by the experiment.

### 9.9 Model configuration

Do not scatter model names and important generation settings throughout the
codebase.

Prefer centralized configuration for settings such as:

- Model identifier
- Temperature
- Token limits
- Retry behavior
- Endpoint
- Provider

---

## 10. Error Handling

Errors should fail clearly and at an appropriate abstraction level.

### 10.1 Do not silently suppress errors

Avoid:

```python
try:
    ...
except Exception:
    pass
```

unless suppression is explicitly justified.

### 10.2 Catch specific exceptions

Prefer:

```python
try:
    content = path.read_text(encoding="utf-8")
except FileNotFoundError as exc:
    ...
```

over unnecessarily broad exception handling.

### 10.3 Preserve exception context

When translating exceptions, preserve the original cause when useful.

```python
raise ConfigurationError("Unable to load configuration.") from exc
```

### 10.4 Error messages

Error messages should help identify:

- What failed
- Which input or resource caused the failure
- What the user can do when appropriate

Never expose secrets in error messages.

---

## 11. Logging

Use Python's `logging` infrastructure rather than scattered `print()` calls for
application diagnostics.

`print()` remains appropriate for intentional command-line output.

Prefer:

```python
logger.info("Processing document: %s", path)
```

rather than:

```python
print("debug:", path)
```

Logging should communicate useful operational information.

Do not log:

- API keys
- Passwords
- Authentication tokens
- Sensitive credentials

Use appropriate logging levels:

- `DEBUG`: detailed diagnostic information
- `INFO`: normal high-level execution information
- `WARNING`: unexpected but recoverable situations
- `ERROR`: operation failures
- `CRITICAL`: severe system-level failures

Avoid excessive logging inside tight loops unless necessary.

---

## 12. Configuration and Secrets

Configuration should be explicit and centralized where practical.

Use environment variables or appropriate configuration mechanisms for:

- API keys
- Credentials
- Environment-dependent endpoints
- Deployment-specific settings

Never hard-code secrets into source files.

Never commit:

- API keys
- Access tokens
- Passwords
- Private credentials
- Secret configuration files

Use `.env` files only when appropriate, and ensure secret-bearing `.env` files
are excluded from Git.

Provide safe examples through files such as:

```text
.env.example
```

Example:

```text
AQUEDUCT_API_KEY=
AQUEDUCT_API_KEY_FILE=
```

Do not put real credentials into example files.

---

## 13. Dependency Management

Use the dependency-management system configured by the repository.

For this project, prefer `uv`.

Prefer commands such as:

```bash
uv add package-name
uv remove package-name
uv sync
uv run python script.py
uv run pytest
uv run ruff check .
```

Do not unnecessarily mix dependency managers within the same project.

Keep dependencies minimal.

Before adding a dependency, consider whether:

- The standard library already solves the problem.
- An existing project dependency already provides the functionality.
- The dependency is maintained and appropriate for the task.
- Its complexity is justified.

---

## 14. Formatting and Linting

Use automated formatting and linting rather than manually maintaining style.

Prefer Ruff for Python formatting and linting when configured by the project.

Typical commands:

```bash
uv run ruff check .
uv run ruff format .
```

Recommended Ruff configuration should enforce relevant rules including:

- Standard Python errors
- Import ordering
- Modern Python syntax
- Common bug patterns
- Documentation conventions

The project should use Google-style docstrings consistently.

A representative configuration is:

```toml
[tool.ruff.lint]
select = [
    "E",
    "F",
    "I",
    "B",
    "UP",
    "D",
]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
docstring-code-format = true
```

The actual repository configuration in `pyproject.toml` takes precedence over
the example above.

Do not modify lint configuration merely to silence legitimate warnings without
understanding why they occur.

---

## 15. Imports

Organize imports into conventional groups:

1. Standard library
2. Third-party packages
3. Local project imports

Example:

```python
import argparse
import logging
from pathlib import Path

from pydantic import BaseModel, Field

from project.extractors import PaperExtractor
```

Avoid wildcard imports:

```python
from module import *
```

except in rare cases where the module is explicitly designed for that purpose.

Remove unused imports.

---

## 16. Testing

Behavioral changes should normally include corresponding tests.

Use the project's configured testing framework. For Python, prefer `pytest`
unless the repository specifies otherwise.

Tests should be:

- Deterministic where practical
- Independent
- Focused
- Easy to understand
- Fast enough for regular execution

### 16.1 Test behavior, not implementation details

Prefer tests that verify observable behavior.

Avoid tests that become invalid merely because internal implementation details
were refactored without changing behavior.

### 16.2 Test naming

Use descriptive names.

Example:

```python
def test_validate_pdf_path_rejects_missing_file() -> None: ...
```

Avoid vague names such as:

```python
def test_pdf() -> None: ...
```

### 16.3 External services

Unit tests should not make real external API calls unless they are explicitly
integration tests.

Mock or substitute:

- LLM APIs
- HTTP APIs
- Cloud services
- External databases

Separate integration tests from ordinary unit tests where appropriate.

### 16.4 LLM testing

For LLM-related code, separately test deterministic components such as:

- Prompt construction
- Schema validation
- Configuration
- Parsing
- Input preparation
- Result serialization

Model-quality evaluation should generally be handled by dedicated evaluation
procedures rather than ordinary deterministic unit tests.

### 16.5 Edge cases

Tests should include meaningful edge cases, especially for:

- Empty input
- Missing files
- Invalid paths
- Invalid configuration
- Malformed structured output
- Boundary values
- Encoding issues
- Unexpected external responses

---

## 17. Async Code

Use asynchronous programming when it provides a concrete benefit, particularly
for I/O-bound operations.

Do not make functions asynchronous without reason.

Async functions should be used consistently through the relevant call chain.

Avoid blocking operations inside asynchronous functions when practical.

Example:

```python
async def extract_metadata(...) -> ExtractionResult:
    ...
```

Clearly document externally relevant asynchronous behavior when necessary.

---

## 18. File I/O

Always specify text encodings when reading or writing text files.

Prefer:

```python
path.read_text(encoding="utf-8")
```

rather than relying on platform-dependent defaults.

Use context managers where required.

Avoid unnecessary filesystem writes.

When output files are generated, make their purpose and location predictable.

---

## 19. Data Models

Prefer explicit structured models over loosely structured dictionaries when
data has stable semantics.

For example, prefer:

```python
class DocumentMetadata(BaseModel):
    title: str
    keywords: list[str]
```

over passing arbitrary dictionaries across many layers when the schema is known.

Use dictionaries when the data is genuinely dynamic or schema definition would
not improve the design.

---

## 20. Architecture

Keep responsibilities separated.

As the project grows, avoid placing all behavior in a single module.

Potential responsibilities may include:

```text
src/
├── extraction/
├── grounding/
├── models/
├── prompts/
├── evaluation/
├── configuration/
└── utilities/
```

This is illustrative rather than mandatory.

Do not create empty architectural layers merely because they appear clean on a
diagram.

Architecture should emerge from actual responsibilities in the project.

### 20.1 Separation of concerns

Where practical, keep the following concerns separate:

- Input/output
- Domain logic
- LLM invocation
- Prompt construction
- Validation
- Configuration
- Evaluation
- Persistence

This improves testing and reproducibility.

### 20.2 Avoid premature abstraction

Do not introduce interfaces, factories, base classes, dependency-injection
frameworks, or generic abstractions before there is a concrete need.

Duplicating a few simple lines can be preferable to introducing an abstraction
that obscures behavior.

### 20.3 Interface and Boundary Documentation

Interfaces that define architectural boundaries are part of the project's
architecture and must be documented accordingly.

This applies to constructs such as:

* Abstract base classes
* `Protocol` definitions
* Public service interfaces
* Repository or storage interfaces
* Provider interfaces
* LLM/model interfaces
* Retrieval interfaces
* Evaluation interfaces
* Adapter boundaries
* Shared schemas that define communication between subsystems
* Other contracts intended to have multiple implementations or consumers

#### Interface documentation requirements

Every architectural interface must document its purpose and contract.

At minimum, the Python module containing the interface must explain:

* Why the interface exists
* Which responsibility or subsystem boundary it represents
* What implementations are expected to provide
* What callers may rely on
* Important inputs and outputs
* Important invariants or behavioral guarantees
* Relevant failure behavior
* Whether implementations may perform I/O or other side effects
* Any assumptions or constraints shared by all implementations

The interface itself and its public methods must also have appropriate
docstrings according to the documentation rules in this file.

Example:

```python
"""Interfaces for document retrieval.

This module defines the boundary between the grounding pipeline and document
retrieval implementations. Retrieval implementations may use local indexes,
vector databases, or external services, but callers interact only through the
`DocumentRetriever` contract.

All implementations must return ranked retrieval results using the shared
`RetrievalResult` schema. Implementations may perform external I/O and should
surface retrieval failures rather than silently returning incomplete results.
"""


class DocumentRetriever(Protocol):
    """Retrieve evidence relevant to a query from a document collection."""

    async def retrieve(
        self,
        query: str,
        limit: int,
    ) -> list[RetrievalResult]:
        """Retrieve the highest-ranked results for a query.

        Args:
            query: Natural-language retrieval query.
            limit: Maximum number of results to return.

        Returns:
            Results ordered from most to least relevant.
        """
        ...
```

#### Separate interface documentation

A separate Markdown document is not required for every interface.

Prefer documentation directly in the Python module when the complete contract
can be clearly described there.

Create additional architectural documentation when an interface:

* Defines a major subsystem boundary
* Is used by several otherwise independent modules
* Has multiple significant implementations
* Requires lifecycle or sequencing rules
* Defines a nontrivial data flow
* Has compatibility or versioning requirements
* Requires diagrams or examples to understand
* Represents an important extension point of the system

Place such documentation in an appropriate location under `docs/`, for example:

```text
docs/
├── architecture.md
├── interfaces/
│   ├── retrieval.md
│   ├── llm_provider.md
│   └── evaluation.md
```

Do not duplicate detailed information unnecessarily between the Python
docstring and the Markdown document.

Use the Python documentation for the executable contract and API semantics.

Use the architectural document for higher-level information such as:

* Why the boundary exists
* Relationships between components
* Data flow
* Lifecycle
* Extension strategy
* Design rationale
* Implementation-independent examples

When separate documentation exists, the interface module should reference it
when useful.

Example:

```python
"""Interfaces for retrieval backends.

See `docs/interfaces/retrieval.md` for the architectural role, data flow, and
extension model of the retrieval subsystem.
"""
```

#### Interface implementation documentation

Concrete implementations should document behavior that differs from or extends
the general interface contract.

Do not repeat the complete interface documentation in every implementation.

For example, an implementation should document relevant details such as:

* External service used
* Persistence mechanism
* Retry behavior
* Caching
* Performance characteristics
* Provider-specific limitations
* Additional failure modes

#### Interface changes

Treat architectural interfaces as contracts.

When modifying an interface:

1. Inspect all known implementations.
2. Inspect all known callers.
3. Determine whether the change is backward compatible.
4. Update the interface documentation.
5. Update separate architectural documentation when present.
6. Update implementations and tests.
7. Update shared schemas when necessary.

Do not change an architectural interface casually merely to simplify one
implementation.


---

## 21. Reproducibility

Reproducibility is particularly important for experiments involving LLMs.

Where relevant, preserve enough information to identify:

- Input data
- Code version
- Prompt version
- Model
- Model provider
- Model configuration
- Output schema
- Evaluation configuration
- Experiment parameters

Do not assume that a model name alone is sufficient to reproduce an experiment.

If external models can change without version guarantees, document that
limitation.

---

## 22. Research Code

Research code should still be engineered carefully.

Temporary exploratory scripts are acceptable, but code that becomes part of the
main pipeline should be cleaned up and documented.

Distinguish between:

- Production/project source code
- Experiments
- One-off analysis scripts
- Tests
- Evaluation tools

Avoid allowing exploratory scripts to become undocumented dependencies of the
main system.

---

## 23. Security

Never expose secrets.

Validate untrusted external inputs where appropriate.

Be particularly careful with:

- File paths
- Shell commands
- Deserialization
- API responses
- User-provided content
- LLM-generated content

Do not execute LLM-generated commands or code without explicit validation and a
clear reason.

Avoid shell invocation when a direct Python API is safer and simpler.

If shell commands are necessary, avoid constructing them through unsafe string
concatenation.

---

## 24. External APIs

External API integrations should clearly define:

- Required configuration
- Inputs
- Outputs
- Failure modes
- Retry behavior where relevant
- Timeouts where relevant

Do not assume network calls always succeed.

Use reasonable timeout behavior.

Retries should be bounded.

Avoid retrying errors that are clearly permanent.

---

## 25. CLI Design

Command-line interfaces should provide:

- Clear argument names
- Useful help text
- Meaningful validation
- Appropriate exit behavior
- Actionable error messages

Use `argparse`, Typer, Click, or another project-approved approach consistently.

Do not silently reinterpret invalid user input.

---

## 26. Public API Stability

Treat publicly used functions, classes, command-line options, data formats, and
configuration names as interfaces.

Do not change them unnecessarily.

When changing an existing interface:

- Update all call sites.
- Update tests.
- Update documentation.
- Consider backward compatibility when relevant.

---

## 27. Git and Commit Guidelines

AI coding agents must create a local Git commit for completed repository changes
unless the user explicitly instructs them not to commit, the work is incomplete or broken,
or committing would include unrelated pre-existing changes that cannot safely be separated.

Creating commits is part of the normal development workflow.

### 27.1 Commit completed work

When an agent makes source-code, test, configuration, or documentation changes,
it must create a Git commit once the requested unit of work is complete and verified.

Do not create a commit for:

* Tasks that do not modify repository files
* Incomplete or knowingly broken work
* Changes that have not been reasonably verified
* Changes the user explicitly asked not to commit

Prefer one logical commit per cohesive change.

Do not create a commit after every small edit.

If a task contains multiple genuinely independent changes, separate commits may
be appropriate.

### 27.2 Inspect repository state first

Before modifying or committing files, inspect the repository state:

```bash
git status --short
```

Existing user changes must be preserved.

Agents must distinguish between:

* Changes that existed before the current task
* Changes created by the agent during the current task

Never assume every uncommitted file belongs to the agent.

### 27.3 Never discard unrelated changes

Do not discard, overwrite, revert, reset, or commit unrelated existing changes.

In particular, do not use destructive commands such as:

```bash
git reset --hard
git checkout -- .
git restore .
git clean -fd
```

unless the user explicitly requests the operation and its consequences are
understood.

Do not modify or amend existing commits unless explicitly requested.

### 27.4 Review changes before committing

Before staging or committing, inspect the relevant changes.

Use commands such as:

```bash
git status --short
git diff
git diff --stat
```

After staging, inspect the staged changes:

```bash
git diff --cached
```

The staged diff must contain only changes intended for the current commit.

### 27.5 Stage only relevant files

Do not blindly stage the entire repository when unrelated changes may exist.

Avoid:

```bash
git add -A
git add .
```

when the working tree contains changes unrelated to the current task.

Prefer explicitly staging the files associated with the task:

```bash
git add src/example.py tests/test_example.py
```

If a file contains both pre-existing user changes and agent changes, take care
not to commit the user's unrelated changes. Use selective staging when
necessary.

### 27.6 Verify before committing

Before creating a commit, run the relevant quality checks when available.

For Python changes, this normally includes:

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
```

Use narrower tests when running the entire test suite would be inappropriate.

Do not claim a check passed unless it was actually executed successfully.

If a check fails because of changes introduced by the current task, fix the
problem before committing.

If a check fails for a pre-existing or unrelated reason, do not silently modify
unrelated code merely to make the check pass. Report the issue appropriately.

### 27.7 Commit message format

Use concise, descriptive commit messages.

Prefer Conventional Commit-style prefixes:

```text
feat: add document retrieval interface
fix: preserve PDF block reading order
docs: document retrieval interface contract
refactor: separate prompt construction from extraction
test: add extraction schema validation tests
chore: configure Ruff documentation checks
```

Use the following common prefixes:

* `feat:` — new functionality
* `fix:` — bug fix
* `docs:` — documentation-only change
* `refactor:` — code restructuring without intended behavior change
* `test:` — test-only change
* `chore:` — tooling, configuration, or maintenance
* `perf:` — performance improvement

Commit messages should describe the change rather than the agent's actions.

Prefer:

```text
feat: add structured paper extraction
```

instead of:

```text
agent updated some extraction files
```

Keep the subject concise and use the imperative style where practical.

For substantial changes, a commit body may explain:

* Why the change was necessary
* Important implementation decisions
* Relevant limitations
* Migration implications

### 27.8 Create the commit

A typical agent commit workflow is:

```bash
git status --short
git diff
uv run ruff format .
uv run ruff check .
uv run pytest
git add <relevant-files>
git diff --cached
git commit -m "feat: describe the change"
git status --short
```

The exact validation commands depend on the files changed.

### 27.9 Respect Git hooks

Do not bypass repository Git hooks merely to force a commit through.

Do not use:

```bash
git commit --no-verify
```

unless explicitly instructed and there is a justified reason.

If a pre-commit or commit-message hook fails because of the current changes,
address the underlying problem and retry the commit.

### 27.10 Do not push automatically

Creating a local commit and publishing it to a remote repository are separate
operations.

Agents may create local commits as part of normal task completion.

Agents must **not** run:

```bash
git push
```

unless the user explicitly requests or authorizes pushing the changes.

This rule also applies to:

* Force pushes
* Creating remote branches
* Creating tags on the remote
* Opening or modifying merge requests through remote APIs

Never force-push unless explicitly requested and the consequences are
understood.

### 27.11 Do not create branches unnecessarily

Work on the currently checked-out branch unless:

* The user explicitly requests a new branch
* The task's workflow explicitly requires one
* Repository-specific instructions define another policy

Do not create arbitrary agent-specific branches without reason.

### 27.12 Report the commit

After successfully committing, report the commit hash and subject.

For example:

```text
Created commit:

a1b2c3d feat: add document retrieval interface
```

If unrelated uncommitted changes remain in the working tree, mention that they
were intentionally left untouched.

### 27.13 Never misrepresent Git operations

Do not claim that changes were:

* Committed
* Pushed
* Tested
* Merged
* Tagged

unless the corresponding operation actually completed successfully.

---

## 28. Code Review Checklist

Before considering a code change complete, check:

### Correctness

- Does the implementation satisfy the requested behavior?
- Are edge cases handled appropriately?
- Are assumptions valid?

### Scope

- Are changes limited to what is necessary?
- Was unrelated behavior preserved?

### Types

- Are function parameters typed?
- Are return values typed?
- Are complex data structures represented clearly?

### Documentation

- Are public APIs documented?
- Are nontrivial private functions documented?
- Are docstrings Google-style?
- Do docstrings describe semantics rather than repeat types?
- Are assumptions and limitations documented?
- Does documentation match the implementation?

### Comments

- Do comments explain non-obvious reasoning?
- Are redundant comments removed?

### Errors

- Are exceptions meaningful?
- Are errors handled at the correct level?
- Are failures being silently suppressed?

### Testing

- Are relevant tests present?
- Are important edge cases covered?
- Are external services mocked in unit tests?

### LLM behavior

When applicable:

- Is the prompt clear?
- Is structured output used appropriately?
- Is the schema documented?
- Is prompt versioning needed?
- Are assumptions about model behavior explicit?
- Is evaluation reproducible?

### Security

- Are secrets excluded?
- Is untrusted input handled safely?
- Are logs free of credentials?

### Quality tools

When configured, run:

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
```

Resolve relevant failures before considering the task complete.

---

## 29. Rules for AI Coding Agents

AI coding agents working in this repository must follow these rules.

### 29.1 Before modifying code

Before making significant changes:

1. Read this `AGENTS.md`.
2. Inspect the relevant existing source code.
3. Inspect relevant tests.
4. If the task affects an architectural interface, inspect its module
   documentation and any corresponding documentation under `docs/interfaces/`.
5. Inspect nearby modules to understand existing conventions.
6. Check `pyproject.toml` and other project configuration when relevant.
7. Preserve the existing architecture unless the requested task requires a
   change.

Do not assume conventions that can be determined from the repository.

### 29.2 While modifying code

Agents should:

- Make the smallest coherent change that solves the task.
- Follow existing naming and architecture.
- Use type hints.
- Add appropriate documentation.
- Preserve unrelated behavior.
- Add or update tests when behavior changes.
- Use existing utilities instead of duplicating functionality unnecessarily.
- Keep dependencies minimal.
- Keep LLM prompts and schemas synchronized.
- Avoid speculative abstractions.

### 29.3 Do not invent APIs

Do not invent:

- Library functions
- Configuration options
- Environment variables
- API parameters
- Project modules
- External service behavior

Verify usage from the installed dependency, repository, or authoritative
documentation when necessary.

### 29.4 Do not silently change behavior

If a task is documentation-only, do not modify application behavior.

If a task is refactoring-only, preserve observable behavior unless explicitly
instructed otherwise.

If behavior must change, make that change explicit and update relevant tests and
documentation.

### 29.5 Documentation audits

When asked to document or review code, check for:

- Missing module docstrings
- Missing public docstrings
- Missing documentation for nontrivial private functions
- Inconsistent Google-style formatting
- Undocumented parameters
- Undocumented return semantics
- Meaningful undocumented exceptions
- Undocumented side effects
- Undocumented assumptions
- Undocumented constraints or units
- Overstated guarantees
- Documentation that disagrees with implementation
- Redundant comments
- Vague Pydantic field descriptions
- Undocumented LLM prompt behavior
- Undocumented output schemas
- Undocumented model assumptions

Do not invent behavior merely to make documentation more complete.

If implementation behavior is ambiguous, document only what can be established
from the code or explicitly flag the ambiguity.

### 29.6 Prefer repository context over generic conventions

These guidelines define project defaults.

When existing project-specific behavior intentionally differs from a generic
best practice, understand the reason before changing it.

Repository configuration and explicit task requirements take precedence over
generic recommendations.

### 29.7 Verify work

After modifying Python code, run appropriate project checks when available.

Typically:

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
```

If the complete test suite is inappropriate or unavailable, run the narrowest
relevant tests and clearly identify what was verified.

Do not claim that tests or commands passed unless they were actually executed.

---

## 30. Documentation Prompt for AI Agents

When performing a documentation-focused task, follow this specification:

```text
Document the Python code according to the project's documentation standard.

Documentation convention:
- Follow PEP 257.
- Use Google-style docstrings.
- Use triple double quotes for Python docstrings.
- All public modules, classes, methods, and functions must have docstrings.
- Non-public functions require docstrings when their behavior, assumptions,
  side effects, failure modes, algorithm, I/O, or domain semantics are not
  obvious.
- Tiny self-explanatory private helpers may use a one-line docstring or no
  docstring.

For function and method docstrings:
1. Begin with a concise summary.
2. Add a longer description only when it provides information not obvious from
   the implementation or signature.
3. Use Args, Returns/Yields, Raises, and Examples sections when applicable.
4. Describe parameter semantics, constraints, units, and accepted forms.
5. Do not repeat Python type annotations in prose.
6. Document meaningful exceptions but not irrelevant internal implementation
   exceptions.
7. Document externally observable side effects such as filesystem access,
   network requests, state mutation, logging, caching, or database changes when
   relevant.
8. State important assumptions and limitations.
9. Do not claim guarantees stronger than the implementation provides.
10. Do not describe obvious implementation steps line by line.

For comments:
- Explain WHY an implementation choice exists, not WHAT an obvious line does.
- Remove comments that merely restate the code.
- Preserve comments explaining workarounds, compatibility issues, numerical
  assumptions, algorithmic choices, security constraints, or other non-obvious
  behavior.

For LLM-related code:
- Clearly document the purpose of important prompts.
- Identify the expected structured output schema.
- Document important model assumptions and nondeterministic behavior where
  relevant.
- Document prompt variables and their semantics.
- Keep prompt behavior and schema descriptions synchronized.
- Do not invent behavior that cannot be inferred from the implementation.

For Pydantic models:
- Give significant models concise docstrings.
- Give fields meaningful descriptions when their semantics or constraints are
  not completely obvious from the field name and type.
- State units, ranges, allowed values, and interpretation where applicable.

Do not change program behavior while performing documentation-only work.

If existing documentation contradicts the implementation, update the
documentation to accurately describe the implementation and identify material
behavior/documentation discrepancies when relevant.
```

---

## 31. Documentation Audit Prompt

When auditing existing documentation, use the following criteria:

```text
Audit the documentation in the provided code.

Check for:
- Missing public docstrings
- Missing documentation for nontrivial private functions
- Inconsistent Google-style formatting
- Undocumented parameter semantics
- Undocumented return semantics
- Undocumented meaningful exceptions
- Undocumented side effects
- Undocumented assumptions
- Undocumented units or constraints
- Claims that overpromise compared with the implementation
- Stale documentation that disagrees with the code
- Redundant comments that merely restate code
- Implementation details that should instead be described semantically
- Undocumented LLM prompts
- Undocumented output schemas
- Undocumented model assumptions
- Undocumented prompt variables
- Vague Pydantic Field descriptions

Do not change functionality during a documentation-only audit.

Do not invent behavior.

Documentation must describe the actual implementation.
```

---

## 32. Source of Truth

This `AGENTS.md` is the canonical repository-level source of development
instructions for AI coding agents.

If agent-specific instruction files are added, such as:

```text
CLAUDE.md
GEMINI.md
.github/copilot-instructions.md
```

they should avoid duplicating the full guidelines whenever possible.

Instead, they should direct the relevant agent to follow this file.

This avoids multiple copies of the same rules becoming inconsistent over time.

More specialized `AGENTS.md` files may be added to subdirectories if particular
parts of the project require additional rules.

For example:

```text
AGENTS.md
src/
├── AGENTS.md
├── extraction/
└── grounding/

tests/
└── AGENTS.md
```

Subdirectory-specific instructions should extend or specialize these global
rules rather than unnecessarily duplicate them.

---

## 33. Final Principle

The purpose of these guidelines is not to maximize ceremony.

The preferred solution is the simplest implementation that is:

- Correct
- Explicit
- Understandable
- Testable
- Well documented
- Reproducible
- Consistent with the rest of the project

When in doubt, favor clarity and correctness over cleverness.