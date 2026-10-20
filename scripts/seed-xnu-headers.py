#!/usr/bin/env python3
"""Seed the DriverKit and TrustCache headers that UniXNU restores from Apple.

UniXNU's scripts/prepare-xnu-source.py downloads each omitted header from
raw.githubusercontent.com. On this host that endpoint resets the connection on
every attempt, while github.com (git) and api.github.com work. This script gets
the identical bytes from the git tag instead:

  - the file list still comes from api.github.com, in the same JSON cache files
    prepare-xnu-source.py writes, so the sourced set is unchanged;
  - the content comes from `git show TAG:path` in the pinned xnu feed;
  - every file is checked against the git blob sha1 recorded in that JSON,
    which is the same integrity check the original script performs.

Run it from the build tree root (out/<board>/tree) before `unixnu build kernel`.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import urllib.request

TAGS = [
    # (tag, api path in the repository, destination directory, json cache name)
    ('xnu-10063.121.3', 'iokit/DriverKit', '.cache/xnu-work/iokit/DriverKit',
     'xnu-driverkit-10063.121.3.json'),
    ('xnu-10063.121.3', 'iokit/DriverKit/crypto', '.cache/xnu-work/iokit/DriverKit/crypto',
     'xnu-driverkit-crypto-10063.121.3.json'),
    ('xnu-8796.101.5', 'EXTERNAL_HEADERS/TrustCache', '.cache/xnu-work/EXTERNAL_HEADERS/TrustCache',
     'xnu-trustcache-8796.101.5.json'),
]
API = 'https://api.github.com/repos/apple-oss-distributions/xnu/contents/{path}?ref={tag}'


def blob_sha1(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def find_feed():
    # The tree lives at out/<board>/tree, so the feeds of the driver are at
    # ../../feeds from here; out/feeds covers running from the repository root.
    candidates = ['../../feeds', 'out/feeds', 'feeds']
    for candidate in candidates:
        feeds = sorted(Path(candidate).glob('xnu-*'))
        if feeds:
            return feeds[0]
    raise SystemExit('no xnu feed checkout under ' + ', '.join(candidates))


def ensure_tag(repo, tag):
    got = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--verify', '-q', f'{tag}^{{commit}}'],
                         capture_output=True, text=True)
    if got.returncode == 0:
        return
    print(f'  fetching tag {tag}')
    subprocess.run(['git', '-C', str(repo), 'fetch', '-q', '--depth', '1', 'origin', f'tag', tag],
                   check=True)


def read_blob(repo, tag, path):
    got = subprocess.run(['git', '-C', str(repo), 'show', f'{tag}:{path}'],
                         capture_output=True)
    if got.returncode != 0:
        raise SystemExit(f'git show {tag}:{path} failed: {got.stderr.decode()[:200]}')
    return got.stdout


def main():
    repo = find_feed()
    print(f'feed {repo}')
    cache = Path('.cache/sources')
    cache.mkdir(parents=True, exist_ok=True)
    total = written = skipped = 0
    for tag, api_path, dest, cache_name in TAGS:
        listing = cache / cache_name
        if not listing.exists():
            url = API.format(path=api_path, tag=tag)
            listing.write_bytes(urllib.request.urlopen(url, timeout=60).read())
        entries = json.loads(listing.read_text())
        ensure_tag(repo, tag)
        target_dir = Path(dest)
        for entry in entries:
            if entry['type'] != 'file' or not entry['name'].endswith('.h'):
                continue
            total += 1
            out = target_dir / entry['name']
            if out.exists():
                skipped += 1
                continue
            data = read_blob(repo, tag, f'{api_path}/{entry["name"]}')
            digest = blob_sha1(data)
            if digest != entry['sha']:
                raise SystemExit(f'blob mismatch for {entry["name"]}: {digest} != {entry["sha"]}')
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
            written += 1
        print(f'  {api_path} @ {tag}: {sum(1 for e in entries if e["type"] == "file" and e["name"].endswith(".h"))} headers')
    print(f'headers: {total} listed, {written} written, {skipped} already present')
    return 0


if __name__ == '__main__':
    sys.exit(main())
