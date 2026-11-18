"""Build a dependency-based .deb and portable source archive without root or dpkg."""
import io
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'dist'
VERSION = '0.1.0'


def tar(entries):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name, data, mode in entries:
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), mode, 0
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def build():
    OUT.mkdir(exist_ok=True)
    control = (f'Package: aula-gif\nVersion: {VERSION}\nArchitecture: all\n'
               'Maintainer: aula-gif contributors <noreply@localhost>\n'
               'Depends: python3 (>= 3.10), python3-pil, python3-tk\n'
               'Section: utils\nPriority: optional\n'
               'Description: GIF converter and experimental AULA F108 Pro screen uploader\n'
               ' Converts GIF files and uploads RGB565 animations over USB HID.\n').encode()
    launcher = b'#!/bin/sh\nexec python3 /usr/share/aula-gif/aula_gif.py "$@"\n'
    desktop = b'[Desktop Entry]\nType=Application\nName=AULA GIF\nComment=Upload GIF animations to AULA F108 Pro\nExec=aula-gif gui\nIcon=input-keyboard\nTerminal=false\nCategories=Utility;\n'
    entries = [('usr/bin/aula-gif', launcher, 0o755),
               ('usr/share/aula-gif/aula_gif.py', (ROOT/'linux/aula_gif.py').read_bytes(), 0o644),
               ('usr/share/applications/aula-gif.desktop', desktop, 0o644),
               ('usr/share/doc/aula-gif/README.md', (ROOT/'README.md').read_bytes(), 0o644),
               ('usr/share/doc/aula-gif/copyright', (ROOT/'LICENSE').read_bytes(), 0o644),
               ('usr/share/doc/aula-gif/70-aula-gif.rules', (ROOT/'linux/70-aula-gif.rules').read_bytes(), 0o644)]
    parts = [('debian-binary', b'2.0\n'), ('control.tar.gz', tar([('control', control, 0o644)])), ('data.tar.gz', tar(entries))]
    with (OUT/f'aula-gif_{VERSION}_all.deb').open('wb') as stream:
        stream.write(b'!<arch>\n')
        for name, data in parts:
            header = f'{name + "/":<16}{0:<12}{0:<6}{0:<6}{"100644":<8}{len(data):<10}`\n'
            stream.write(header.encode('ascii'))
            stream.write(data)
            if len(data) % 2:
                stream.write(b'\n')
    portable = [('aula-gif/aula_gif.py', (ROOT/'linux/aula_gif.py').read_bytes(), 0o755),
                ('aula-gif/README.md', (ROOT/'README.md').read_bytes(), 0o644),
                ('aula-gif/LICENSE', (ROOT/'LICENSE').read_bytes(), 0o644),
                ('aula-gif/70-aula-gif.rules', (ROOT/'linux/70-aula-gif.rules').read_bytes(), 0o644)]
    (OUT/f'aula-gif-{VERSION}-ubuntu.tar.gz').write_bytes(tar(portable))
    print('Built Ubuntu .deb and source bundle. Installation/USB still require Linux validation.')


if __name__ == '__main__':
    build()
