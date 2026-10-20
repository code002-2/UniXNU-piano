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
| MIG and iig | resolve from the SDK on Xcode 26.6 (`macos-14`'s Xcode 15.4 is too old: it fails with `clang: error: unknown argument: '-mach_msg2'` followed by `mig: fatal: no SubSystem declaration`) |
| whole kernel compile (osfmk, bsd, iokit, libkern, pexpert) | works, ~346k log lines |
| display probe archive (`stubs/PianoDisplayProbe.c`) | builds and links |

## The loop that stops it

Two conditions in `scripts/build-xnu-4k-baseline.sh` form a cycle that the
driver alone cannot break:

1. Line 524 wraps the entire archive-linking block in
   `if [ XNU_SOURCE_CORECRYPTO14 = 1 ]`. With the crypto tree off, not even
   `XNU_EXTRA_LD_ARCHIVES` is applied, so the display probe stub cannot be
   linked — and `bsd_init.c` declares those probes inside
   `#if DEVELOPMENT || DEBUG`, which this build always takes, so the link then
   fails on `_native_legacy_display_probe`.
2. With the crypto tree on, line 720 requires
   `build/corecrypto-2023/libcorecrypto_kernel_noasm-namespaced.a` to exist.
   Producing it needs `scripts/build-corecrypto-14.py --namespace`, which reads
   the *built kernel's* undefined symbols to decide which provider names to
   prefix. So the archive needs a kernel that cannot be linked without it.

A `CRYPTO_BOOTSTRAP=source` seed configuration does not help: line 720 requires
the same namespaced archive in either mode.

## Next step

Break the loop outside the driver, which is what the porting flow expects:

1. Run xnu's make directly for one pass, with the same arguments the driver uses
   (`SDKROOT=iphoneos ARCH_CONFIGS=ARM64 MACHINE_CONFIGS=BCM2837
   KERNEL_CONFIGS=DEVELOPMENT`, plus the stub archive on the link line), to
   produce `mach.development.bcm2837.unstripped.noctf`.
2. Build the plain and then the namespaced corecrypto provider against it.
3. From there `unixnu build kernel` and `unixnu build prelink` work as
   documented.

## Still missing after that

- A real legacy display provider. The stub only resolves the symbols and prints;
  nothing drives the UEFI framebuffer, so there is no on-screen console.
  sheng's `package/LegacyDisplayProbe.cpp` and
  `scripts/build-native-legacy-display.py` cannot be reused: they audit an exact
  qualified original `IOMobileFramebufferLegacy` candidate by sha256.
- The firmware half: `UniXNUPkg` and `DarwinBoot` are not yet part of the
  SunUEFI `pianoPkg` build.
- `payload`, `bootimg` and the on-device boot itself.
