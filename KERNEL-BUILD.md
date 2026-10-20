# Building the piano kernel in CI

The kernel step needs macOS with Xcode: it drives xnu's own makefiles with
`xcodebuild` and the iPhoneOS SDK, and generates Mach stubs with Apple's MIG.
GitHub's macOS runners have both, so the build runs there:
`gh workflow run build-piano-kernel`.

## What works

Everything up to and including the full kernel compile.

| Step | State |
| --- | --- |
| `unixnu defconfig` / `fetch` / `ipsw fetch` on the runner | works |
| omitted DriverKit and TrustCache headers | restored from git tags, no GitHub API |
| MIG and iig | resolve from the SDK on Xcode 26.x. `macos-14` ships Xcode 15.4 and is too old: it fails with `clang: error: unknown argument: '-mach_msg2'` followed by `mig: fatal: no SubSystem declaration` |
| whole kernel compile (osfmk, bsd, iokit, libkern, pexpert) | works, about 346k log lines |
| display probe hooks | provided, see below |

## The cycle in the build script, and how it is broken

Two conditions in `scripts/build-xnu-4k-baseline.sh` form a cycle that the driver
alone cannot break:

1. Line 524 wraps the entire archive-linking block in
   `if [ XNU_SOURCE_CORECRYPTO14 = 1 ]`. With the crypto tree off, not even
   `XNU_EXTRA_LD_ARCHIVES` is applied, so no archive can be added to the link.
2. With the crypto tree on, line 720 requires
   `build/corecrypto-2023/libcorecrypto_kernel_noasm-namespaced.a`. Producing it
   needs `scripts/build-corecrypto-14.py --namespace`, which reads the built
   kernel's undefined symbols to decide which provider names to prefix. The
   archive therefore needs a kernel that cannot be linked without it.

`CRYPTO_BOOTSTRAP=source` does not help: line 720 requires the same namespaced
archive in either mode.

The workflow breaks the cycle with a two-pass build:

1. `configs/piano_seed_defconfig` turns the crypto tree off and builds a plain
   kernel. It links because the display probe hooks are supplied in the source
   (below), not through an archive.
2. `build-corecrypto-14.py` runs twice against that kernel, plain then
   `--namespace`.
3. `scripts/build-arm-driver.py` compiles the two driver archives the shipping
   configuration needs (`ArmDTPlatform`, `ArmCpu`) from `drivers/` of the base
   repository, against the compile command the seed kernel recorded.
4. `configs/piano_defconfig` builds the shipping kernel, which now finds every
   archive it requires, and `unixnu build kernel` prelinks it.

## The display probe hooks

`bsd_init.c` declares `native_mobile_graphics_load_probe()` inside
`#if DEVELOPMENT || DEBUG`, which this configuration always takes, so every
DEVELOPMENT kernel references `native_legacy_display_probe`,
`native_mobile_graphics_client_probe` and `native_mobile_graphics_probe_checkpoint`.

sheng supplies them from `package/LegacyDisplayProbe.cpp` and
`scripts/build-native-legacy-display.py`, which qualify an exact original
`IOMobileFramebufferLegacy` candidate by sha256; that candidate does not exist for
piano. The device repository therefore overrides
`scripts/build-xnu-4k-baseline.sh` and appends the three functions, which log and
return, to the tail of `bsd_init.c` — outside every patch's context, and without
touching the base repository's `patches/xnu` module (a device `patches/xnu` would
replace those 49 patches instead of adding to them).

The consequence is stated plainly: the kernel references a display path that does
nothing, so there is no on-screen console until a real provider replaces it.

## Built

Run [39403317018](https://github.com/code002-2/UniXNU-piano/actions/runs/39403317018)
finished the whole chain in 9m12s on `macos-latest` (Xcode 26.6, iPhoneOS 26.5 SDK):

| Artifact | Size | Note |
| --- | --- | --- |
| `kernel.macho` | 51,806,208 B | prelinked kernel, sha256 `6912319adf0b623eb04987f2dbd29c4b5c9f97ca18b469571bd67c7815c86c07` |
| `mach.development.bcm2837.unstripped.noctf` | 18,961,024 B | the native kernel before prelink |
| `mach.development.bcm2837.a` | 128,989,576 B | the kernel's static archive |

Both Mach-O images are `cputype 0x100000c` (ARM64), `filetype 2` (`MH_EXECUTE`).

`mach.development.bcm2837.linkarchives` shows exactly what the link consumed:

```
-L.../.cache/fakeroot/usr/local/lib/kernel -lfirehose_kernel
  .../build/corecrypto-2023/libcorecrypto_kernel_noasm-namespaced.a
  -Wl,-force_load,.../build/armdt-platform/libArmDTPlatform.a
  -Wl,-force_load,.../build/armcpu/libArmCpu.a
```

The prelink tool describes its own output honestly, and that wording matters:

```
Experimental candidate: 51806208 bytes; executable bytes unchanged; runtime unqualified
```

So the kernel exists and is prelinked against the iPad7,1 kernelcache, but nothing
about it has been validated on hardware yet.

## Still missing

- A real legacy display provider, for the reason above.
- UFS and its piano-specific clock and power integration, for the root device.
- The firmware half: `UniXNUPkg` and `DarwinBoot` are not yet part of the SunUEFI
  `pianoPkg` build.
- `payload`, `bootimg`, and the boot on the tablet itself.

## Note on the tracing override

`scripts/build-xnu-4k-baseline.sh` in this repository is a copy of the base
script with `set -x` and an `ERR` trap added, plus the probe-hook append. It is
kept because the base script exits non-zero in places without printing why. Once
the kernel links, it should shrink back to just the probe-hook change.
