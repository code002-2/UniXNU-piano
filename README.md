# UniXNU-piano

The UniXNU device repository for the **Xiaomi Pad 8 Pro** (codename `piano`,
Snapdragon 8 Elite / SM8750).

This is the device half of a port of [UniXNU](https://github.com/UniXNU/UniXNU)
to that tablet: it describes the board, the target iOS image, the kernel
configuration, the Apple-format device tree, and the build steps that produce a
bootable Darwin kernel. The firmware half comes from
[Project-SunUEFI](https://github.com/slwyts/Project-SunUEFI), which already
carries a working piano EDK2 port.

## What is here

| Path | Contents |
| --- | --- |
| `board.toml` | board description read by the `unixnu` driver |
| `configs/piano_defconfig` | kernel configuration |
| `scripts/make-piano-adt.py` | generates the Apple-format device tree |
| `scripts/check-piano-adt.py` | validates the generated device tree structure |
| `scripts/seed-xnu-headers.py` | restores omitted xnu headers from git tags |
| `.github/workflows/build-kernel.yml` | builds the kernel on a macOS runner |
| `LINUX-BUILD.md` | what was measured while trying to build without macOS |

## Board facts

All of these were read from the running tablet, not assumed:

| Item | Value |
| --- | --- |
| SoC | SM8750 (`qcom,sun`, `qcom,sunp`, `qcom,sun-mtp`), 8 × Oryon |
| GICv3 | distributor `0x16000000`/`0x10000`, redistributor `0x16080000`/`0x200000`, stride `0x40000` |
| Timebase | 19,200,000 Hz (`timer@16800000`, `timer` ) |
| DRAM | base `0x80000000`; the tablet has 8 GiB |
| CPU MPIDR | `0x000,0x100,0x200,0x300,0x400,0x500` and `0x10000,0x10100` |
| PSCI | `arm,psci-1.0`, method `smc` |
| UFS | host controller `0x1d84000` (same as the SM8550 sheng port) |
| Display | `sm8750-dpu` at `0xae01000`, dual DSI, 3200×2136 |
| GPU | Adreno 830 (`adreno-44050001`) at `0x3d00000` |
| Touch | Novatek NT36532 |
| Storage LBAs | 4096-byte logical sectors; `userdata` = 3632128‥30830586 |

## Target image

The port targets the unchanged **iPad7,1 iPadOS 17.7.11 (21H461)** restore image,
the same one the sheng port was qualified against. The Darwin ABI comes from the
kernelcache and the userland, not from the SoC, so the device identity has to
stay `iPad7,1` for MobileGestalt and the prelinked kexts to agree. The
kernelcache this board pins hashes to
`f18b4df865405f2a287b84977d7aca745e056d656d9fc9df1662970ce2969de7`, which is the
pin sheng records as well — verified by extracting it from Apple's CDN.

## Building

The kernel step needs macOS with Xcode, so it runs in CI:

```sh
gh workflow run build-kernel
```

Download `piano-kernel` from the run and read `kernel.macho` plus its sha256.

## Status

The board description, the kernel configuration and the device tree generator
are in place and the `unixnu` driver accepts them. The kernel has not been built
yet; `LINUX-BUILD.md` records how far a macOS-free build got and why it stops.
