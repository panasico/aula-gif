# Ubuntu / WSL validation checklist

Windows hardware upload has already succeeded on AULA F108 Pro. The Ubuntu port has **not been tested in WSL or on Linux hardware**. The owner decided not to perform Ubuntu testing; no Ubuntu packages are published. This optional checklist is retained for future contributors, not as a promised test or supported installation guide.

## 1. Conversion, packaging and GUI without USB

```powershell
wsl --list --verbose
```

Inside Ubuntu, in a checkout of this repository:

```sh
cat /etc/os-release
uname -r
sudo apt update
sudo apt install python3 python3-pil python3-tk
python3 -m unittest discover -s tests -v
python3 scripts/build-ubuntu.py
dpkg-deb --info dist/aula-gif_0.1.0_all.deb
sudo apt install ./dist/aula-gif_0.1.0_all.deb
aula-gif --help
aula-gif convert /path/to/example.gif /tmp/aula-gif-check
aula-gif check /tmp/aula-gif-check/animation.aula-rgb565
aula-gif gui
```

Use a fresh output folder on repeat runs. GUI needs WSLg or another working display server. Confirm the generated frame count and duration in `info.txt` and preview before testing hardware.

## 2. USB hardware test (separate from conversion tests)

WSL does not automatically receive Windows USB devices. Microsoft documents forwarding with [usbipd-win](https://learn.microsoft.com/en-us/windows/wsl/connect-usb). While attached to WSL, the keyboard cannot be used by Windows. Have another keyboard/input method ready. Do not forward the keyboard during an active upload.

First inspect `usbipd list` on Windows; do not assume a bus ID. If usbipd is absent, install it with the user's permission. Binding requires an administrator terminal:

```powershell
usbipd list
usbipd bind --busid <actual-keyboard-busid>
usbipd attach --wsl --busid <actual-keyboard-busid>
```

Inside Ubuntu:

```sh
lsusb -d 0c45:800a
ls /dev/hidraw*
aula-gif list
```

If `/dev/hidraw*` is absent, the WSL kernel may lack the required HID raw configuration. Stop there; do not substitute SET_REPORT for screen data or claim that USB has been validated. Native Ubuntu is an alternative test environment.

The expected vendor collections are usage page `ff13` with a 64-byte feature report and usage page `ff68` with 4096-byte output / 64-byte input reports. If permissions block access, use a carefully scoped device permission change or, for a controlled test of the reviewed local code, `sudo aula-gif upload ...` from the terminal. Do not run the GUI as root.

Only after descriptor and conversion checks pass, upload a short prepared animation. Keep USB connected until both the program and keyboard finish; verify playback physically. Record exact Ubuntu/WSL versions and the result in VALIDATION.md.

Detach afterward from Windows:

```powershell
usbipd detach --busid <actual-keyboard-busid>
```

## Handoff context

- Project: public GitHub repository intended to be named `aula-gif`.
- Windows app was built and successfully used by the owner.
- Demo GIF and successful upload screenshot are in `docs/media`.
- Experimental Ubuntu source, development `.deb` builder and mock tests are retained for contributors. No Ubuntu release is published and no hardware test is currently planned.
- Never describe Ubuntu as hardware-tested solely because CI or conversion tests pass.
