import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('aula_gif', ROOT/'linux'/'aula_gif.py')
aula = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aula)


def fixture():
    data = bytearray(b'\xff' * 65536)
    data[0:2] = bytes((1, 5))
    return bytes(data)


class FakeTransport:
    def __init__(self, fail=False):
        self.events = []
        self.fail = fail
    def __enter__(self):
        return self
    def __exit__(self, *_):
        self.events.append('close')
    def command(self, command, pages=0):
        self.events.append((command, pages))
    def page(self, data):
        self.events.append(('page', len(data)))
        if self.fail:
            raise TimeoutError('test timeout')


class ProtocolTests(unittest.TestCase):
    def test_upload_sequence(self):
        transport = FakeTransport()
        aula.upload(fixture(), lambda: transport, lambda _: None)
        self.assertEqual(transport.events[:2], [(0x18, 0), (0x72, 16)])
        self.assertEqual(transport.events[2:-2], [('page', 4096)] * 16)
        self.assertEqual(transport.events[-2:], [(2, 0), 'close'])

    def test_partial_upload_never_applies_or_retries(self):
        transport = FakeTransport(fail=True)
        with self.assertRaises(TimeoutError):
            aula.upload(fixture(), lambda: transport, lambda _: None)
        self.assertNotIn((2, 0), transport.events)
        self.assertEqual(transport.events.count(('page', 4096)), 1)
        self.assertEqual(transport.events[-1], 'close')

    def test_invalid_data_never_opens_hardware(self):
        for index, value in ((0, 0), (0, 142), (1, 0), (255, 0), (65535, 0)):
            data = bytearray(fixture())
            data[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                aula.upload(data, lambda: self.fail('Hardware must not open'))
        with self.assertRaises(ValueError):
            aula.validate(fixture()[:-1])

    def test_header_packet(self):
        packet = aula.feature_packet(0x72, 2231)
        self.assertEqual(packet[:4], b'\0\x04\x72\x01')
        self.assertEqual(struct.unpack_from('<H', packet, 9)[0], 2231)
        with self.assertRaises(ValueError):
            aula.feature_packet(0x72, 2232)

    def test_descriptor(self):
        descriptor = bytes.fromhex('0668ff0961a10175689540810275089600109102c0')
        self.assertEqual(aula.descriptor_caps(descriptor), (0xFF68, 832, 4096, 0))
        descriptor = bytes.fromhex('0668ff0961a1017508954081029600109102c0')
        self.assertEqual(aula.descriptor_caps(descriptor), (0xFF68, 64, 4096, 0))
        with self.assertRaises(ValueError):
            aula.descriptor_caps(bytes.fromhex('0668ff8501750895408102'))


class ConverterTests(unittest.TestCase):
    def test_rgb565_and_frame_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            frames = [Image.new('RGB', (16, 9), (255, i, 0)) for i in range(167)]
            source = root/'source.gif'
            frames[0].save(source, save_all=True, append_images=frames[1:], duration=40, loop=0, optimize=False)
            data = aula.convert(source, root/'out')
            self.assertEqual(aula.validate(data), 141)
            self.assertEqual(sum(data[1:142])*20, 6680)
            self.assertEqual(data[256:258], b'\x00\xf8')
            self.assertEqual(len(data), 2231*4096)
            with self.assertRaises(ValueError):
                aula.convert(source, root/'out')

    def test_transparency_on_black(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = Image.new('RGBA', (240, 135), (255, 0, 0, 0))
            image.save(root/'transparent.gif', transparency=0)
            data = aula.convert(root/'transparent.gif', root/'out')
            self.assertEqual(data[256:258], b'\0\0')


if __name__ == '__main__':
    unittest.main()
