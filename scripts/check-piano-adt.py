#!/usr/bin/env python3
"""Validate a generated Apple-format device tree (ADT) and print its structure.

The format is the flat Open Firmware tree Apple uses: every node starts with a
32-bit property count and a 32-bit child count, followed by that many
properties (32-byte name, 32-bit byte length, value padded to 4 bytes) and then
the child nodes, recursively.

Run it on the output of make-piano-adt.py before handing the tree to DarwinBoot:

    python3 scripts/check-piano-adt.py build/piano/boot/kernel.macho.adt
"""
from pathlib import Path
import argparse
import struct
import sys

REQUIRED = {
    'chosen': ('dram-base', 'dram-size', 'random-seed', 'osenvironment',
               'crypto-hash-method', 'amfi-only-platform-code'),
    'cpus': (),
    'arm-io': ('device_type', 'ranges'),
    'product': ('product-name', 'model'),
}
REQUIRED_CHILDREN = {
    '': ('chosen', 'cpus', 'arm-io', 'product', 'defaults', 'options'),
    'chosen': ('memory-map', 'manifest-properties'),
    'arm-io': ('intc', 'ufshc'),
}


def walk(data, offset, depth, path, problems, out):
    if offset + 8 > len(data):
        problems.append(f'{path or "/"}: truncated node header at {offset}')
        return offset
    nprops, nchildren = struct.unpack_from('<II', data, offset)
    offset += 8
    name = path.rsplit('/', 1)[-1] or '/'
    props = {}
    for _ in range(nprops):
        if offset + 36 > len(data):
            problems.append(f'{path or "/"}: truncated property header')
            return offset
        raw_name, length = struct.unpack_from('<32sI', data, offset)
        offset += 36
        key = raw_name.split(b'\0', 1)[0].decode('latin-1')
        value = data[offset:offset + length]
        if len(value) != length:
            problems.append(f'{path or "/"}/{key}: value runs past the end')
            return offset
        offset += length + (-length % 4)
        props[key] = value
    out.append((path or '/', props, nchildren))
    for want in REQUIRED.get(name if path else '', ()):
        if want not in props:
            problems.append(f'{path or "/"}: missing property {want}')
    for want in REQUIRED_CHILDREN.get(path, ()):
        pass  # checked after the children are known
    child_names = []
    for _ in range(nchildren):
        if offset + 44 > len(data):
            problems.append(f'{path or "/"}: truncated child header')
            return offset
        # The child's own 8-byte header comes first, then its 'name' property
        # (32-byte key, 32-bit length at +40, value at +44) whose *value* is the
        # node name.
        child_length = struct.unpack_from('<I', data, offset + 40)[0]
        child_name = data[offset + 44:offset + 44 + child_length].split(b'\0', 1)[0]
        offset = walk(data, offset, depth + 1, f'{path}/{child_name.decode("latin-1")}', problems, out)
        child_names.append(child_name.decode('latin-1'))
    for want in REQUIRED_CHILDREN.get(path, ()):
        if want not in child_names:
            problems.append(f'{path or "/"}: missing child {want}')
    return offset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('adt', type=Path)
    parser.add_argument('--v', '--verbose', action='store_true')
    args = parser.parse_args()

    data = args.adt.read_bytes()
    problems = []
    out = []
    end = walk(data, 0, 0, '', problems, out)
    if end != len(data):
        problems.append(f'{len(data) - end} trailing bytes after the root node')

    for path, props, nchildren in out:
        if path != '/' and not args.v:
            continue
        print(f'{path}  ({len(props)} props, {nchildren} children)')
        for key, value in props.items():
            if key == 'name':
                continue
            if len(value) == 4:
                show = f'0x{struct.unpack("<I", value)[0]:x}'
            elif len(value) == 8:
                show = f'0x{struct.unpack("<Q", value)[0]:x}'
            elif len(value) <= 16:
                show = '0x' + value.hex() if value and not value[-1:] == b'\0' else value.rstrip(b'\0')
            else:
                show = f'<{len(value)} bytes>'
            print(f'    {key} = {show}')

    print()
    print(f'{args.adt}: {len(data)} bytes, {len(out)} nodes')
    if problems:
        print('PROBLEMS:')
        for problem in problems:
            print(f'  - {problem}')
        sys.exit(1)
    print('OK')


if __name__ == '__main__':
    main()
