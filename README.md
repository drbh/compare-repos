# Compare Repos

Compare directories or Git repositories with detailed file-by-file analysis and similarity metrics.

## Usage

```bash
# Compare local directories
uv run compare.py dir1/ dir2/

# Compare repositories
uv run compare.py https://github.com/user/repo1.git https://github.com/user/repo2.git

# Compare subdirectories
uv run compare.py repo1/ repo2/ --subdir1 src --subdir2 source
```

## Options

- `--subdir1`, `--subdir2`: Compare specific subdirectories
- `--include`: Include file patterns (e.g., `*.py *.cpp`)
- `--exclude`: Exclude file patterns

## Supported Files

C/C++ (`.cpp`, `.c`, `.h`, `.hpp`, `.cu`, `.cuh`), Python (`.py`, `.pyx`)


## Example Output

```bash
uv run compare.py \
    https://github.com/Dao-AILab/flash-attention.git \
    https://huggingface.co/kernels-community/flash-attn \
    --subdir1 csrc/flash_attn \
    --subdir2 flash_attn
```

```
Total: 93, Identical: 92, Different: 1, Only in source1: 0, Only in source2: 0, Avg similarity: 99.90%

# To git diff these files:
# git diff --no-index /Users/drbh/Projects/compare-repos/.repo_cache/flash-attention/csrc/flash_attn /Users/drbh/Projects/compare-repos/.repo_cache/kernels-community_flash-attn/flash_attn

# Modified files (1):
git diff --no-index '/Users/drbh/Projects/compare-repos/.repo_cache/flash-attention/csrc/flash_attn/flash_api.cpp' '/Users/drbh/Projects/compare-repos/.repo_cache/kernels-community_flash-attn/flash_attn/flash_api.cpp' (90.9%)
```

## Quick Start

You can run it directly with `uv`:

```bash
uv run https://raw.githubusercontent.com/drbh/compare-repos/refs/heads/main/compare.py \
    https://github.com/Dao-AILab/flash-attention.git \
    https://huggingface.co/kernels-community/flash-attn \
    --subdir1 csrc/flash_attn \
    --subdir2 flash_attn
```  