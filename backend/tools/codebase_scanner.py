"""
codebase_scanner.py — Smart existing codebase analyser.

Logic:
1. Read CODEBASE.md (if present) and parse which sections are covered.
2. For each MISSING section, scan the actual source tree to extract that info.
3. Return a compact supplement dict the Architect injects into its context.

This avoids re-scanning things the developer already documented,
and avoids wasting tokens sending the full source to the LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
#  What CODEBASE.md sections we track
# ─────────────────────────────────────────────────────────────────────────────

EXPECTED_SECTIONS = {
    "architecture":  ["architecture", "mvvm", "viper", "tca", "clean architecture", "pattern"],
    "file_map":      ["file structure", "folder structure", "directory", "source tree"],
    "types":         ["class", "struct", "protocol", "actor", "enum", "viewmodel", "service"],
    "conventions":   ["convention", "naming", "style", "swiftlint", "coding standard"],
    "dependencies":  ["dependency", "spm", "cocoapods", "framework", "package", "pod"],
    "testing":       ["test", "xctest", "swift testing", "mock", "fixture"],
}


@dataclass
class CodebaseContext:
    """Compact summary of an existing codebase, ready to inject into agent prompts."""
    source: str                             # "codebase.md" | "scan" | "mixed"
    architecture_notes: str = ""
    file_map: list[str] = field(default_factory=list)       # relative paths
    types: list[dict] = field(default_factory=list)         # {name, kind, file, public_api}
    conventions: str = ""
    dependencies: list[str] = field(default_factory=list)
    testing_notes: str = ""
    gaps_filled: list[str] = field(default_factory=list)    # which gaps were auto-scanned
    warnings: list[str] = field(default_factory=list)

    def to_prompt_str(self) -> str:
        """Compact string for injection into Architect/Coder system prompts."""
        parts = ["EXISTING CODEBASE CONTEXT:"]

        if self.architecture_notes:
            parts.append(f"\nArchitecture:\n{self.architecture_notes}")

        if self.types:
            parts.append("\nExisting types (DO NOT redefine these):")
            for t in self.types[:60]:  # cap to avoid token explosion
                api = f" — {', '.join(t['public_api'][:3])}" if t.get("public_api") else ""
                parts.append(f"  {t['kind']} {t['name']} ({t['file']}){api}")
            if len(self.types) > 60:
                parts.append(f"  ... and {len(self.types) - 60} more")

        if self.file_map:
            parts.append("\nExisting files (modify, don't recreate):")
            for f in self.file_map[:40]:
                parts.append(f"  {f}")
            if len(self.file_map) > 40:
                parts.append(f"  ... and {len(self.file_map) - 40} more")

        if self.dependencies:
            parts.append(f"\nDependencies: {', '.join(self.dependencies)}")

        if self.conventions:
            parts.append(f"\nConventions:\n{self.conventions}")

        if self.testing_notes:
            parts.append(f"\nTesting:\n{self.testing_notes}")

        if self.gaps_filled:
            parts.append(f"\n[Auto-scanned to fill gaps: {', '.join(self.gaps_filled)}]")

        if self.warnings:
            for w in self.warnings:
                parts.append(f"⚠ {w}")

        return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  Scanner
# ─────────────────────────────────────────────────────────────────────────────

class CodebaseScanner:
    """
    Reads CODEBASE.md first. Only scans source files for sections
    that are missing or thin in CODEBASE.md.
    """

    # Swift type declaration regex
    _SWIFT_TYPE = re.compile(
        r"^(?:public\s+|open\s+|internal\s+|private\s+|fileprivate\s+)?"
        r"(?:final\s+)?(?:@MainActor\s+)?"
        r"(?P<kind>class|struct|enum|protocol|actor|extension)\s+"
        r"(?P<name>[A-Z][A-Za-z0-9_]*)",
        re.MULTILINE,
    )
    _SWIFT_FUNC = re.compile(
        r"^\s+(?:public|open)\s+(?:func|var|let)\s+(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)",
        re.MULTILINE,
    )

    # Files / dirs to always skip
    _SKIP_DIRS = {
        ".git", ".build", "DerivedData", "Pods", ".swiftpm",
        "node_modules", "__pycache__", ".venv", "build", "dist",
    }
    _SKIP_EXTENSIONS = {".pyc", ".o", ".a", ".dylib", ".png", ".jpg",
                        ".jpeg", ".pdf", ".xcassets", ".storyboard"}

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.codebase_md = self.project_path / "CODEBASE.md"

    # ── Public entry point ────────────────────────────────────────────────

    def scan(self) -> CodebaseContext:
        """
        Main entry. Returns CodebaseContext with CODEBASE.md content
        supplemented by source scan for any missing sections.
        """
        md_content = ""
        if self.codebase_md.exists():
            md_content = self.codebase_md.read_text(encoding="utf-8", errors="replace")

        covered = self._detect_covered_sections(md_content)
        missing = [s for s in EXPECTED_SECTIONS if s not in covered]

        ctx = CodebaseContext(
            source="codebase.md" if not missing else "mixed",
            architecture_notes=self._extract_md_section(md_content, "architecture"),
            conventions=self._extract_md_section(md_content, "convention", "style", "naming"),
            testing_notes=self._extract_md_section(md_content, "test"),
        )

        # Parse dependencies from CODEBASE.md
        ctx.dependencies = self._extract_dependencies_from_md(md_content)

        if not missing:
            print("[SCANNER] CODEBASE.md covers all sections — skipping source scan")
            return ctx

        print(f"[SCANNER] CODEBASE.md missing sections: {missing} — scanning source tree")

        # Only scan what's missing
        swift_files = self._find_swift_files()
        if not swift_files:
            ctx.warnings.append("No Swift files found in project — is --project pointing at the right directory?")
            return ctx

        if "file_map" in missing:
            ctx.file_map = [str(f.relative_to(self.project_path)) for f in swift_files]
            ctx.gaps_filled.append("file_map")

        if "types" in missing:
            ctx.types = self._extract_types(swift_files)
            ctx.gaps_filled.append("types")

        if "architecture" in missing and not ctx.architecture_notes:
            ctx.architecture_notes = self._infer_architecture(swift_files)
            ctx.gaps_filled.append("architecture")

        if "dependencies" in missing and not ctx.dependencies:
            ctx.dependencies = self._find_dependencies()
            ctx.gaps_filled.append("dependencies")

        if "testing" in missing and not ctx.testing_notes:
            ctx.testing_notes = self._infer_testing(swift_files)
            ctx.gaps_filled.append("testing")

        return ctx

    # ── CODEBASE.md parsing ───────────────────────────────────────────────

    def _detect_covered_sections(self, md: str) -> set[str]:
        """Return set of section keys that are substantively covered in CODEBASE.md."""
        md_lower = md.lower()
        covered = set()
        for section, keywords in EXPECTED_SECTIONS.items():
            # Consider covered if ≥2 keywords present and section has ≥50 chars of content
            matches = sum(1 for kw in keywords if kw in md_lower)
            if matches >= 2 and len(md) > 50:
                covered.add(section)
        return covered

    def _extract_md_section(self, md: str, *keywords: str) -> str:
        """Extract the first markdown section whose heading matches any keyword."""
        lines = md.split("\n")
        result: list[str] = []
        in_section = False
        for line in lines:
            heading = line.lstrip("#").strip().lower()
            if line.startswith("#"):
                if any(kw in heading for kw in keywords):
                    in_section = True
                    result = []
                elif in_section:
                    break  # next section started
            elif in_section:
                result.append(line)
        return "\n".join(result).strip()[:1500]  # cap at 1500 chars

    def _extract_dependencies_from_md(self, md: str) -> list[str]:
        deps = []
        for line in md.split("\n"):
            # Look for common dependency patterns
            m = re.search(r"[`\"]([A-Za-z][A-Za-z0-9_\-]+)[`\"]", line)
            if m and any(kw in line.lower() for kw in ["import", "package", "pod", "spm", "depend"]):
                deps.append(m.group(1))
        return list(dict.fromkeys(deps))[:20]  # deduplicate, cap at 20

    # ── Source tree scanning ──────────────────────────────────────────────

    def _find_swift_files(self) -> list[Path]:
        files = []
        for path in self.project_path.rglob("*.swift"):
            # Skip directories in skip list
            if any(skip in path.parts for skip in self._SKIP_DIRS):
                continue
            if path.suffix in self._SKIP_EXTENSIONS:
                continue
            files.append(path)
        return sorted(files)

    def _extract_types(self, swift_files: list[Path]) -> list[dict]:
        types = []
        for fpath in swift_files:
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            rel = str(fpath.relative_to(self.project_path))
            for m in self._SWIFT_TYPE.finditer(content):
                kind = m.group("kind")
                name = m.group("name")
                if kind == "extension":
                    continue  # skip extensions, they're noise
                # Extract public API (first 3 public funcs/vars)
                public_api = [
                    fm.group("name")
                    for fm in self._SWIFT_FUNC.finditer(content)
                ][:3]
                types.append({
                    "kind": kind,
                    "name": name,
                    "file": rel,
                    "public_api": public_api,
                })
        return types

    def _infer_architecture(self, swift_files: list[Path]) -> str:
        """Guess architecture from file/type naming patterns."""
        names = [f.stem for f in swift_files]
        patterns = {
            "MVVM": sum(1 for n in names if "ViewModel" in n),
            "VIPER": sum(1 for n in names if any(x in n for x in ["Presenter", "Interactor", "Router", "Entity"])),
            "TCA": sum(1 for n in names if "Reducer" in n or "Store" in n),
            "MVC":  sum(1 for n in names if "Controller" in n or "ViewController" in n),
        }
        dominant = max(patterns, key=patterns.get)
        score = patterns[dominant]
        if score == 0:
            return "Architecture not detected — no strong naming pattern found."
        return (
            f"Detected pattern: {dominant} ({score} matching files). "
            f"All pattern counts: {patterns}."
        )

    def _find_dependencies(self) -> list[str]:
        """Extract package names from Package.swift, Podfile, or .xcodeproj."""
        deps = []
        # Swift Package Manager
        pkg_swift = self.project_path / "Package.swift"
        if pkg_swift.exists():
            content = pkg_swift.read_text(errors="replace")
            for m in re.finditer(r'\.package\([^)]*url:\s*"[^"]+/([^"/.]+?)(?:\.git)?"\s*', content):
                deps.append(m.group(1))

        # CocoaPods
        podfile = self.project_path / "Podfile"
        if podfile.exists():
            content = podfile.read_text(errors="replace")
            for m in re.finditer(r"pod\s+['\"]([^'\"]+)['\"]", content):
                deps.append(m.group(1))

        return list(dict.fromkeys(deps))[:30]

    def _infer_testing(self, swift_files: list[Path]) -> str:
        test_files = [f for f in swift_files if "Test" in f.stem or "Spec" in f.stem]
        if not test_files:
            return "No test files found."
        frameworks = set()
        for fpath in test_files[:10]:
            try:
                content = fpath.read_text(errors="replace")
                if "import Testing" in content or "@Test" in content:
                    frameworks.add("Swift Testing")
                if "import XCTest" in content:
                    frameworks.add("XCTest")
                if "XCUIApplication" in content:
                    frameworks.add("XCUITest")
            except Exception:
                pass
        return (
            f"{len(test_files)} test files found. "
            f"Frameworks in use: {', '.join(sorted(frameworks)) or 'unknown'}."
        )
