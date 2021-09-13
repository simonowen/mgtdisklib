import os, unittest
from mgtdisklib import Image, MGTImage, SADImage

TESTDIR=os.path.join(os.path.split(__file__)[0], 'data')
TESTOUTPUTFILE=f'{TESTDIR}/__output__.mgt'

class ImageTests(unittest.TestCase):
    def test_construct_image(self):
        image = Image()
        self.assertEqual(image.spt, 10)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_construct_image_9spt(self):
        image = Image(spt=9)
        self.assertEqual(image.spt, 9)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 737280)

    def test_open_mgt_image(self):
        image = Image.open(f'{TESTDIR}/image.mgt')
        self.assertEqual(image.spt, 10)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_sad_image(self):
        image = Image.open(f'{TESTDIR}/image.sad')
        self.assertEqual(image.spt, 10)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 819222)

    def test_open_edsk_image(self):
        image = Image.open(f'{TESTDIR}/image.dsk')
        self.assertEqual(image.spt, 10)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 860416)

    def test_open_mgt_gzip_image(self):
        image = Image.open(f'{TESTDIR}/image.mgt.gz')
        self.assertEqual(image.spt, 10)
        self.assertTrue(image.compressed)
        self.assertEqual(len(image.data), 819200)

    def test_open_sad_gzip_image(self):
        image = Image.open(f'{TESTDIR}/image.sad.gz')
        self.assertEqual(image.spt, 10)
        self.assertTrue(image.compressed)
        self.assertEqual(len(image.data), 819222)

    def test_open_edsk_gzip_image(self):
        image = Image.open(f'{TESTDIR}/image.dsk.gz')
        self.assertEqual(image.spt, 10)
        self.assertTrue(image.compressed)
        self.assertEqual(len(image.data), 860416)

    def test_open_mgt_image9(self):
        image = Image.open(f'{TESTDIR}/image9.mgt')
        self.assertEqual(image.spt, 9)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 737280)

    def test_open_sad_image9(self):
        image = Image.open(f'{TESTDIR}/image9.sad')
        self.assertEqual(image.spt, 9)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 22+737280)

    def test_open_edsk_image9(self):
        image = Image.open(f'{TESTDIR}/image9.dsk')
        self.assertEqual(image.spt, 9)
        self.assertFalse(image.compressed)
        self.assertEqual(len(image.data), 778496)

    def test_open_invalid_image(self):
        self.assertRaises(RuntimeError, Image.open, f'{TESTDIR}/samdos2')

    def test_save_mgt_image(self):
        image = Image()
        image.save(TESTOUTPUTFILE)
        self.assertEqual(os.path.getsize(TESTOUTPUTFILE), 819200)
        image = Image.open(TESTOUTPUTFILE)
        os.remove(TESTOUTPUTFILE)
        self.assertFalse(image.compressed)
        self.assertEqual(image.spt, 10)

    def test_save_mgt_gzip_image(self):
        image = Image()
        image.save(TESTOUTPUTFILE, compressed=True)
        self.assertLess(os.path.getsize(TESTOUTPUTFILE), 10000)
        image = Image.open(TESTOUTPUTFILE)
        os.remove(TESTOUTPUTFILE)
        self.assertTrue(image.compressed)
        self.assertEqual(image.spt, 10)

    def test_save_mgt_image9(self):
        image = Image(spt=9)
        image.save(TESTOUTPUTFILE)
        self.assertEqual(os.path.getsize(TESTOUTPUTFILE), 737280)
        image = Image.open(TESTOUTPUTFILE)
        os.remove(TESTOUTPUTFILE)
        self.assertFalse(image.compressed)
        self.assertEqual(image.spt, 9)

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

    def test_dos_sector_offsets(self):
        image = Image(spt=9)
        self.assertEqual(image.sector_offset(0, 1), 0)
        self.assertEqual(image.sector_offset(1, 1), 2*9*512)
        self.assertEqual(image.sector_offset(79, 9), (79*2*9+8)*512)
        self.assertEqual(image.sector_offset(128, 1), 9*512)
        self.assertEqual(image.sector_offset(207, 9), (80*2*9-1)*512)
        self.assertRaises(ValueError, image.sector_offset, 0, 0)
        self.assertRaises(ValueError, image.sector_offset, 0, 10)
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

    def test_edsk_sector_offsets_9spt(self):
        image = Image.open(f'{TESTDIR}/image9.dsk')
        self.assertEqual(image.sector_offset(0, 1), 0x100+0x100)
        self.assertEqual(image.sector_offset(0, 2), 0x100+0x100+512)
        self.assertEqual(image.sector_offset(1, 1), 0x100+(0x1300*2)+0x100+512)
        self.assertEqual(image.sector_offset(79, 9), 0x100+(0x1300*79*2)+0x100+6*512)
        self.assertEqual(image.sector_offset(128, 1), 0x100+(0x1300)+0x100)
        self.assertEqual(image.sector_offset(207, 9), 0x100+(0x1300*79*2+0x1300)+0x100+6*512)
        self.assertRaises(ValueError, image.sector_offset, -1, 1)
        self.assertRaises(ValueError, image.sector_offset, 0, 0)
        self.assertRaises(ValueError, image.sector_offset, 0, 10)
        self.assertRaises(ValueError, image.sector_offset, 80, 1)
        self.assertRaises(ValueError, image.sector_offset, 208, 1)

    def test_read_sector(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        data = image.read_sector(0, 1)
        self.assertEqual(len(data), 512)
        self.assertEqual(data[1:1+7], bytes('samdos2', 'ascii'))
        data = image.read_sector(4, 1)
        self.assertEqual(len(data), 512)
        self.assertEqual(data[315:315+7], bytes('samdos2', 'ascii'))

    def test_write_sector(self):
        image = MGTImage()
        data = bytes((x & 0xff for x in range(512)))
        image.write_sector(10, 5, data)
        self.assertEqual(image.read_sector(10, 5), data)
        self.assertRaises(ValueError, image.write_sector, 0, 1, bytes(511))
        self.assertRaises(ValueError, image.write_sector, 0, 1, bytes(513))

if __name__ == '__main__':
    unittest.main() # pragma: no cover
