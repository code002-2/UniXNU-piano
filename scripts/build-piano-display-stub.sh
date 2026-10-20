#!/bin/bash
# Build the piano display probe archive.
#
# The kernel link needs the three probe symbols that bsd_init.c declares under
# `#if DEVELOPMENT || DEBUG`, and piano has no display provider to supply them.
# This produces build/piano-display-stub/libPianoDisplayStub.a, which
# configs/piano_defconfig links through CONFIG_XNU_EXTRA_LD_ARCHIVES.
#
# It deliberately does not need the kernel compile records: it compiles for the
# same target the kernel uses, so it can be built before the first kernel pass.
#
# Usage: scripts/build-piano-display-stub.sh <tree-root> <device-repo-root>
set -euo pipefail
tree=${1:?tree root, e.g. out/piano/tree}
device=${2:?device repository root}

source_file="$device/stubs/PianoDisplayProbe.c"
output_dir="$tree/build/piano-display-stub"
archive="$output_dir/libPianoDisplayStub.a"

sdk=$(xcrun --sdk iphoneos --show-sdk-path)
echo "build-piano-display-stub: sdk $sdk"
mkdir -p "$output_dir"

# -mkernel matches how the kernel itself is compiled (no hosted libc, no
# shared-library assumptions), so the archive links into the kernel.
xcrun --sdk iphoneos clang -target arm64-apple-ios17.0 -isysroot "$sdk" \
	-mkernel -Os -g -Wall -c "$source_file" -o "$output_dir/PianoDisplayProbe.o"

xcrun --sdk iphoneos libtool -static -o "$archive" "$output_dir/PianoDisplayProbe.o"
ls -l "$archive"
xcrun --sdk iphoneos nm -g "$archive" | grep -E 'native_legacy_display_probe|native_mobile_graphics' || true
