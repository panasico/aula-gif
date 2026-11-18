Convert ordinary GIFs and upload them to the AULA F108 Pro screen over USB, without the vendor's configuration application.

### Downloads

- **Windows ZIP:** extract and open AulaGif.exe. Windows USB upload has been confirmed on a real F108 Pro by the owner.
- **SHA256SUMS.txt:** checksum for the Windows archive.

**Tested only on AULA F108 Pro, on Windows over USB. No other keyboard model is supported or tested.** Contributions and verified hardware profiles for other models are welcome.

Automatically resizes to 240x135, caps at 141 frames and accumulates skipped frame delays. Uses RGB565 with 20 ms timing resolution. Includes graphical file selection and CLI commands.

Keep the keyboard in wired mode and leave USB connected until its loading bar finishes. Upload replaces the custom animation in slot 1. Supports only USB ID 0c45:800a; not firmware and not a generic AULA updater.

No Ubuntu binaries or packages are published. The [experimental Ubuntu source](https://github.com/panasico/aula-gif/blob/main/linux/aula_gif.py) is available for contributors, but Linux installation, GUI and hardware upload are unverified. Software-only tests are not hardware validation.
