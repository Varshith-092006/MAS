"""Shared task requirement text processing and CLI contract formatting.

Ensures both MAS and ChatDev receive byte-for-byte identical requirement text,
including standard entry-point CLI contract expectations.
"""

CLI_CONTRACT_SUFFIX: str = (
    "The program must run with 'python main.py' without crashing and must exit with code 0 when run with --help."
)


def get_augmented_requirement(description: str) -> str:
    """Appends the shared CLI contract suffix to requirement text identically for all systems."""
    desc = (description or "").strip()
    if not desc:
        return CLI_CONTRACT_SUFFIX
    # If the suffix is already present, do not duplicate
    if CLI_CONTRACT_SUFFIX in desc:
        return desc
    return f"{desc}\n\n{CLI_CONTRACT_SUFFIX}"
