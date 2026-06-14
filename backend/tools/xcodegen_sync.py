"""
xcodegen_sync.py — Register new Swift files with the Xcode project by patching project.pbxproj.

After the Coder writes files to disk:
1. Find the .xcodeproj in the project directory.
2. Parse project.pbxproj to find the main target and its source build phase.
3. Add new Swift files as PBXFileReference + PBXBuildFile entries.
4. Insert them into the correct PBXGroup based on their path.

No xcodegen or project.yml required — works with any existing .xcodeproj.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Optional

INFO_COLOR = "\033[94m"
WARN_COLOR = "\033[93m"
OK_COLOR   = "\033[92m"
RESET      = "\033[0m"


def _make_id(seed: str) -> str:
    """Generate a deterministic 24-char Xcode-style ID from a seed string."""
    h = hashlib.md5(seed.encode()).hexdigest().upper()
    return h[:24]


class XcodegenSync:
    """
    Patches project.pbxproj to register new Swift files into the Xcode project.
    Call sync(new_files) after each story's files are written.
    """

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self._pbxproj_path: Optional[Path] = None

    # ── Public API ────────────────────────────────────────────────────────

    def sync(self, new_files: list[str]) -> bool:
        """
        Register new Swift files into the .xcodeproj.
        Returns True if successful.
        """
        swift_files = [f for f in new_files if f.endswith(".swift")]
        if not swift_files:
            return True

        pbxproj = self._find_pbxproj()
        if not pbxproj:
            print(f"{WARN_COLOR}[XCODEPROJ] No .xcodeproj found in {self.project_path}{RESET}")
            return False

        try:
            content = pbxproj.read_text(encoding="utf-8")
            original = content

            for rel_path in swift_files:
                abs_path = self.project_path / rel_path
                if not abs_path.exists():
                    print(f"{WARN_COLOR}[XCODEPROJ] File not found on disk: {rel_path}{RESET}")
                    continue

                content = self._add_file_to_pbxproj(content, rel_path)

            if content != original:
                pbxproj.write_text(content, encoding="utf-8")
                print(f"{OK_COLOR}[XCODEPROJ] project.pbxproj updated with {len(swift_files)} file(s) ✓{RESET}")
            return True

        except Exception as e:
            print(f"{WARN_COLOR}[XCODEPROJ] Failed to patch project.pbxproj: {e}{RESET}")
            return False

    def ensure_project_yml(self) -> bool:
        """No-op — we don't use project.yml anymore."""
        return True

    # ── pbxproj patching ──────────────────────────────────────────────────

    def _add_file_to_pbxproj(self, content: str, rel_path: str) -> str:
        """Add a single Swift file to the pbxproj content."""
        filename = Path(rel_path).name

        # Generate stable IDs based on path
        file_ref_id = _make_id(f"fileref:{rel_path}")
        build_file_id = _make_id(f"buildfile:{rel_path}")

        # Skip if already registered
        if file_ref_id in content:
            print(f"{INFO_COLOR}[XCODEPROJ] Already registered: {rel_path}{RESET}")
            return content

        # 1. Add PBXFileReference
        file_ref = (
            f"\t\t{file_ref_id} = "
            f"{{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; "
            f"name = {filename}; path = {rel_path}; sourceTree = \"<group>\"; }};"
        )
        content = self._insert_into_section(content, "PBXFileReference", file_ref)

        # 2. Add PBXBuildFile
        build_file = (
            f"\t\t{build_file_id} = "
            f"{{isa = PBXBuildFile; fileRef = {file_ref_id} /* {filename} */; }};"
        )
        content = self._insert_into_section(content, "PBXBuildFile", build_file)

        # 3. Add to main target's Sources build phase
        content = self._add_to_sources_phase(content, build_file_id, filename)

        # 4. Add to the appropriate PBXGroup
        content = self._add_to_group(content, file_ref_id, rel_path, filename)

        print(f"{INFO_COLOR}[XCODEPROJ] Registered: {rel_path}{RESET}")
        return content

    def _insert_into_section(self, content: str, section: str, new_entry: str) -> str:
        """Insert a new entry into a /* Begin SECTION section */ block."""
        marker = f"/* Begin {section} section */"
        idx = content.find(marker)
        if idx == -1:
            return content
        insert_at = content.find("\n", idx) + 1
        return content[:insert_at] + new_entry + "\n" + content[insert_at:]

    def _add_to_sources_phase(self, content: str, build_file_id: str, filename: str) -> str:
        """Add a build file reference to the first PBXSourcesBuildPhase files list."""
        # Find Sources build phase files array
        pattern = r"(isa = PBXSourcesBuildPhase;.*?files = \()(.*?)(\);)"
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return content

        files_section = match.group(2)
        new_entry = f"\n\t\t\t\t{build_file_id} /* {filename} in Sources */,"
        new_files_section = files_section.rstrip() + new_entry + "\n\t\t\t"

        return content[:match.start(2)] + new_files_section + content[match.end(2):]

    def _add_to_group(self, content: str, file_ref_id: str, rel_path: str, filename: str) -> str:
        """Add the file reference to the most appropriate PBXGroup."""
        # Try to find a group matching the parent directory
        parent_dir = str(Path(rel_path).parent)

        # Look for a group whose path matches the parent directory name
        parent_name = Path(rel_path).parent.name
        if parent_name and parent_name != ".":
            pattern = rf'(path = {re.escape(parent_name)};.*?children = \()(.*?)(\);)'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                new_entry = f"\n\t\t\t\t{file_ref_id} /* {filename} */,"
                new_children = match.group(2).rstrip() + new_entry + "\n\t\t\t"
                return content[:match.start(2)] + new_children + content[match.end(2):]

        # Fall back: add to the main project group (first group with many children)
        # Find the group that contains the most files — likely the main source group
        pattern = r'(/\* [A-Za-z]+ \*/ = \{[^}]*isa = PBXGroup;[^}]*children = \()(.*?)(\);)'
        matches = list(re.finditer(pattern, content, re.DOTALL))
        if matches:
            # Pick the group with the most children entries
            best = max(matches, key=lambda m: m.group(2).count("/*"))
            new_entry = f"\n\t\t\t\t{file_ref_id} /* {filename} */,"
            new_children = best.group(2).rstrip() + new_entry + "\n\t\t\t"
            return content[:best.start(2)] + new_children + content[best.end(2):]

        return content

    # ── Helpers ───────────────────────────────────────────────────────────

    def _find_pbxproj(self) -> Optional[Path]:
        if self._pbxproj_path and self._pbxproj_path.exists():
            return self._pbxproj_path
        for xcodeproj in self.project_path.glob("*.xcodeproj"):
            pbxproj = xcodeproj / "project.pbxproj"
            if pbxproj.exists():
                self._pbxproj_path = pbxproj
                return pbxproj
        return None
