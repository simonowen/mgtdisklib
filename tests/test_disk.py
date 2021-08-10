import os, unittest
from mgtdisklib import Disk, DiskType, FileType, Image, MGTImage

TESTDIR=os.path.join(os.path.split(__file__)[0], 'data')
TESTOUTPUTFILE=f'{TESTDIR}/__output__.mgt'

class DiskTests(unittest.TestCase):
    def test_construct(self):
        disk = Disk()
        self.assertEqual(disk.type, DiskType.SAMDOS)
        self.assertEqual(disk.dir_tracks, 4)
        self.assertEqual(disk.files, [])
        self.assertFalse(disk.compressed)
        self.assertIsNone(disk.label)
        self.assertIsNone(disk.serial)

    def test_open(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        self.assertIsNotNone(disk)

    def test_from_image(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        disk = Disk.from_image(image)
        disk2 = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')

        self.assertEqual(disk.type, disk2.type)
        self.assertEqual(disk.dir_tracks, disk2.dir_tracks)
        self.assertEqual(disk.label, disk2.label)
        self.assertEqual(disk.serial, disk2.serial)
        self.assertEqual(disk.compressed, disk2.compressed)
        self.assertEqual(len(disk.files), len(disk2.files))
        self.assertEqual(disk.files[0].data, disk2.files[0].data)

    def test_save(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        disk.save(TESTOUTPUTFILE)
        image = Image.open(TESTOUTPUTFILE)
        self.assertEqual(os.path.getsize(TESTOUTPUTFILE), 819200)
        self.assertEqual(len(image.data), 819200)
        os.remove(TESTOUTPUTFILE)

    def test_save_9spt(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        disk.save(TESTOUTPUTFILE, spt=9)
        image = Image.open(TESTOUTPUTFILE)
        self.assertEqual(os.path.getsize(TESTOUTPUTFILE), 737280)
        self.assertEqual(len(image.data), 737280)
        os.remove(TESTOUTPUTFILE)

    def test_to_image(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        image = disk.to_image()
        disk2 = Disk.from_image(image)

        self.assertEqual(len(image.data), 819200)
        self.assertEqual(disk.type, disk2.type)
        self.assertEqual(disk.dir_tracks, disk2.dir_tracks)
        self.assertEqual(disk.label, disk2.label)
        self.assertEqual(disk.serial, disk2.serial)
        self.assertEqual(disk.compressed, disk2.compressed)
        self.assertEqual(len(disk.files), len(disk2.files))
        self.assertEqual(disk.files[0].data, disk2.files[0].data)

    def test_to_image_9spt(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        image = disk.to_image(spt=9)
        disk2 = Disk.from_image(image)

        self.assertEqual(len(image.data), 737280)
        self.assertEqual(disk.type, disk2.type)
        self.assertEqual(disk.dir_tracks, disk2.dir_tracks)
        self.assertEqual(disk.label, disk2.label)
        self.assertEqual(disk.serial, disk2.serial)
        self.assertEqual(disk.compressed, disk2.compressed)
        self.assertEqual(len(disk.files), len(disk2.files))
        self.assertEqual(disk.files[0].data, disk2.files[0].data)

    def test_add_code_file(self):
        disk = Disk()
        self.assertEqual(len(disk.files), 0)
        disk.add_code_file(f'{TESTDIR}/samdos2')
        self.assertEqual(len(disk.files), 1)
        disk.add_code_file(f'{TESTDIR}/samdos2', filename='altname')
        self.assertEqual(len(disk.files), 2)
        self.assertEqual(disk.files[1].name, "altname")
        disk.add_code_file(f'{TESTDIR}/samdos2', filename='newname', at_index=1)
        self.assertEqual(len(disk.files), 3)
        self.assertEqual(disk.files[1].name, "newname")

    def test_delete(self):
        disk = Disk()
        self.assertEqual(len(disk.files), 0)
        disk.add_code_file(f'{TESTDIR}/samdos2')
        self.assertEqual(len(disk.files), 1)
        disk.add_code_file(f'{TESTDIR}/samdos2', filename='two')
        self.assertEqual(len(disk.files), 2)
        disk.add_code_file(f'{TESTDIR}/samdos2', filename='three')
        self.assertEqual(len(disk.files), 3)
        self.assertEqual(disk.delete('T*'), 2)
        self.assertEqual(len(disk.files), 1)

    def test_bam(self):
        disk = Disk()
        disk.add_code_file(f'{TESTDIR}/samdos2')
        disk = disk.from_image(disk.to_image())
        bam1 = disk.bam()
        self.assertEqual(bam1, disk.files[0].sector_map)
        disk.add_code_file(f'{TESTDIR}/samdos2', filename='two')
        disk = disk.from_image(disk.to_image())
        bam2 = disk.bam()
        self.assertEqual(bam2, disk.files[0].sector_map | disk.files[1].sector_map)
        disk.add_code_file(f'{TESTDIR}/samdos2', filename='three')
        disk = disk.from_image(disk.to_image())
        bam3 = disk.bam()
        self.assertEqual(bam3, disk.files[0].sector_map | disk.files[1].sector_map | disk.files[2].sector_map)

    def test_dir_position(self):
        self.assertEqual(Disk.dir_position(0), (0, 1, 0))
        self.assertEqual(Disk.dir_position(1), (0, 1, 256))
        self.assertEqual(Disk.dir_position(2), (0, 2, 0))
        self.assertEqual(Disk.dir_position(20), (1, 1, 0))
        self.assertEqual(Disk.dir_position(21), (1, 1, 256))
        self.assertEqual(Disk.dir_position(79), (3, 10, 256))

    def test_dir_position_9spt(self):
        self.assertEqual(Disk.dir_position(0, spt=9), (0, 1, 0))
        self.assertEqual(Disk.dir_position(1, spt=9), (0, 1, 256))
        self.assertEqual(Disk.dir_position(2, spt=9), (0, 2, 0))
        self.assertEqual(Disk.dir_position(18, spt=9), (1, 1, 0))
        self.assertEqual(Disk.dir_position(19, spt=9), (1, 1, 256))
        self.assertEqual(Disk.dir_position(71, spt=9), (3, 9, 256))

    def test_read_dir(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        data = Disk.read_dir(image, 0)
        self.assertEqual(data[0], 0x13)
        data = Disk.read_dir(image, 1)
        self.assertEqual(data[0], 0)
        self.assertRaises(IndexError, Disk.read_dir, image, -1)

    def test_write_dir(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        data = Disk.read_dir(image, 0)
        Disk.write_dir(image, 1, data)
        self.assertEqual(Disk.read_dir(image, 1), data)
        self.assertRaises(IndexError, Disk.write_dir, image, -1, data)

    def test_read_data(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        data = Disk.read_data(image, FileType.CODE, 20, 4, 1)
        self.assertEqual(len(data), 20*510)
        data = Disk.read_data(image, FileType.CODE, 20, 207, 10)
        self.assertEqual(len(data), 510)

    def test_write_data(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        data = Disk.read_data(image, FileType.CODE, 20, 4, 1)
        Disk.write_data(image, FileType.CODE, 4, 1, data)
        data2 = Disk.read_data(image, FileType.CODE, 20, 4, 1)
        self.assertEqual(data, data2)
        self.assertEqual(image.read_sector(4, 10)[510:], bytes((5, 1)))
        Disk.write_data, image, 207, 10, bytes(510)
        self.assertRaises(ValueError, Disk.write_data, image, FileType.CODE, 207, 10, bytes(2 * 510))

    def test_write_data_9spt(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        data = Disk.read_data(image, FileType.CODE, 20, 4, 1)
        image2 = MGTImage(spt=9)
        Disk.write_data(image2, FileType.CODE, 4, 1, data)
        data2 = Disk.read_data(image2, FileType.CODE, 20, 4, 1)
        self.assertEqual(data, data2)
        self.assertEqual(image2.read_sector(4, 9)[510:], bytes((5, 1)))
        Disk.write_data, image2, 207, 9, bytes(510)
        self.assertRaises(ValueError, Disk.write_data, image2, FileType.CODE, 207, 9, bytes(2 * 510))

    def test_next_sector(self):
        self.assertEqual(Disk.next_sector(0, 1), (0, 2))
        self.assertEqual(Disk.next_sector(0, 10), (1, 1))
        self.assertEqual(Disk.next_sector(79, 10), (128, 1))
        self.assertEqual(Disk.next_sector(128, 10), (129, 1))
        self.assertEqual(Disk.next_sector(207, 10), (208, 1))   # detected later

    def test_next_sector_9spt(self):
        self.assertEqual(Disk.next_sector(0, 1, spt=9), (0, 2))
        self.assertEqual(Disk.next_sector(0, 9, spt=9), (1, 1))
        self.assertEqual(Disk.next_sector(79, 9, spt=9), (128, 1))
        self.assertEqual(Disk.next_sector(128, 9, spt=9), (129, 1))
        self.assertEqual(Disk.next_sector(207, 9, spt=9), (208, 1))

if __name__ == '__main__':
    unittest.main()
