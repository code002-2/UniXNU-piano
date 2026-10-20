/*
 * PianoDisplayProbe.c - the display probe hooks for the first piano boot.
 *
 * bsd_init.c declares these inside `#if DEVELOPMENT || DEBUG`, which the build
 * always takes (KERNEL_CONFIGS=DEVELOPMENT), so every DEVELOPMENT kernel has to
 * resolve them at link time even when the board has no display provider yet:
 *
 *   native_legacy_display_probe
 *   native_mobile_graphics_client_probe
 *   native_mobile_graphics_probe_checkpoint
 *
 * sheng supplies them with its own family: package/LegacyDisplayProbe.cpp and
 * scripts/build-native-legacy-display.py, which audit an exact qualified
 * original IOMobileFramebufferLegacy candidate by sha256 and therefore only
 * exist for that board. piano has no such candidate, so this file provides the
 * honest "no provider installed" implementation instead of a working display.
 *
 * Consequences, stated plainly: with this stub the kernel links and starts, but
 * nothing drives the UEFI framebuffer yet, so there is no on-screen console.
 * The functions print when reached so a boot log records that the boot arguments
 * got that far. Replacing this archive with a real provider is what turns the
 * framebuffer into a console.
 */
/*
 * The archive is compiled against the iPhoneOS SDK only, so it must not include
 * XNU's own headers (sys/systm.h lives in the kernel tree, not in the SDK).
 * printf inside the kernel is XNU's kernel printf and has the usual signature.
 */
extern int printf(const char *format, ...);

int
native_legacy_display_probe_reached(void)
{
	return 1;
}

void
native_legacy_display_probe(void)
{
	printf("piano: native_legacy_display_probe: no display provider on this board yet\n");
}

void
native_mobile_graphics_client_probe(void)
{
	printf("piano: native_mobile_graphics_client_probe: no display provider on this board yet\n");
}

void
native_mobile_graphics_probe_checkpoint(void)
{
	printf("piano: native_mobile_graphics_probe_checkpoint: mobile graphics load path reached\n");
}
