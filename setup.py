"""Build portable resources from the authoritative repository files."""

from pathlib import Path
import os
import re
import sys

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from release_resources import bundle_sources, check_build_tree, runtime_data_sources


class BuildResources(build_py):
    def run(self):
        check_build_tree(ROOT, Path(self.build_lib) / "minecode_runtime")
        super().run()
        target = Path(self.build_lib) / "minecode_runtime" / "data"
        target.mkdir(parents=True, exist_ok=True)
        runtime_sources = runtime_data_sources(ROOT)
        runtime_destinations = {source.resolve(): target / source.name for source in runtime_sources}
        for source in runtime_sources:
            self.copy_file(str(source), str(target / source.name))
        for source in bundle_sources(ROOT):
            destination = target / "bundle" / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            self.copy_file(str(source), str(destination))
            if source.suffix == ".md":
                # Repository source links should open the installed runtime offline.
                def rebase(match):
                    link = match.group(1)
                    resolved = (source.parent / link).resolve()
                    module_root = ROOT / "src" / "minecode_runtime"
                    if resolved.is_relative_to(module_root):
                        installed = Path(self.build_lib) / "minecode_runtime" / resolved.relative_to(module_root)
                        return "](" + Path(os.path.relpath(installed, destination.parent)).as_posix() + ")"
                    if resolved in runtime_destinations:
                        return (
                            "]("
                            + Path(os.path.relpath(runtime_destinations[resolved], destination.parent)).as_posix()
                            + ")"
                        )
                    return match.group(0)

                destination.write_text(
                    re.sub(r"\]\(([^)]+)\)", rebase, source.read_text(encoding="utf-8")), encoding="utf-8"
                )


setup(cmdclass={"build_py": BuildResources})
