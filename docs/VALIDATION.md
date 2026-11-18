# Validation record

## 2026-11-18 — Windows

Owner confirmed successful upload and playback on a USB-wired AULA F108 Pro. Supplied screenshot shows all 2231 pages and APPLY acknowledged. Source: 167 frames, 498x284, 6680 ms. Output: 141 frames, 240x135, 6680 ms.

The Windows source preserves the same uploader used in that successful test. Local checks cover RGB565 red pixel bytes (00 F8), one-frame 65536-byte output, duration preservation, and rejection of invalid frame counts.

## Python / Linux port

Converter and protocol tests run on Windows using CPython 3.13.11 and Pillow 13.0.0. Includes frame limiting, transparent background, total duration, invalid data rejection before opening hardware, command ordering, and no retry/APPLY after an interrupted transfer.

This does **not** validate Linux sysfs discovery, ioctl behavior, udev access, package installation, Tk GUI, or actual Linux USB upload. The owner decided not to install WSL or carry out Ubuntu hardware testing. Ubuntu packages are therefore excluded from Releases; the experimental source remains available to contributors. GitHub Actions results provide Linux software tests only, not physical hardware validation.

Only the owner's AULA F108 Pro has been hardware-tested. Other models are not supported or tested.
