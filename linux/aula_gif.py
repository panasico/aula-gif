#!/usr/bin/env python3
"""GIF conversion and F108 Pro HID upload. Ubuntu transport is experimental."""
from __future__ import annotations
import argparse
import csv
import io
import os
from pathlib import Path
import select
import struct
import sys
import time

WIDTH, HEIGHT, MAX_FRAMES = 240, 135, 141
FRAME_BYTES, PAGE_BYTES = 64800, 4096


def validate(data: bytes) -> int:
    if len(data) < PAGE_BYTES or len(data) % PAGE_BYTES:
        raise ValueError('Invalid page alignment')
    frames = data[0]
    if not 1 <= frames <= MAX_FRAMES:
        raise ValueError('Frame count must be 1..141')
    expected = ((256 + frames * FRAME_BYTES + 4095) // 4096) * 4096
    if len(data) != expected or any(v == 0 for v in data[1:frames + 1]):
        raise ValueError('Invalid image size or frame delay')
    if data[frames + 1:256] != b'\xff' * (255 - frames):
        raise ValueError('Invalid header padding')
    if data[256 + frames * FRAME_BYTES:] != b'\xff' * (len(data) - 256 - frames * FRAME_BYTES):
        raise ValueError('Invalid page padding')
    return frames


def convert(source: Path, output: Path) -> bytes:
    from PIL import Image, ImageOps
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose a new or empty output directory')
    with Image.open(source) as image:
        if image.format != 'GIF':
            raise ValueError('Input must be a GIF')
        total = image.n_frames
        if not 1 <= total <= 20000:
            raise ValueError('Unsupported source frame count')
        count = min(total, MAX_FRAMES)
        selected = [i * total // count for i in range(count)]
        # Sequential seeks preserve GIF disposal/compositing and avoid storing large source frames.
        pictures, durations = [], []
        next_selected = 0
        for i in range(total):
            image.seek(i)
            durations.append(max(0, int(image.info.get('duration', 100))) or 100)
            if next_selected < count and i == selected[next_selected]:
                rgba = image.convert('RGBA')
                background = Image.new('RGBA', rgba.size, 'black')
                background.alpha_composite(rgba)
                fitted = ImageOps.contain(background.convert('RGB'), (WIDTH, HEIGHT), Image.Resampling.LANCZOS)
                canvas = Image.new('RGB', (WIDTH, HEIGHT), 'black')
                canvas.paste(fitted, ((WIDTH - fitted.width)//2, (HEIGHT - fitted.height)//2))
                pictures.append(canvas)
                next_selected += 1
        data = bytearray(b'\xff' * (((256 + count * FRAME_BYTES + 4095)//4096)*4096))
        data[0] = count
        elapsed, emitted = 0, 0
        rows = []
        for i, picture in enumerate(pictures):
            end = selected[i + 1] if i + 1 < count else total
            elapsed += sum(durations[selected[i]:end])
            ticks = max(1, round(elapsed / 20) - emitted)
            if ticks > 255:
                raise ValueError('A frame hold exceeds 5.1 seconds; shorten GIF holds')
            emitted += ticks
            data[i + 1] = ticks
            offset = 256 + i * FRAME_BYTES
            pixels = picture.tobytes()
            for r, g, b in zip(pixels[0::3], pixels[1::3], pixels[2::3]):
                struct.pack_into('<H', data, offset, ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
                offset += 2
            rows.append((i, selected[i], ticks * 20))
        validate(data)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'animation.aula-rgb565').write_bytes(data)
        pictures[0].save(output / 'preview.png')
        with (output / 'frames.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(('frame', 'source_frame', 'delay_ms'))
            writer.writerows(rows)
        info = (f'Source: {image.width}x{image.height}, {total} frames, {sum(durations)} ms\n'
                f'Output: 240x135, {count} frames, {emitted * 20} ms, {len(data)//4096} pages\n')
        (output / 'info.txt').write_text(info, encoding='utf-8')
        print(info)
        return bytes(data)


def descriptor_caps(data: bytes) -> tuple[int, int, int, int]:
    """Read global HID items and aggregate unnumbered report sizes; reject numbered reports."""
    state = dict(page=0, size=0, count=0, report=0)
    stack, pages = [], set()
    bits = {8: 0, 9: 0, 11: 0}
    pos = 0
    while pos < len(data):
        prefix = data[pos]
        pos += 1
        if prefix == 0xFE:
            raise ValueError('Unsupported long HID item')
        length = (0, 1, 2, 4)[prefix & 3]
        if pos + length > len(data):
            raise ValueError('Truncated HID descriptor')
        value = int.from_bytes(data[pos:pos+length], 'little')
        pos += length
        kind, tag = (prefix >> 2) & 3, prefix >> 4
        if kind == 1:
            if tag in (0, 7, 8, 9):
                state[{0: 'page', 7: 'size', 8: 'report', 9: 'count'}[tag]] = value
            elif tag == 10:
                stack.append(state.copy())
            elif tag == 11:
                if not stack:
                    raise ValueError('Invalid HID global pop')
                state = stack.pop()
        elif kind == 0 and tag in bits:
            if state['report']:
                raise ValueError('Numbered reports are not supported for this device')
            pages.add(state['page'])
            bits[tag] += state['size'] * state['count']
    if len(pages) != 1 or any(n % 8 for n in bits.values()):
        raise ValueError('Unexpected HID report structure')
    return pages.pop(), bits[8] // 8, bits[9] // 8, bits[11] // 8


def devices() -> list[dict]:
    if not sys.platform.startswith('linux'):
        raise RuntimeError('USB upload from this version requires Linux; use AulaGif.exe on Windows')
    found = []
    for entry in sorted(Path('/sys/class/hidraw').glob('hidraw*')):
        device = (entry / 'device').resolve()
        event = dict(line.split('=', 1) for line in (device/'uevent').read_text().splitlines() if '=' in line)
        ident = event.get('HID_ID', '').split(':')
        if len(ident) != 3 or tuple(int(v, 16) for v in ident) != (3, 0x0C45, 0x800A):
            continue
        try:
            caps = descriptor_caps((device/'report_descriptor').read_bytes())
        except ValueError:
            continue  # Standard keyboard/media collections are not our vendor interfaces.
        parent = next((p for p in device.parents if (p/'idVendor').exists() and (p/'idProduct').exists()), None)
        if parent is not None:
            found.append(dict(path=Path('/dev')/entry.name, parent=parent, caps=caps))
    return found


def feature_packet(command: int, pages: int = 0) -> bytes:
    packet = bytearray(65)
    packet[1:3] = bytes((4, command))
    if command == 0x72:
        if not 1 <= pages <= 2231:
            raise ValueError('Invalid page count')
        packet[3] = 1
        struct.pack_into('<H', packet, 9, pages)
    elif command not in (0x18, 0x02):
        raise ValueError('Unsupported command')
    return bytes(packet)


class HidTransport:
    def __enter__(self):
        import fcntl
        found = devices()
        controls = [d for d in found if d['caps'][0] == 0xFF13 and d['caps'][3] == 64
                    and d['caps'][1] in (0, 64) and d['caps'][2] in (0, 64)]
        screens = [d for d in found if d['caps'] == (0xFF68, 64, 4096, 0)]
        if len(controls) != 1 or len(screens) != 1 or controls[0]['parent'] != screens[0]['parent']:
            raise RuntimeError('Expected one wired F108 Pro with matching control and screen descriptors')
        self.fds = []
        try:
            for item in (controls[0], screens[0]):
                fd = os.open(item['path'], os.O_RDWR | os.O_NONBLOCK)
                self.fds.append(fd)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.control, self.screen = self.fds
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        for fd in self.fds:
            os.close(fd)
        self.fds = []

    def command(self, command: int, pages: int = 0):
        import fcntl
        packet = bytearray(feature_packet(command, pages))
        # Linux HIDIOCSFEATURE/HIDIOCGFEATURE, size includes the zero report ID.
        fcntl.ioctl(self.control, 0xC0000000 | (65 << 16) | (ord('H') << 8) | 6, packet)
        time.sleep(0.035)
        answer = bytearray(65)
        fcntl.ioctl(self.control, 0xC0000000 | (65 << 16) | (ord('H') << 8) | 7, answer)
        payload = answer[1:] if answer[0] == 0 else answer
        if payload[:2] != bytes((4, command)) or payload[3] != 1:
            raise RuntimeError('Unexpected feature acknowledgment: ' + answer[:12].hex(' '))
        time.sleep(0.035)

    def page(self, page: bytes):
        if len(page) != PAGE_BYTES:
            raise ValueError('Invalid page length')
        # write() uses interrupt OUT for this interface. Never use SET_REPORT for image pages.
        if os.write(self.screen, b'\0' + page) != PAGE_BYTES + 1:
            raise RuntimeError('Incomplete page write; not retrying')
        if not select.select([self.screen], [], [], 5)[0]:
            raise TimeoutError('Page acknowledgment timed out; not retrying')
        answer = os.read(self.screen, 64)
        if len(answer) != 64 or answer[:3] != b'\x01\x5a\x02':
            raise RuntimeError('Unexpected page acknowledgment: ' + answer[:12].hex(' '))


def upload(data: bytes, transport_factory=HidTransport, progress=print):
    frames = validate(data)  # Validate before opening hardware, never permit >141 frames.
    pages = len(data) // PAGE_BYTES
    with transport_factory() as transport:
        progress(f'Uploading {frames} frames. Keep the cable connected.')
        transport.command(0x18)
        transport.command(0x72, pages)
        for index in range(pages):
            transport.page(data[index*PAGE_BYTES:(index+1)*PAGE_BYTES])
            if index % 100 == 0 or index == pages-1:
                progress(f'Progress: {index+1}/{pages} ({(index+1)*100//pages}%)')
        transport.command(0x02)
    progress('All pages and APPLY acknowledged. Wait for the keyboard loading bar to finish.')


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    import queue
    import threading
    from datetime import datetime
    root = tk.Tk()
    root.title('AULA GIF — Ubuntu preview')
    root.geometry('580x240')
    status = tk.StringVar(value='Select a GIF. Connect your F108 Pro with USB in wired mode.')
    ttk.Label(root, textvariable=status, wraplength=540).pack(padx=20, pady=25)
    events = queue.Queue()
    busy = [False]

    def start():
        name = filedialog.askopenfilename(filetypes=[('GIF animation', '*.gif')])
        if not name:
            return
        folder = Path.home()/'Pictures'/'AulaGif'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        busy[0] = True
        button.configure(state='disabled')
        status.set('Converting GIF…')
        def prepare():
            try:
                events.put(('ready', convert(Path(name), folder)))
            except Exception as error:
                events.put(('error', str(error)))
        threading.Thread(target=prepare, daemon=True).start()

    def send(data):
        try:
            upload(data, progress=lambda text: events.put(('progress', text)))
            events.put(('done', 'Upload acknowledged. Wait for loading to finish, then select GIF Image.'))
        except Exception as error:
            events.put(('error', str(error)))

    def poll():
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == 'ready':
                    if messagebox.askyesno('Upload animation?', f'{value[0]} frames prepared. Replace custom animation in slot 1?\nUbuntu USB upload is experimental. Keep the cable connected until loading finishes.'):
                        threading.Thread(target=send, args=(value,), daemon=True).start()
                    else:
                        busy[0] = False
                        button.configure(state='normal')
                        status.set('Converted files saved under ~/Pictures/AulaGif.')
                elif kind in ('done', 'error'):
                    busy[0] = False
                    button.configure(state='normal')
                    status.set(value)
                    (messagebox.showinfo if kind == 'done' else messagebox.showerror)('AULA GIF', value)
                else:
                    status.set(value)
        except queue.Empty:
            pass
        root.after(100, poll)

    def close():
        if busy[0]:
            messagebox.showinfo('AULA GIF', 'Wait for the current operation to finish before closing.')
        else:
            root.destroy()
    button = ttk.Button(root, text='Select GIF', command=start)
    button.pack(pady=10)
    root.protocol('WM_DELETE_WINDOW', close)
    root.after(100, poll)
    root.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('list')
    sub.add_parser('gui')
    converter = sub.add_parser('convert')
    converter.add_argument('source', type=Path)
    converter.add_argument('output', type=Path)
    for action in ('check', 'upload'):
        command = sub.add_parser(action)
        command.add_argument('file', type=Path)
        if action == 'upload':
            command.add_argument('--yes', action='store_true', help='Replace custom animation without prompt')
    args = parser.parse_args(argv)
    try:
        if args.command in (None, 'gui'):
            gui()
        elif args.command == 'list':
            for device in devices():
                print(device['path'], device['caps'])
        elif args.command == 'convert':
            convert(args.source, args.output)
        elif args.command == 'check':
            print(f'Valid: {validate(args.file.read_bytes())} frames')
        elif args.command == 'upload':
            data = args.file.read_bytes()
            validate(data)
            if args.yes or input('Replace custom animation in slot 1? [y/N] ').lower() == 'y':
                upload(data)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
