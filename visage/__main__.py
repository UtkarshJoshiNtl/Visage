"""Visage entry point."""
import sys
from visage import __version__

def main() -> None:
    print(f"Visage v{__version__} — System Performance Dashboard")
    print("Phase 1: scaffold complete. Dashboard coming next.")
    sys.exit(0)

if __name__ == "__main__":
    main()
