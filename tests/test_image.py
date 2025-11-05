import os
import unittest

from mgtdisklib import EDSKImage, Image, IMGImage, MGTImage, SADImage
from test_utils import TESTDIR, make_temp_file


class ImageTests(unittest.TestCase):
    def test_construct_image(self):
        image = Image()
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_mgt_image(self):
        image = Image.open(f'{TESTDIR}/image.mgt')
        self.assertIsInstance(image, MGTImage)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_sad_image(self):
        image = Image.open(f'{TESTDIR}/image.sad')
        self.assertIsInstance(image, SADImage)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 819222)

    def test_open_edsk_image(self):
        image = Image.open(f'{TESTDIR}/image.dsk')
        self.assertIsInstance(image, EDSKImage)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 860416)

    def test_open_img_image(self):
        image = Image.open(f'{TESTDIR}/image.img')
        self.assertIsInstance(image, IMGImage)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_img_short_image(self):
        image = Image.open(f'{TESTDIR}/image_short.img.gz')
        self.assertIsInstance(image, IMGImage)
        self.assertTrue(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_mgt_gzip_image(self):
        image = Image.open(f'{TESTDIR}/image.mgt.gz')
        self.assertIsInstance(image, MGTImage)
        self.assertTrue(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_sad_gzip_image(self):
        image = Image.open(f'{TESTDIR}/image.sad.gz')
        self.assertIsInstance(image, SADImage)
        self.assertTrue(image.compressed)
        self.assertEqual(len(image.data), 819222)

    def test_open_edsk_gzip_image(self):
        image = Image.open(f'{TESTDIR}/image.dsk.gz')
        self.assertIsInstance(image, EDSKImage)
        self.assertTrue(image.compressed)
        self.assertEqual(len(image.data), 860416)

    def test_open_img_gzip_image(self):
        image = Image.open(f'{TESTDIR}/image.img.gz')
        self.assertIsInstance(image, IMGImage)
        self.assertTrue(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_mgt_zip_image(self):
        image = Image.open(f'{TESTDIR}/image.mgt.zip')
        self.assertIsInstance(image, MGTImage)
        self.assertEqual(image.path, os.path.abspath(f'{TESTDIR}/image.mgt.zip'))
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_mgt_gzip_zip_image(self):
        image = Image.open(f'{TESTDIR}/image.mgt.gz.zip')
        self.assertIsInstance(image, MGTImage)
        self.assertTrue(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_mgt_upper_zip_image(self):
        image = Image.open(f'{TESTDIR}/image_upper.zip')
        self.assertIsInstance(image, MGTImage)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_zip_multiple_images(self):
        self.assertRaises(RuntimeError, Image.open, f'{TESTDIR}/image_multiple.zip')

    def test_open_invalid_image(self):
        self.assertRaises(RuntimeError, Image.open, f'{TESTDIR}/samdos2')

    def test_save_no_path(self):
        image = Image()
        self.assertRaises(ValueError, image.save)

    def test_save_mgt_image(self):
        image = Image()
        with make_temp_file('.mgt') as temp_path:
            image.save(temp_path)
            self.assertEqual(os.path.getsize(temp_path), 819200)
            image = Image.open(temp_path)
            image.save()
        self.assertFalse(image.compressed)

    def test_save_mgt_gzip_image(self):
        image = Image()
        with make_temp_file('.mgt.gz') as temp_path:
            image.save(temp_path, compressed=True)
            self.assertLess(os.path.getsize(temp_path), 10000)
            image = Image.open(temp_path)
        self.assertTrue(image.compressed)

    def test_base_sector_offsets(self):
        image = Image()
        self.assertRaises(NotImplementedError, image.sector_offset, 0, 1)

    def test_mgt_sector_offsets(self):
        image = MGTImage()
        self.assertEqual(image.sector_offset(0, 1), 0)
        self.assertEqual(image.sector_offset(0, 2), 512)
        self.assertEqual(image.sector_offset(1, 1), 1*2*10*512)
        self.assertEqual(image.sector_offset(4, 1), 4*2*10*512)
        self.assertEqual(image.sector_offset(79, 10), (79*2*10+9)*512)
        self.assertEqual(image.sector_offset(128, 1), 10*512)
        self.assertEqual(image.sector_offset(207, 10), (80*2*10-1)*512)
        self.assertRaises(ValueError, image.sector_offset, -1, 1)
        self.assertRaises(ValueError, image.sector_offset, 0, 0)
        self.assertRaises(ValueError, image.sector_offset, 0, 11)
        self.assertRaises(ValueError, image.sector_offset, 80, 1)
        self.assertRaises(ValueError, image.sector_offset, 208, 1)

    def test_img_sector_offsets(self):
        image = IMGImage()
        self.assertEqual(image.sector_offset(0, 1), 0)
        self.assertEqual(image.sector_offset(0, 2), 512)
        self.assertEqual(image.sector_offset(1, 1), 1*10*512)
        self.assertEqual(image.sector_offset(4, 1), 4*10*512)
        self.assertEqual(image.sector_offset(79, 10), (80*10-1)*512)
        self.assertEqual(image.sector_offset(128, 1), 80*10*512)
        self.assertEqual(image.sector_offset(207, 10), (80*2*10-1)*512)
        self.assertRaises(ValueError, image.sector_offset, -1, 1)
        self.assertRaises(ValueError, image.sector_offset, 0, 0)
        self.assertRaises(ValueError, image.sector_offset, 0, 11)
        self.assertRaises(ValueError, image.sector_offset, 80, 1)
        self.assertRaises(ValueError, image.sector_offset, 208, 1)

    def test_sad_sector_offsets(self):
        image = SADImage()
        self.assertEqual(image.sector_offset(0, 1), 22+0)
        self.assertEqual(image.sector_offset(0, 2), 22+512)
        self.assertEqual(image.sector_offset(1, 1), 22+10*512)
        self.assertEqual(image.sector_offset(79, 10), 22+(79*10+9)*512)
        self.assertEqual(image.sector_offset(128, 1), 22+(80+0)*10*512)
        self.assertEqual(image.sector_offset(207, 10), 22+((80+79)*10+10-1)*512)
        self.assertRaises(ValueError, image.sector_offset, -1, 1)
        self.assertRaises(ValueError, image.sector_offset, 0, 0)
        self.assertRaises(ValueError, image.sector_offset, 0, 11)
        self.assertRaises(ValueError, image.sector_offset, 80, 1)
        self.assertRaises(ValueError, image.sector_offset, 208, 1)

    def test_edsk_sector_offsets(self):
        image = Image.open(f'{TESTDIR}/image.dsk')
        self.assertEqual(image.sector_offset(0, 1), 0x100+0x100)
        self.assertEqual(image.sector_offset(0, 2), 0x100+0x100+512)
        self.assertEqual(image.sector_offset(1, 1), 0x100+(0x1500*2)+0x100+512)
        self.assertEqual(image.sector_offset(79, 10), 0x100+(0x1500*79*2)+0x100+8*512)
        self.assertEqual(image.sector_offset(128, 1), 0x100+(0x1500)+0x100)
        self.assertEqual(image.sector_offset(207, 10), 0x100+(0x1500*79*2+0x1500)+0x100+8*512)
        self.assertRaises(ValueError, image.sector_offset, -1, 1)
        self.assertRaises(ValueError, image.sector_offset, 0, 0)
        self.assertRaises(ValueError, image.sector_offset, 0, 11)
        self.assertRaises(ValueError, image.sector_offset, 80, 1)
        self.assertRaises(ValueError, image.sector_offset, 208, 1)

    def test_read_sector_mgt(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        self.assertIsInstance(image, MGTImage)
        data = image.read_sector(0, 1)
        self.assertEqual(len(data), 512)
        self.assertEqual(data[1:1+7], bytes('samdos2', 'ascii'))
        data = image.read_sector(4, 1)
        self.assertEqual(len(data), 512)
        self.assertEqual(data[315:315+7], bytes('samdos2', 'ascii'))

    def test_read_sector_img(self):
        image = Image.open(f'{TESTDIR}/image.img.gz')
        self.assertIsInstance(image, IMGImage)
        data = image.read_sector(0, 1)
        self.assertEqual(len(data), 512)
        self.assertEqual(data[1:1+5], bytes('hello', 'ascii'))
        data = image.read_sector(4, 1)
        self.assertEqual(len(data), 512)
        self.assertEqual(data[0:1], b'\x10')

    def test_write_sector(self):
        image = MGTImage()
        data = bytes((x & 0xff for x in range(512)))
        image.write_sector(10, 5, data)
        self.assertEqual(image.read_sector(10, 5), data)
        self.assertRaises(ValueError, image.write_sector, 0, 1, bytes(511))
        self.assertRaises(ValueError, image.write_sector, 0, 1, bytes(513))


if __name__ == '__main__':
    unittest.main()  # pragma: no cover
