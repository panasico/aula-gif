# Contributing

Issues and pull requests are welcome. Currently **only AULA F108 Pro on Windows over wired USB** has been tested on real hardware.

## Other keyboard models

Please include:

- Exact model/edition and USB VID/PID in wired mode.
- Vendor-interface HID descriptors and report lengths.
- Verified screen dimensions, RGB encoding, storage layout and maximum safe frame count, with a source such as the vendor configuration or a hardware capture.
- A separate device profile and tests that reject mismatched devices and oversized uploads.
- OS/version and actual hardware results, including whether the normal keyboard/menu still works after a short upload.

Do not just change the VID/PID or increase 141 frames. This limit protects menu graphics on the F108 Pro; another model may have a different protocol and memory layout. Do not submit device serial numbers or private captures unrelated to the keyboard.

## Ubuntu / Linux

[linux/aula_gif.py](linux/aula_gif.py) is experimental source, not a supported release. Contributions validating sysfs detection, hidraw report handling, permissions, GUI and real USB playback are especially useful. See [the validation checklist](docs/WSL.md). Report actual hardware tests separately from mock/unit tests.

## Tests

Windows: build with `scripts/build-windows.ps1`, then run `scripts/test-windows.ps1`.

Python tests (Pillow required): `python3 -m unittest discover -s tests -v`.

Keep the upload bounded, validate before opening hardware, and never retry or apply a failed partial transfer automatically.
