#!/usr/bin/env python3
import os
import subprocess
import fnmatch
import difflib
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Set, List


@dataclass
class FileComparison:
    path: str
    status: str
    similarity_ratio: Optional[float] = None
    additions: int = 0
    deletions: int = 0


class DirectoryDiff:
    def __init__(self):
        self.supported_extensions = {
            ".cpp",
            ".c",
            ".cc",
            ".cxx",
            ".hpp",
            ".h",
            ".hxx",
            ".cu",
            ".cuh",
            ".py",
            ".pyx",
        }

    def should_compare_file(
        self, file_path: str, include: List[str] = None, exclude: List[str] = None
    ) -> bool:
        if Path(file_path).suffix.lower() not in self.supported_extensions:
            return False
        if include and not any(fnmatch.fnmatch(file_path, p) for p in include):
            return False
        if exclude and any(fnmatch.fnmatch(file_path, p) for p in exclude):
            return False
        return True

    def get_file_list(
        self, directory: str, include: List[str] = None, exclude: List[str] = None
    ) -> Set[str]:
        files = set()
        for root, dirs, filenames in os.walk(directory):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in {"__pycache__", "build", "dist"}
            ]

            for filename in filenames:
                file_path = Path(root) / filename
                relative_path = str(file_path.relative_to(directory))
                if self.should_compare_file(relative_path, include, exclude):
                    files.add(relative_path)
        return files

    def is_url(self, path: str) -> bool:
        return path.startswith(("http://", "https://"))

    def clone_repo(self, repo_url: str, target_dir: str) -> str:
        clone_args = ["git", "clone", "--depth", "1"]
        env = None

        if "huggingface.co" in repo_url:
            env = os.environ.copy()
            env["GIT_LFS_SKIP_SMUDGE"] = "1"
            clone_args.extend(["--filter=blob:none"])

        subprocess.run(
            clone_args + [repo_url, target_dir],
            check=True,
            capture_output=True,
            env=env,
        )
        return target_dir

    def resolve_path(self, path: str, subdir: str = "") -> tuple[str, bool]:
        """Returns (resolved_path, is_temp)"""
        if self.is_url(path):
            cache_dir = Path.cwd() / ".repo_cache"
            cache_dir.mkdir(exist_ok=True)

            # Create a safe directory name from the URL
            repo_name = path.split("/")[-1].replace(".git", "")
            if "huggingface.co" in path:
                repo_name = path.split("/")[-2] + "_" + repo_name

            target_dir = cache_dir / repo_name

            if not target_dir.exists():
                cloned_dir = self.clone_repo(path, str(target_dir))
            else:
                cloned_dir = str(target_dir)

            final_path = os.path.join(cloned_dir, subdir) if subdir else cloned_dir
            return final_path, True
        else:
            final_path = os.path.join(path, subdir) if subdir else path
            return final_path, False

    def analyze_files(self, file1: str, file2: str) -> dict:
        try:
            with open(file1, "r", encoding="utf-8") as f1:
                lines1 = f1.readlines()
            with open(file2, "r", encoding="utf-8") as f2:
                lines2 = f2.readlines()
        except Exception:
            return {"similarity_ratio": 0.0, "additions": 0, "deletions": 0}

        differ = difflib.SequenceMatcher(None, lines1, lines2)
        additions = deletions = 0

        for tag, i1, i2, j1, j2 in differ.get_opcodes():
            if tag == "delete":
                deletions += i2 - i1
            elif tag == "insert":
                additions += j2 - j1
            elif tag == "replace":
                deletions += i2 - i1
                additions += j2 - j1

        return {
            "similarity_ratio": differ.ratio(),
            "additions": additions,
            "deletions": deletions,
        }

    def compare_directories(
        self, dir1: str, dir2: str, include: List[str] = None, exclude: List[str] = None
    ) -> dict:
        files1 = self.get_file_list(dir1, include, exclude)
        files2 = self.get_file_list(dir2, include, exclude)
        all_files = files1.union(files2)

        comparisons = []
        identical = different = only_1 = only_2 = 0
        total_similarity = valid_similarities = 0

        for rel_path in sorted(all_files):
            file1_path = Path(dir1) / rel_path
            file2_path = Path(dir2) / rel_path

            if not file1_path.exists():
                comparisons.append(FileComparison(rel_path, "only_in_dir2"))
                only_2 += 1
            elif not file2_path.exists():
                comparisons.append(FileComparison(rel_path, "only_in_dir1"))
                only_1 += 1
            else:
                try:
                    with open(file1_path, "rb") as f1, open(file2_path, "rb") as f2:
                        if f1.read() == f2.read():
                            comparisons.append(
                                FileComparison(rel_path, "identical", 1.0)
                            )
                            identical += 1
                            total_similarity += 1.0
                            valid_similarities += 1
                        else:
                            analysis = self.analyze_files(
                                str(file1_path), str(file2_path)
                            )
                            comp = FileComparison(
                                rel_path,
                                "different",
                                analysis["similarity_ratio"],
                                analysis["additions"],
                                analysis["deletions"],
                            )
                            comparisons.append(comp)
                            different += 1
                            total_similarity += analysis["similarity_ratio"]
                            valid_similarities += 1
                except Exception:
                    comparisons.append(FileComparison(rel_path, "error"))

        avg_similarity = (
            total_similarity / valid_similarities if valid_similarities > 0 else 0
        )

        return {
            "comparisons": comparisons,
            "total_files": len(all_files),
            "identical": identical,
            "different": different,
            "only_in_1": only_1,
            "only_in_2": only_2,
            "avg_similarity": avg_similarity,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Compare directories or repositories",
        epilog="Examples:\n"
        "  Compare local dirs: %(prog)s dir1/ dir2/\n"
        "  Compare repos: %(prog)s https://github.com/user/repo1.git https://github.com/user/repo2.git\n"
        "  With subdirs: %(prog)s repo1/ repo2/ --subdir1 src --subdir2 source",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("source1", help="First directory path or git/huggingface URL")
    parser.add_argument("source2", help="Second directory path or git/huggingface URL")
    parser.add_argument("--subdir1", default="", help="Subdirectory in first source")
    parser.add_argument("--subdir2", default="", help="Subdirectory in second source")
    parser.add_argument("--include", nargs="*", help="Include file patterns")
    parser.add_argument("--exclude", nargs="*", help="Exclude file patterns")

    args = parser.parse_args()

    tool = DirectoryDiff()

    try:
        dir1, is_temp1 = tool.resolve_path(args.source1, args.subdir1)
        dir2, is_temp2 = tool.resolve_path(args.source2, args.subdir2)

        if not os.path.exists(dir1):
            raise RuntimeError(f"Directory not found: {dir1}")
        if not os.path.exists(dir2):
            raise RuntimeError(f"Directory not found: {dir2}")

        result = tool.compare_directories(dir1, dir2, args.include, args.exclude)

        print(
            f"Total: {result['total_files']}, "
            f"Identical: {result['identical']}, "
            f"Different: {result['different']}, "
            f"Only in source1: {result['only_in_1']}, "
            f"Only in source2: {result['only_in_2']}, "
            f"Avg similarity: {result['avg_similarity']:.2%}"
        )

        print(f"\n# To git diff these files:")
        print(f"# git diff --no-index {dir1} {dir2}")

        if result["different"] > 0:
            print(f"\n# Modified files ({result['different']}):")
            different_files = [
                c for c in result["comparisons"] if c.status == "different"
            ]
            different_files.sort(key=lambda x: x.similarity_ratio or 0)
            for comp in different_files:
                sim_str = (
                    f" ({comp.similarity_ratio:.1%})" if comp.similarity_ratio else ""
                )
                print(
                    f"git diff --no-index '{dir1}/{comp.path}' '{dir2}/{comp.path}'{sim_str}"
                )

        if result["only_in_1"] > 0:
            print(f"\n# Files only in source1 ({result['only_in_1']}):")
            only_1_files = [
                c.path for c in result["comparisons"] if c.status == "only_in_dir1"
            ]
            for path in only_1_files:
                print(f"# Only in source1: {path}")

        if result["only_in_2"] > 0:
            print(f"\n# Files only in source2 ({result['only_in_2']}):")
            only_2_files = [
                c.path for c in result["comparisons"] if c.status == "only_in_dir2"
            ]
            for path in only_2_files:
                print(f"# Only in source2: {path}")

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    main()

