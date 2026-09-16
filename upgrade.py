#!/usr/bin/env python3

from pathlib import Path
import argparse
import gzip
import re
import subprocess
import sys
import tempfile
import urllib.request


TAG_RE = re.compile(r'^therock-(\d+)\.(\d+)(?:\.(\d+))?$')

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
    url = 'https://stable.repo.amd.com/rocm/core/packages/ubuntu2604/dists/stable/main/binary-amd64/Packages.gz'
    with urllib.request.urlopen(url, timeout=60) as response:
        data = gzip.decompress(response.read()).decode()

    names = set()

    for paragraph in data.split('\n\n'):
        fields = {}
        for line in paragraph.splitlines():
            if ': ' in line and not line.startswith((' ', '\t')):
                key, value = line.split(': ', 1)
                fields[key] = value
        if fields.get('Architecture') == 'amd64' and 'Package' in fields:
            names.add(fields['Package'])

    return names


def is_compatible(tag, packages):
    major, minor, _ = version_tuple(tag)
    series = f'{major}.{minor}'
    required = {
        f'amdrocm-llvm{series}',
        f'amdrocm-runtime{series}',
        f'amdrocm-sysdeps{series}',
    }
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
        raise RuntimeError(f"none of the candidate TheRock tags ({candidates}) has a complete AMD package set published")

    selected = max(compatible_tags, key=version_tuple)
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
