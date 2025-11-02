import copy
import os
import random
import unittest

from bitarray import bitarray

from mgtdisklib import Disk, DiskType, File, FileType, Image, MGTImage
from test_utils import TESTDIR, make_temp_file


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

    def test_open_masterdos_label(self):
        disk = Disk.open(f'{TESTDIR}/masterdos_label.mgt.gz')
        self.assertEqual(disk.type, DiskType.MASTERDOS)
        self.assertEqual(disk.label, 'ABCDEFGHIJ')

    def test_open_masterdos_short_label(self):
        disk = Disk.open(f'{TESTDIR}/masterdos_short_label.mgt.gz')
        self.assertEqual(disk.type, DiskType.MASTERDOS)
        self.assertEqual(disk.label, 'abc')

    def test_open_masterdos_no_label(self):
        disk = Disk.open(f'{TESTDIR}/masterdos_no_label.mgt.gz')
        self.assertEqual(disk.type, DiskType.MASTERDOS)
        self.assertIsNone(disk.label)

    def test_open_bdos_label(self):
        disk = Disk.open(f'{TESTDIR}/bdos_label.mgt.gz')
        self.assertEqual(disk.type, DiskType.BDOS)
        self.assertEqual(disk.label, 'ABCDEFGHIJKLMNOP')

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
        with make_temp_file('.mgt') as temp_path:
            disk.save(temp_path)
            image = Image.open(temp_path)
            self.assertEqual(os.path.getsize(temp_path), 819200)
            self.assertEqual(len(image.data), 819200)

    def test_to_image_empty(self):
        disk = Disk()
        disk.to_image()

    def test_to_image(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertFalse(disk2.compressed)

        self.assertEqual(len(image.data), 819200)
        self.assertEqual(disk.type, disk2.type)
        self.assertEqual(disk.dir_tracks, disk2.dir_tracks)
        self.assertEqual(disk.label, disk2.label)
        self.assertEqual(disk.serial, disk2.serial)
        self.assertEqual(len(disk.files), len(disk2.files))
        self.assertEqual(disk.files[0].data, disk2.files[0].data)

    def test_to_image_file_limit_samdos(self):
        disk = Disk()
        for i in range(80):
            disk.add_code_bytes(b'\x00', filename=f'file{i+1}')
        self.assertEqual(len(disk.files), 80)
        disk.to_image()
        disk.add_code_bytes(b'\x00', filename='file81')
        self.assertRaises(RuntimeError, Disk.to_image, disk)

    def test_to_image_file_limit_masterdos(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        disk.dir_tracks = 5
        for i in range(98):
            disk.add_code_bytes(b'\x00', filename=f'file{i+1}')
        self.assertEqual(len(disk.files), 98)
        disk.to_image()
        disk.add_code_bytes(b'\x00', filename='file99')
        self.assertRaises(RuntimeError, Disk.to_image, disk)

    def test_to_image_data_limit(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        raw_capacity = (76 + 80) * 10 * 510  # too big for a single file
        disk.files[0].data = bytes(0x7f800 - 9)  # 1024 full sectors
        raw_capacity -= (9 + disk.files[0].length)
        disk.files.append(copy.deepcopy(disk.files[0]))
        disk.files[1].name = 'other2'
        disk.files[1].data = bytes(raw_capacity - 9)  # remaining space
        disk.to_image()
        disk.files[1].data += bytes(1)
        self.assertRaises(RuntimeError, Disk.to_image, disk)

    def test_to_image_dir_tracks_types(self):
        disk = Disk()
        disk.type = DiskType.SAMDOS
        disk.dir_tracks = 5
        self.assertRaises(ValueError, Disk.to_image, disk)
        disk.type = DiskType.BDOS
        self.assertRaises(ValueError, Disk.to_image, disk)
        disk.type = DiskType.MASTERDOS
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk2.dir_tracks, 5)
        disk.dir_tracks = 39
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk2.dir_tracks, 39)
        disk.dir_tracks = 3
        self.assertRaises(ValueError, Disk.to_image, disk)
        disk.dir_tracks = 40
        self.assertRaises(ValueError, Disk.to_image, disk)

    def test_to_image_dir_tracks_extra(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        disk.dir_tracks = 5
        disk.add_code_file(f'{TESTDIR}/samdos2')
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk2.files[0].first_sector, (4, 1))
        self.assertEqual(disk2.sector_map[:30], bitarray('100000000011111111111111111110'))
        data = image.read_sector(4, 1)
        self.assertEqual(data[510], 5)
        self.assertEqual(data[511], 1)
        disk.dir_tracks = 39
        image = disk.to_image()

    def test_to_image_label_samdos(self):
        disk = Disk()
        disk.label = 'ABCDEFGHIJ'
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk.type, disk2.type)
        self.assertIsNone(disk2.label)

    def test_to_image_label_masterdos(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        disk.label = 'ABCDEFGHIJ'
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk.type, disk2.type)
        self.assertEqual(disk.label, disk2.label)

    def test_to_image_label_bdos(self):
        disk = Disk()
        disk.type = DiskType.BDOS
        disk.label = 'ABCDEFGHIJKLMNOP'
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk.type, disk2.type)
        self.assertEqual(disk.label, disk2.label)

    def test_to_image_label_blank_masterdos(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk.type, disk2.type)
        self.assertIsNone(disk2.label)

    def test_to_image_label_blank_bdos(self):
        disk = Disk()
        disk.type = DiskType.BDOS
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk.type, disk2.type)
        self.assertIsNone(disk2.label)

    def test_to_image_label_blank_marker_masterdos(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        disk.label = '*'
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk.type, disk2.type)
        self.assertIsNone(disk2.label)

    def test_to_image_label_and_serial_masterdos(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        disk.label = 'ABCDEFGHIJ'
        disk.serial = 0x1234
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk.type, disk2.type)
        self.assertEqual(disk.label, disk2.label)
        self.assertEqual(disk.serial, disk2.serial)

    def test_to_image_serial_masterdos(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        disk.serial = 0x1234
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk.type, disk2.type)
        self.assertEqual(disk.serial, disk2.serial)

    def test_to_image_reserved_dir(self):
        disk = Disk()
        reserved_map = bitarray(1600, endian='little')
        reserved_map[0:10] = 1
        disk.add_code_file(f'{TESTDIR}/samdos2')
        image = disk.to_image(reserved_map=reserved_map)
        dir_data = image.read_sector(1, 1)
        self.assertEqual(dir_data[1:1+7], 'samdos2'.encode('ascii'))
        reserved_map[5] = 0
        image = disk.to_image(reserved_map=reserved_map)
        dir_data = image.read_sector(0, 6)
        self.assertEqual(dir_data[1:1+7], 'samdos2'.encode('ascii'))

    def test_to_image_reserved_data(self):
        disk = Disk()
        reserved_map = bitarray(1600, endian='little')
        for t in range(4, 6, 1):
            for s in range(10):
                reserved_map[t * 10 + s] = 1
        disk.add_code_file(f'{TESTDIR}/samdos2')
        image = disk.to_image(reserved_map=reserved_map)
        disk2 = Disk.from_image(image)
        self.assertEqual(disk2.files[0]._first_sector, (6, 1))
        data = image.read_sector(6, 1)
        self.assertEqual(data[9:510], disk.files[0].data[:510-9])

    def test_to_image_special_fixed(self):
        disk = Disk()
        disk.add_code_bytes(bytes(512*5), filename='special')
        disk.files[0].type = FileType.SPECIAL
        disk.files[0].sector_map.setall(0)
        disk.files[0].sector_map[5:10] = 1
        disk.add_code_bytes(bytes(510*10-9), filename='code')
        image = disk.to_image()
        disk2 = Disk.from_image(image)
        self.assertEqual(disk2.files[0].sector_map[:16], bitarray("0000011111000000"))
        self.assertEqual(disk2.files[1].sector_map[:16], bitarray("1111100000111110"))

    def test_validate_empty(self):
        disk = Disk()
        Disk.validate(disk)

    def test_validate_duplicate_file_obj(self):
        disk = Disk.open(f'{TESTDIR}/dir.mgt.gz')
        disk.files.append(disk.files[0])
        self.assertRaises(RuntimeError, Disk.validate, disk)

    def test_validate_duplicate_dirs(self):
        disk = Disk.open(f'{TESTDIR}/dir.mgt.gz')
        disk.files.append(copy.deepcopy(disk.files[0]))
        disk.files[1].name = 'other'
        self.assertRaises(RuntimeError, Disk.validate, disk)

    def test_validate_missing_dir(self):
        disk = Disk.open(f'{TESTDIR}/dir.mgt.gz')
        self.assertEqual(disk.files[0].dir, disk.files[1].dir)
        disk.files[0].dir = 2
        self.assertRaises(RuntimeError, Disk.validate, disk)

    def test_validate_duplicate_filename(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        disk.files.append(copy.deepcopy(disk.files[0]))
        disk.files[1].name = 'different'
        disk.validate()
        disk.files[1].name = disk.files[0].name
        self.assertEqual(len(disk.files), 2)
        self.assertRaises(RuntimeError, Disk.validate, disk)

    def test_validate_special_overlap(self):
        disk = Disk()
        special_data = bytes(512 * 10)
        disk.add_code_bytes(special_data, filename='special1')
        disk.files[0].type = FileType.SPECIAL
        disk.files[0].sector_map.setall(0)
        disk.files[0].sector_map[0:10] = 1
        disk.add_code_bytes(special_data, filename='special2')
        disk.files[1].type = FileType.SPECIAL
        disk.files[1].sector_map.setall(0)
        disk.files[1].sector_map[5:15] = 1
        self.assertRaises(RuntimeError, Disk.validate, disk)

    def test_bootable_empty(self):
        disk = Disk()
        self.assertFalse(disk.bootable)

    def test_bootable_samdos2(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        self.assertTrue(disk.bootable)

    def test_bootable_basic(self):
        disk = Disk.open(f'{TESTDIR}/zx_basic_auto.mgt.gz')
        self.assertFalse(disk.bootable)

    def test_free_slots_samdos(self):
        disk = Disk()
        self.assertEqual(disk.free_slots(), 80)
        disk.add_code_bytes(b'\x00', filename='fileA')
        self.assertEqual(disk.free_slots(), 79)
        for i in range(78):
            disk.add_code_bytes(b'\x00', filename=f'file{i}')
        self.assertEqual(disk.free_slots(), 1)
        disk.add_code_bytes(b'\x00', filename='fileB')
        self.assertEqual(disk.free_slots(), 0)
        disk.add_code_bytes(b'\x00', filename='fileB')
        self.assertEqual(disk.free_slots(), 0)  # clipped, checked in to_image()

    def test_free_slots_masterdos(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        disk.dir_tracks = 5
        self.assertEqual(disk.free_slots(), 98)
        disk.add_code_bytes(b'\x00', filename='fileA')
        self.assertEqual(disk.free_slots(), 97)
        for i in range(96):
            disk.add_code_bytes(b'\x00', filename=f'file{i}')
        self.assertEqual(disk.free_slots(), 1)
        disk.add_code_bytes(b'\x00', filename='fileB')
        self.assertEqual(disk.free_slots(), 0)

    def test_free_sectors_samdos(self):
        disk = Disk()
        self.assertEqual(disk.free_sectors(), (160 - 4) * 10)
        disk.add_code_file(f'{TESTDIR}/samdos2')
        file = disk.files[0]
        self.assertEqual(disk.free_sectors(), (160 - 4) * 10 - file.sectors)
        file.data = b'\x00' * (((160 - 4) * 10 * 510) - 9 - 510)  # leave 1 sector
        self.assertEqual(disk.free_sectors(), 1)
        file.data += b'\x00'  # use a byte of final sector
        self.assertEqual(disk.free_sectors(), 0)
        file.data += b'\x00' * 510
        self.assertEqual(disk.free_sectors(), 0)  # clipped, checked in to_image()

    def test_free_sectors_masterdos(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        disk.dir_tracks = 5
        self.assertEqual(disk.free_sectors(), (160 - 5) * 10 + 1)
        disk.dir_tracks = 39
        self.assertEqual(disk.free_sectors(), (160 - 39) * 10 + 1)

    def test_free_bytes_samdos(self):
        disk = Disk()
        self.assertEqual(disk.free_bytes(), (160 - 4) * 10 * 510 - 9)
        self.assertEqual(disk.free_bytes(type=FileType.SPECIAL), (160 - 4) * 10 * 512)
        disk.add_code_file(f'{TESTDIR}/samdos2')
        file = disk.files[0]
        self.assertEqual(disk.free_bytes(), ((160 - 4) * 10 - file.sectors) * 510 - 9)
        file.data = b'\x00' * (((160 - 4) * 10 * 510) - 9 - 510)  # leave 1 sector
        self.assertEqual(disk.free_bytes(), 510 - 9)
        file.data += b'\x00'  # use a byte of final sector
        self.assertEqual(disk.free_bytes(), 0)
        file.data += b'\x00' * 510
        self.assertEqual(disk.free_bytes(), 0)  # clipped, checked in to_image()

    def test_free_bytes_masterdos(self):
        disk = Disk()
        disk.type = DiskType.MASTERDOS
        disk.dir_tracks = 39
        self.assertEqual(disk.free_bytes(), ((160 - 39) * 10 + 1) * 510 - 9)
        self.assertEqual(disk.free_bytes(type=FileType.SPECIAL), ((160 - 39) * 10 + 1) * 512)

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

    def test_add_code_bytes(self):
        disk = Disk()
        self.assertEqual(len(disk.files), 0)
        with open(f'{TESTDIR}/samdos2', 'rb') as f:
            data = f.read()
        disk.add_code_bytes(data, filename='samdos2')
        self.assertEqual(len(disk.files), 1)
        self.assertEqual(disk.files[0].name, 'samdos2')
        self.assertEqual(disk.files[0].data, data)
        disk.add_code_bytes(data, filename='file2')
        self.assertEqual(len(disk.files), 2)
        self.assertEqual(disk.files[1].name, 'file2')
        disk.add_code_bytes(data, filename='file3', at_index=1)
        self.assertEqual(len(disk.files), 3)
        self.assertEqual(disk.files[1].name, 'file3')
        self.assertEqual(disk.files[2].name, 'file2')

    def test_find_glob(self):
        disk = Disk.open(f'{TESTDIR}/masterdos_dir_5trk.mgt.gz')
        self.assertEqual([x.name for x in disk.find("*7")], ['7', '17', '27', '37', '47', '57', '67', '77', '87', '97'])
        self.assertEqual([x.name for x in disk.find("8*")], ['8', '80', '81', '82', '83', '84', '85', '86', '87', '88', '89'])
        self.assertEqual([x.name for x in disk.find("?7")], ['17', '27', '37', '47', '57', '67', '77', '87', '97'])
        self.assertEqual(len([x.name for x in disk.find("*7*")]), 19)
        self.assertEqual(len([x.name for x in disk.find("?")]), 9)
        self.assertEqual(len([x.name for x in disk.find("??")]), 89)
        self.assertEqual(len([x.name for x in disk.find("???")]), 0)
        self.assertEqual(len([x.name for x in disk.find("")]), 0)
        self.assertEqual(len([x.name for x in disk.find("foo")]), 0)

    def test_find_case(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        self.assertEqual([x.name for x in disk.find("samdos2")], ['samdos2'])
        self.assertEqual([x.name for x in disk.find("SAMDOS2")], ['samdos2'])
        self.assertEqual([x.name for x in disk.find("SamDos2")], ['samdos2'])

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

    def test_sector_map(self):
        disk = Disk()
        disk.add_code_file(f'{TESTDIR}/samdos2')
        disk = disk.from_image(disk.to_image())
        bam1 = disk.sector_map
        self.assertEqual(bam1, disk.files[0].sector_map)
        disk.add_code_file(f'{TESTDIR}/samdos2', filename='two')
        disk = disk.from_image(disk.to_image())
        bam2 = disk.sector_map
        self.assertEqual(bam2, disk.files[0].sector_map | disk.files[1].sector_map)
        disk.add_code_file(f'{TESTDIR}/samdos2', filename='three')
        disk = disk.from_image(disk.to_image())
        bam3 = disk.sector_map
        self.assertEqual(bam3, disk.files[0].sector_map | disk.files[1].sector_map | disk.files[2].sector_map)

    def test_dir_map(self):
        bam_bits = (80 * 2 - 4) * 10
        disk = Disk()
        self.assertEqual(disk.dir_sector_map, bitarray(bam_bits))
        disk.type = DiskType.MASTERDOS
        disk.dir_tracks = 5
        self.assertEqual(disk.dir_sector_map[:11], bitarray('0' + ('1' * ((5 - 4) * 10 - 1)) + '0'))
        disk.dir_tracks = 39
        self.assertEqual(disk.dir_sector_map[:351], bitarray('0' + ('1' * ((39 - 4) * 10 - 1)) + '0'))

    def test_dir_tracks_read(self):
        disk = Disk.open(f'{TESTDIR}/masterdos_dir_39trk.mgt.gz')
        self.assertEqual(disk.type, DiskType.MASTERDOS)
        self.assertEqual(disk.dir_tracks, 39)
        disk = Disk.open(f'{TESTDIR}/masterdos_dir_5trk.mgt.gz')
        self.assertEqual(disk.type, DiskType.MASTERDOS)
        self.assertEqual(disk.dir_tracks, 5)
        self.assertEqual(disk.files[0].first_sector, (4, 1))
        self.assertEqual(disk.files[80-1].name, '80')
        self.assertEqual(disk.files[81-1].name, '81')
        self.assertEqual(disk.files[82-1].name, '82')
        self.assertEqual(disk.files[83-1].name, '83')
        self.assertEqual(disk.files[98-1].name, '98')

    def test_dir_sectors(self):
        self.assertEqual(Disk.dir_slots(4), 80)
        self.assertEqual(Disk.dir_slots(5), 98)  # track 4 sector 1 is boot sector
        self.assertEqual(Disk.dir_slots(6), 118)
        self.assertEqual(Disk.dir_slots(39), 778)
        self.assertRaises(ValueError, Disk.dir_slots, -1)
        self.assertRaises(ValueError, Disk.dir_slots, 0)
        self.assertRaises(ValueError, Disk.dir_slots, 3)
        self.assertRaises(ValueError, Disk.dir_slots, 40)

    def test_dir_position(self):
        self.assertEqual(Disk.dir_position(0), (0, 1, 0))
        self.assertEqual(Disk.dir_position(1), (0, 1, 256))
        self.assertEqual(Disk.dir_position(2), (0, 2, 0))
        self.assertEqual(Disk.dir_position(20), (1, 1, 0))
        self.assertEqual(Disk.dir_position(21), (1, 1, 256))
        self.assertEqual(Disk.dir_position(79), (3, 10, 256))
        self.assertEqual(Disk.dir_position(80), (4, 2, 0))
        self.assertEqual(Disk.dir_position(81), (4, 2, 256))
        self.assertEqual(Disk.dir_position(82), (4, 3, 0))
        self.assertEqual(Disk.dir_position(97), (4, 10, 256))
        self.assertEqual(Disk.dir_position(98), (5, 1, 0))

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
        self.assertRaises(ValueError, Disk.write_dir, image, 0, bytes(0))
        self.assertRaises(ValueError, Disk.write_dir, image, 0, bytes(255))
        self.assertRaises(ValueError, Disk.write_dir, image, 0, bytes(257))

    def test_read_data(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        file = Disk.from_image(image).files[0]
        header, data = file.header, file.data
        data_ret = Disk.read_data(image, file)
        self.assertEqual(file.data, data_ret)
        self.assertEqual(file.header, header)
        self.assertEqual(file.data, data)
        self.assertEqual(len(file.data), 10000)

    def test_read_data_contig(self):
        image = Image.open(f'{TESTDIR}/emptycpm.mgt.gz')
        file = Disk.from_image(image).files[0]
        self.assertEqual(file.sectors, 80*2*9)
        data_ret = Disk.read_data(image, file)
        self.assertEqual(file.data, data_ret)
        self.assertEqual(file.header, b'')
        self.assertEqual(file.data, bytes(b'\xe5' * 80*2*9*512))

    def test_read_data_uncompress_fail(self):
        image = Image.open(f'{TESTDIR}/mbasic_compress_screen.mgt.gz')
        file = Disk.from_image(image).files[11]
        data_sectors = File.sector_list(file.sector_map)
        image.write_sector(*data_sectors[-1], bytes(512))  # corrupt last sector
        file = Disk.from_image(image).files[11]
        self.assertEqual(file.length, 9171)
        self.assertIsNone(file._data)

    def test_write_data(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        file = Disk.from_image(image).files[0]
        self.assertEqual(file.type, FileType.CODE)
        header, data = file.header, file.data
        Disk.write_data(image, file)
        Disk.read_data(image, file)
        self.assertEqual(file.header, header)
        self.assertEqual(file.data, data)
        self.assertEqual(image.read_sector(4, 10)[510:], bytes((5, 1)))

    def test_write_data_contig(self):
        image = MGTImage()
        file = Disk.open(f'{TESTDIR}/emptycpm.mgt.gz').files[0]
        self.assertEqual(file.type, FileType.SPECIAL)
        file.data = random.getrandbits(80*2*9*512 * 8).to_bytes(80*2*9*512, 'little')
        file.allocate()
        Disk.write_data(image, file)
        data2 = b''.join([image.read_sector((t % 80) + (128 if t >= 80 else 0), s)
                         for t in range(4, 4+file.sectors//10) for s in range(1, 11, 1)])
        self.assertEqual(file.data, data2)
        file.header = bytes(9)
        self.assertRaises(RuntimeError, Disk.write_data, image, file)

    def test_write_data_header_size(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        file = Disk.from_image(image).files[0]
        file.header = bytes()
        self.assertRaises(RuntimeError, Disk.write_data, image, file)
        image = Image.open(f'{TESTDIR}/emptycpm.mgt.gz')
        file = Disk.from_image(image).files[0]
        file.header = bytes(9)
        self.assertRaises(RuntimeError, Disk.write_data, image, file)

    def test_write_data_short_map(self):
        image = Image.open(f'{TESTDIR}/samdos2.mgt.gz')
        file = Disk.from_image(image).files[0]
        self.assertEqual(file.type, FileType.CODE)
        file.sector_map[file.sector_map.index(1)] = 0  # remove 1 sector
        self.assertRaises(RuntimeError, Disk.write_data, image, file)

    def test_str(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        dir = str(disk).splitlines()
        self.assertEqual(dir[0], '* SAMDOS:')
        self.assertEqual(dir[-1], ' 1 files, 79 free slots, 1540 free sectors, 10.0K used, 770.0K free')

        disk = Disk.open(f'{TESTDIR}/masterdos_label.mgt.gz')
        dir = str(disk).splitlines()
        self.assertEqual(dir[0], '* ABCDEFGHIJ:')

        disk = Disk.open(f'{TESTDIR}/masterdos_no_label.mgt.gz')
        dir = str(disk).splitlines()
        self.assertEqual(dir[0], '* MASTERDOS:')

        disk = Disk.open(f'{TESTDIR}/bdos_label.mgt.gz')
        dir = str(disk).splitlines()
        self.assertEqual(dir[0], '* ABCDEFGHIJKLMNOP:')

    def test_dir(self):
        disk = Disk.open(f'{TESTDIR}/samdos2.mgt.gz')
        dir = disk.dir().splitlines()
        self.assertEqual(len(dir), 4)


if __name__ == '__main__':
    unittest.main()  # pragma: no cover
