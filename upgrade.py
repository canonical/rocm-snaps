#!/usr/bin/env python3

import argparse
import gzip
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request


TAG_RE = re.compile(r'^therock-(\d+)\.(\d+)(?:\.(\d+))?$')
REPO_INDEX = 'https://stable.repo.amd.com/rocm/core/packages/ubuntu2604/dists/stable/main/binary-amd64/Packages.gz'
GPU_ISAS = ('gfx1151', 'gfx1100', 'gfx950')
HOST_PACKAGES = (
    'sysdeps', 'base', 'runtime', 'amdsmi', 'math-common', 'profiler-base',
    'blas-host', 'rand-host', 'solver-host', 'sparse-host', 'llvm', 'llvm-dev',
    'runtime-dev', 'blas-dev', 'hipblas-common-dev', 'rand-dev', 'ccl-dev',
)

cli = argparse.ArgumentParser(description=(
    "Update ROCm snaps to the newest TheRock tag " +
    "that has a matching package set in AMD's stable repository."
))
cli.add_argument(
    "--target",
    metavar="therock-X.Y[.Z]",
    help="select a specific stable TheRock tag (default is latest)",
)
mode = cli.add_mutually_exclusive_group()
mode.add_argument(
    "--check",
    action='store_true',
    help="exit with 0 when current, 1 when an upgrade is available",
)
mode.add_argument(
    "--dry-run",
    action='store_true',
    help="print the proposed changes (if any) without applying them",
)


def version_tuple(tag):
    match = TAG_RE.fullmatch(tag)
    if not match: raise ValueError(f"not a stable TheRock tag: {tag}")
    return tuple(int(part or 0) for part in match.groups())


def fetch_upstream_tags() -> list[str]:
    git_ls_remote_tags = subprocess.check_output(
        [
            'git',
            'ls-remote',
            '--tags',
            'https://github.com/ROCm/TheRock.git',
            'refs/tags/therock-*',
        ],
        text=True,
    )

    tags = []

    for line in git_ls_remote_tags.splitlines():
        tag = line.rsplit('refs/tags/', 1)[-1]
        if TAG_RE.fullmatch(tag):
            tags.append(tag)

    return tags


def fetch_package_names() -> set[str]:
    with urllib.request.urlopen(REPO_INDEX, timeout=60) as response:
        data = gzip.decompress(response.read()).decode()
    names = set()
    for paragraph in data.split('\n\n'):
        fields = dict(
            line.split(': ', 1) for line in paragraph.splitlines()
            if ': ' in line and not line.startswith((' ', '\t'))
        )
        if fields.get('Architecture') == 'amd64' and fields.get('Package'):
            names.add(fields['Package'])
    return names


def is_compatible(tag, packages):
    major, minor, patch = version_tuple(tag)
    series = f'{major}.{minor}'
    if patch:
        return False
    required = {f'amdrocm-{name}{series}' for name in HOST_PACKAGES}
    required.update(
        f'amdrocm-{name}{series}-{isa}'
        for name in ('blas', 'rand', 'solver', 'sparse')
        for isa in GPU_ISAS
    )
    return required <= packages


def update_recipe(original_recipe, new_version) -> str:
    snap_version = new_version.removeprefix('therock-')

    updated, version_count = re.subn(
        r'(?m)version: ["\']?[^"\']+["\']?',
        f'version: \'{snap_version}\'',
        original_recipe,
    )

    if version_count != 1:
        raise RuntimeError("refusing to update an unexpected recipe layout")

    return updated


def replace_contents(path, content):
    with tempfile.NamedTemporaryFile('w', dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.chmod(path.stat().st_mode)
    temporary_path.replace(path)


if __name__ == '__main__':
    args = cli.parse_args()

    recipe_path = Path(__file__).resolve().parent / 'inference' / 'snapcraft.yaml'
    original_recipe = recipe_path.read_text()

    version_match = re.search(r'(?m)^\s*version: ["\']?([^"\']+)["\']?$', original_recipe)
    if not version_match:
        raise RuntimeError(f"recipe at '{recipe_path}' does not contain the expected version field")

    current_version = version_match.group(1)
    current_tag = f'therock-{current_version}'
    version_tuple(current_tag)

    candidates = [args.target] if args.target else fetch_upstream_tags()
    package_names = fetch_package_names()
    compatible_tags = [tag for tag in candidates if is_compatible(tag, package_names)]
    if not compatible_tags:
        raise RuntimeError(f"none of the candidate TheRock tags ({candidates}) has the complete AMD package set")

    selected = max(compatible_tags, key=version_tuple)
    if version_tuple(selected)[:2] > version_tuple(current_tag)[:2]:
        print(f'{selected} is available; update the snap version, package names, '
              'and content identifier together after reviewing its package set')
        if args.check:
            sys.exit(1)
        if not args.dry_run:
            raise RuntimeError('automatic upgrades across ROCm series are not supported')
        sys.exit(0)
    if not args.target and version_tuple(selected) <= version_tuple(current_tag):
        print(f"Current version ({current_tag}) already up to date with latest candidate ({selected})")
        sys.exit(0)

    print(f"Latest compatible release: {selected}")
    updated = update_recipe(original_recipe, selected)

    if args.check:
        sys.exit(1)
    elif args.dry_run:
        print(f"dry-run: won't apply changes!")
    else:
        print(f"Applying changes...", end="")
        replace_contents(recipe_path, updated)
        print(f" done!")

    sys.exit(0)
