# Building the piano kernel without macOS

UniXNU's driver requires macOS with Xcode for the kernel step
(`xnu`, `installfile`, `setsegname`, `kextsymboltool`,
`replacecontents`, `decomment` are built as macOS host tools and the kernel is
built with `SDKROOT=iphoneos`). This document records how far that step can be
taken on Linux, what had to be replaced, and what is still missing.

The measurements below were taken on the target tablet itself
(Debian 13 trixie, aarch64, clang 19.1.7, 8 cores, 7.2 GiB RAM) — which makes
it a native-architecture build host for this port.

## Status

| Stage | State |
| --- | --- |
| `unixnu defconfig piano_defconfig -D ../UniXNU-piano` | works |
| `unixnu fetch` (xnu, libplatform, libdispatch, AvailabilityVersions, mu_basecore) | works |
| `unixnu ipsw fetch` (KernelCache, DeviceTree, 2 trust caches) | works, kernelcache matches the board pin |
| `unixnu tree` (assemble tree, apply the 49 xnu patches) | works |
| DriverKit / TrustCache header restore | works through git tags instead of raw.githubusercontent.com |
| all six XNU host tools (`config`, `installfile`, `replacecontents`, `decomment`, `kextsymboltool`, `setsegname`) | build, link and run |
| kernel header export (`build_exporthdrs_mi`) | starts, generates 14 objects, then stops |
| XNU MIG-generated headers and stubs | **blocked, no MIG on Linux** |
| Kernel compile and link | not reached |

The last build reached `build_exporthdrs_mi_bootstrap_DEVELOPMENT^ARM64^BCM2837`
and failed for two reasons, both traced to the missing MIG:

```
            MIG clock.h
make[5]: DAPPLE: 没有那个文件或目录
make[5]: [osfmk/mach/Makefile:306：clock.h] 错误 127 (已忽略）
...
installfile: open(clock.h): No such file or directory
make[5]: [makedefs/MakeInc.rule:449：.../EXPORT_HDRS/osfmk/mach/clock.h] 错误 66
```

`DAPPLE` is the shell trying to execute what is left of the MIG command line
once the empty `$(MIG)` is removed. The MIG rules are marked ignore-errors, so
they only warn, but the header they should have produced is then missing and
`installfile` fails on it, which is fatal.

## Why MIG cannot be obtained

`mig` turns a `.defs` file into the Mach interface headers and RPC stubs that
both the kernel and its exported headers need. It was part of `cctools` in old
Darwin releases, but:

- the current `apple-oss-distributions/cctools` tree has `ar`, `ld`, `libmacho`,
  `libstuff`, `otool` and **no `mig`**;
- Debian has no MIG package for arm64 (the Hurd's `mig` is built only for the
  Hurd ports, and it generates GNU Mach stubs, not Apple's);
- Darling, which does need Apple-compatible Mach stubs on Linux, vendors no MIG
  either — its `src/buildtools` holds only `Rez` and two helper sources.

Apple's MIG now ships inside Xcode. The only public copy of the source is
vendored in Chromium (`third_party/mig`), which builds it with Xcode for macOS.
Porting that to Linux is a project of its own, not a build flag.

## A bug worth remembering

The first successful header-export pass filled the tablet's root filesystem:
eight `*.strip.*` temporary files of about 10.7 GB each, disk at 100%.

The cause was `SETUP/decomment`, XNU's comment stripper. It stores `getchar()`
results in `char` variables, which is only correct where `char` is signed. On
arm64 Linux `char` is unsigned, so `EOF` (-1) becomes 255, the comparison never
matches, and the tool writes `0xFF` forever. `HOST_CC` now passes
`-fsigned-char`, and the tool terminates with its usage message when given no
input file.

Consequence for anyone repeating this: build with a bounded `JOBS`.



## macOS host tools replaced

Each has to sit at the macOS path because XNU's makedefs invoke them by
absolute path or through `xcrun`.

| macOS tool | Replacement | Notes |
| --- | --- | --- |
| `compression_tool` | Debian `lzfse` behind a shim | `ipsw.py` hardcodes `/usr/bin/compression_tool`; the shim drops `-a lzfse`, which Debian's CLI does not take |
| `ditto` | `cp -a` shim | the kernel script uses `ditto SRC DST` three times, directory to directory |
| `sysctl` | shim answering `hw.memsize` / `hw.physicalcpu` / `hw.logicalcpu`, delegating the rest to procps | `makedefs/MakeInc.top` reads `hw.memsize`; without it the memory arithmetic in `KERNEL_BUILDS_IN_PARALLEL` collapses |
| `sw_vers` | shim reporting macOS 14.5 | `makedefs/MakeInc.cmd` reads `-productVersion` |
| `xcrun` | shim | `-sdk macosx -show-sdk-path` returns `/`; `-find clang` returns the wrapper below; `-sdk iphoneos -show-sdk-path` returns a directory to be filled |
| `codesign` | no-op shim | host tools are signed with `-s -`; signatures are meaningless for binaries that only run on this host |
| `codesign_allocate` | stub | only located by `xcrun -find`, not run for a DEVELOPMENT build |
| `gm4` | symlink to `m4` | XNU runs the MIG generator through `gm4` |
| `xcodebuild` | shim that logs and fails | only satisfies the driver's `tool()` check; the kernel script never calls it |

## Compiler and libc gap

`SETUP/*/Makefile` hard-assign `CFLAGS` (`CFLAGS = -isysroot ... -mmacosx-version-min=...`),
so `CFLAGS_EXTRA` never reaches the host tools. The injection point that does
work is `HOST_CC`, which makedefs resolve as `xcrun -sdk macosx -find clang`.
That now returns a wrapper that adds:

```
-isystem /usr/local/include/darwin-compat -include darwin-compat.h
```

`darwin-compat.h` supplies what glibc lacks, guarded so it is inert for the
`arm64-apple-ios` target compiles:

- `getprogname()` through `program_invocation_short_name`
- `setmode()` / `getmode()`, octal form
- `fcopyfile()` / `copyfile()` / `COPYFILE_DATA`
- a `libc.h` and a `copyfile.h` for the includes that only exist on macOS

`strlcpy`/`strlcat` are deliberately not defined there: glibc 2.38 and later
declare them, and a static definition clashes.

## What still blocks the kernel step

1. **MIG.** XNU generates kernel MIG stubs from `.defs` files
   (`MIGFLAGS`, `MIGKSFLAGS`, `MIGKUFLAGS` in `makedefs/MakeInc.def`). Apple no
   longer ships `mig` in `cctools`: the current cctools tree has `ar`, `ld`,
   `libmacho`, `libstuff`, `otool` and no `mig`. Debian has no MIG package for
   arm64 either. The known Linux sources are GNU Mach's `mig` directory and the
   Darling port; either has to be built and taught the XNU-specific flags.
2. **Mach-O host headers.** `kextsymboltool` and `setsegname` include
   `mach-o/arch.h`, `mach-o/swap.h` and `mach/mach_init.h`, which are not in the
   XNU tree and not in Debian. `cctools/libstuff` and `libmacho` contain
   implementations that could be built into a compat library and linked through
   the same `HOST_CC` wrapper.
3. **Mach-O linking.** `/usr/lib/llvm-19/bin/ld64.lld` exists, so a Mach-O
   linker is available, but the kernel link uses `-sectcreate`,
   `ARM64_LINK_ADDR=0xfffffff007004000`, `ARM64_PLKSEG_ADDR` and other Apple
   `ld` behaviour that has not been validated against `ld64.lld`.

## Reproducing what works

```sh
git clone https://github.com/UniXNU/UniXNU ~/xnu-port/UniXNU
# device repository (this one) next to it
cd ~/xnu-port/UniXNU
./unixnu defconfig piano_defconfig -D ../UniXNU-piano
./unixnu fetch
./unixnu ipsw fetch
./unixnu tree
# once, before the first kernel build, because raw.githubusercontent.com is
# unreachable from this host:
cd out/piano/tree && python3 ~/xnu-port/UniXNU-piano/scripts/seed-xnu-headers.py && cd -
~/xnu-port/build-kernel.sh
```

The host replacements are installed under `/usr` by a set of small scripts that
each do one stage (LZFSE, the xcrun/sw_vers/sysctl stand-ins, the compat header,
the Mach-O library, the final `HOST_CC`). Those scripts are deliberately not in
this repository: they log in to the tablet with `sudo -S`, so they contain its
sudo password in clear text. Every replacement they make is listed in the tables
above and each one is a single file under `/usr`, so removing them restores the
stock host.
