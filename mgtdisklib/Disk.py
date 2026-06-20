# Disk wrapper for MGT logical disk format.
#
# Part of https://github.com/simonowen/mgtdisklib
#
# SPDX-License-Identifier: MIT

import fnmatch
import operator
import random
import struct
from enum import Enum
from functools import reduce

from bitarray import bitarray

from .File import File, FileType, TimeFormat
from .Image import Image, MGTImage


class DiskType(Enum):
    SAMDOS = 1
    MASTERDOS = 2
    BDOS = 3


class Disk:
    __slots__ = ('type', 'path', 'dir_tracks', 'label', 'serial', 'files', 'compressed')

    def __init__(self) -> None:
        self.type: DiskType = DiskType.SAMDOS
        self.path: str | None = None
        self.dir_tracks: int = 4
        self.label: str | None = None
        self.serial: int | None = None
        self.files: list[File] = []
        self.compressed: bool = False

    def __str__(self) -> str:
        """String representation of Disk, as directory listing"""
        return self.dir()

    @property
    def bootable(self) -> bool:
        """True if disk is bootable due to first file entry"""
        return len(self.files) > 0 and self.files[0].bootable

    @property
    def sector_map(self) -> bitarray:
        """Combined Bitmap Address Map for all files"""
        return reduce(operator.or_, (file.sector_map for file in self.files))

    @property
    def dir_sector_map(self) -> bitarray:
        """Sector map for extended directory area (dir_tracks > 4)"""
        dir_map = File.empty_sector_map()
        if self.dir_tracks > 4:
            dir_map[1:((self.dir_tracks - 4) * 10)] = 1
        return dir_map

    @staticmethod
    def open(path: str) -> 'Disk':
        """Load disk from disk image file"""
        image = Image.open(path)
        return Disk.from_image(image)

    @staticmethod
    def from_image(image: Image) -> 'Disk':
        """Construct a Disk object from a disk image"""
        disk = Disk()
        disk.path = image.path
        disk.compressed = image.compressed
        label_raw: bytes | None = None

        entry0 = image.read_sector(0, 1)
        if entry0[232:232+4] == bytes('BDOS', 'ascii'):
            disk.type = DiskType.BDOS
            if entry0[210]:
                label_raw = entry0[210:210+10] + entry0[250:250+6]
        elif entry0[210] != 0 and entry0[210] != 0xff:
            disk.type = DiskType.MASTERDOS
            disk.dir_tracks = max(4, min(4 + entry0[255], 39))
            if entry0[210] != ord('*'):
                label_raw = entry0[210:210+10]
            disk.serial = struct.unpack('<H', entry0[252:252+2])[0]

        if label_raw:
            disk.label = bytes(map(lambda x: x & 0x7f, label_raw)).decode('ascii', errors='replace').rstrip()

        for i in range(Disk.dir_slots(disk.dir_tracks)):
            entry = Disk.read_dir(image, i)
            file = File.from_dir(entry)
            if file.type:
                Disk.read_data(image, file)
                disk.files.append(file)
            elif not file.name_raw[1]:
                break

        return disk

    def free_slots(self) -> int:
        """Number of free directory slots"""
        return max(0, Disk.dir_slots(self.dir_tracks) - len(self.files))

    def free_sectors(self) -> int:
        """Number of free data sectors"""
        total_sectors = 80 * 2 * 10
        dir_sectors = Disk.dir_slots(self.dir_tracks) // 2
        used_sectors = sum(file.sectors for file in self.files)
        return max(0, total_sectors - dir_sectors - used_sectors)

    def free_bytes(self, *, type: FileType = FileType.CODE) -> int:
        """Number of usable file data bytes"""
        return max(0, self.free_sectors() * File.data_bytes_per_sector(type) - File.type_header_size(type))

    def save(self, path: str | None = None, *, compressed: bool = False) -> None:
        """Save disk content to disk image"""
        path = path or self.path
        if not path:
            raise ValueError('save path is required')

        image = self.to_image()
        image.save(path, compressed=compressed)

    def validate(self) -> None:
        """Validate current disk settings"""

        unique_files = set(id(file) for file in self.files)
        if len(unique_files) != len(self.files):
            raise RuntimeError('duplicate file objects, expected unique copies')

        if self.dir_tracks > 4 and self.type is not DiskType.MASTERDOS:
            raise ValueError('extra directory tracks requires a MasterDOS disk')
        elif self.dir_tracks < 4 or self.dir_tracks > 39:
            raise ValueError('4 to 39 directory tracks are supported')

        dir_numbers = [file.dir for file in self.files if file.type == FileType.DIR and file.dir is not None]
        dup_dirs = [dir for dir in dir_numbers if dir_numbers.count(dir) > 1]
        if dup_dirs:
            raise RuntimeError(f'directory number used more than once: {", ".join(set(map(str, dup_dirs)))}')

        used_dirs = [file.dir for file in self.files if file.type != FileType.DIR and file.dir is not None]
        missing_dirs = [dir for dir in used_dirs if dir not in dir_numbers]
        if missing_dirs:
            raise RuntimeError(f'directory number used but not found: {", ".join(set(map(str, missing_dirs)))}')

        file_names = [file.name.lower().rstrip() for file in self.files]
        dup_names = [file.name for file in self.files if file_names.count(file.name.lower()) > 1]
        if dup_names:
            raise RuntimeError(f'duplicate filename found: {", ".join(set(dup_names))}')

        for file in self.files:
            file.validate()

        special_files = [x for x in self.files if x.type == FileType.SPECIAL]
        if special_files:
            special_map = reduce(operator.or_, (x.sector_map for x in special_files))
            special_count = sum(x.sector_map.count() for x in special_files)
            if special_map.count() != special_count:
                raise RuntimeError('SPECIAL file sector maps overlap')

    def to_image(self, *, reserved_map: bitarray | None = None) -> Image:
        """Generate MGT disk image from current contents"""
        self.validate()

        image = MGTImage()
        image.path = self.path
        timefmt = TimeFormat.BDOS if self.type is DiskType.BDOS else TimeFormat.MASTERDOS

        reserved_map = reserved_map or bitarray(1600, endian='little')
        data_sector_map = reserved_map[4*10:] | self.dir_sector_map

        special_files = [x for x in self.files if x.type == FileType.SPECIAL]
        if special_files:
            data_sector_map |= reduce(operator.or_, (x.sector_map for x in special_files))

        dir_sector_map = reserved_map[:self.dir_tracks*10]
        dir_sector_map |= (~self.dir_sector_map >> 4*10)[:self.dir_tracks*10]
        dir_slot_map = bitarray(''.join([f'{x}{x}' for x in dir_sector_map]))

        for file in self.files:
            dir_slot = dir_slot_map.find(0)
            if dir_slot < 0:
                raise RuntimeError('too many files for disk')
            dir_slot_map[dir_slot] = 1

            entry, data_sector_map = file.to_dir(data_sector_map, timefmt=timefmt)
            Disk.write_data(image, file)
            Disk.write_dir(image, dir_slot, entry)
            dir_slot += 1

        entry0 = bytearray(image.read_sector(0, 1))
        if self.type is DiskType.SAMDOS:
            entry0[210] = 0
        elif self.type is DiskType.MASTERDOS:
            if self.label:
                entry0[210:210+10] = bytes(self.label.ljust(10), 'ascii')[:10]
            else:
                entry0[210:210+1] = b'*'
            serial = self.serial or random.getrandbits(16)
            entry0[252:252+2] = struct.pack('<H', serial & 0xffff)
            entry0[255] = self.dir_tracks - 4
        elif self.type is DiskType.BDOS:
            entry0[232:232+4] = bytes('BDOS', 'ascii')
            if self.label:
                label_bytes = bytes((self.label or '').strip().ljust(16), 'ascii')[:16]
                entry0[210:210+10] = label_bytes[:10]
                entry0[250:250+6] = label_bytes[10:16]
        image.write_sector(0, 1, bytes(entry0))

        return image

    def add_code_file(self, path: str, *, filename: str | None = None, start: int = 0x8000,
                       execute: int | None = None, at_index: int | None = None) -> None:
        """Add CODE file from path"""
        file = File.from_code_path(path, filename=filename, start=start, execute=execute)
        self.delete(file.name)
        self.files.insert(len(self.files) if at_index is None else at_index, file)

    def add_code_bytes(self, data: bytes, *, filename: str, start: int = 0x8000,
                       execute: int | None = None, at_index: int | None = None) -> None:
        """Add CODE file from bytes"""
        file = File.from_code_bytes(data, filename=filename, start=start, execute=execute)
        self.delete(file.name)
        self.files.insert(len(self.files) if at_index is None else at_index, file)

    def find(self, pattern: str) -> list[File]:
        """Find files matching filename pattern"""
        return [file for file in self.files if fnmatch.fnmatch(file.name.lower(), pattern.lower())]

    def delete(self, pattern: str) -> list[str]:
        """Delete files matching filename pattern"""
        filenames = [file.name for file in self.find(pattern)]
        self.files = [file for file in self.files if file.name not in filenames]
        return filenames

    def dir(self) -> str:
        """Generate directory listing"""
        str = f'* {self.label or self.type.name}:\n'

        for i, file in enumerate(self.files):
            str += f'{i+1:3}{file}\n'

        used_sectors = sum(file.sectors for file in self.files)

        str += f'\n{len(self.files):2} files'
        str += f', {self.free_slots()} free slots'
        str += f', {self.free_sectors()} free sectors'
        str += f', {used_sectors/2:3}K used'
        str += f', {self.free_sectors()/2:3}K free\n'
        return str

    @staticmethod
    def dir_slots(dir_tracks: int = 4) -> int:
        """Calculate number of sectors used by directory"""
        if dir_tracks < 4 or dir_tracks > 39:
            raise ValueError(f'invalid number of directory tracks ({dir_tracks})')
        reserved_slots = 2 if dir_tracks > 4 else 0  # track 4 sector 1 is boot sector
        return (dir_tracks * 10 * 2) - reserved_slots

    @staticmethod
    def dir_position(index: int) -> tuple[int, int, int]:
        """Calculate offset in image for zero-based directory entry"""
        if index >= (4 * 10 * 2):
            index += 2  # skip track 4 sector 1
        track = index // (10 * 2)
        sector = 1 + (index % (10 * 2)) // 2
        offset = (index % 2) * 256
        return track, sector, offset

    @staticmethod
    def read_dir(image: Image, index: int) -> bytes:
        """Read zero-based directory entry"""
        if index < 0:
            raise IndexError(f'invalid directory index ({index})')
        track, sector, offset = Disk.dir_position(index)
        data = image.read_sector(track, sector)
        return data[offset:offset+256]

    @staticmethod
    def write_dir(image: Image, index: int, entry: bytes) -> None:
        """Write zero-based directory entry"""
        if index < 0:
            raise IndexError(f'invalid directory index ({index})')
        elif len(entry) != 256:
            raise ValueError('directory entry should be 256 bytes')
        track, sector, offset = Disk.dir_position(index)
        data = bytearray(image.read_sector(track, sector))
        data[offset:offset+256] = entry
        image.write_sector(track, sector, bytes(data))

    @staticmethod
    def read_data(image: Image, file: File) -> bytes:
        """Read file data"""

        chunk_size = File.data_bytes_per_sector(file.type)
        header_size = File.type_header_size(file.type)
        length = header_size + (file._length or 0)

        data = b''
        for track, sector in File.sector_list(file.sector_map):
            chunk = image.read_sector(track, sector)
            if chunk_size == 512:
                data += chunk
            else:
                data += chunk[:-2]

        file.header = data[:header_size]
        file.data = data[header_size:length]

        try:
            if file._save_mode == 2:
                file.data, file._data = File.uncompress_mode2(file.data), file.data
            elif file._save_mode == 3 and file.screen_mode is not None:
                file.data, file._data = File.uncompress_mode3(file.data, file.screen_mode), file.data
        except Exception:
            pass

        return file.data

    @staticmethod
    def write_data(image: Image, file: File) -> None:
        """Write file data"""
        chunk_size = File.data_bytes_per_sector(file.type)

        if len(file.header) != File.type_header_size(file.type):
            raise RuntimeError('file header size does not match file type')
        data = file.header + file.data

        if file.sector_map.count() != file.sectors:
            raise RuntimeError('file sector map does not match sector count')
        data_sectors = File.sector_list(file.sector_map)
        track, sector = data_sectors.pop(0)

        while len(data) > 0:
            next_track, next_sector = data_sectors.pop(0) if data_sectors else (0, 0)

            chunk = data[:chunk_size] + b'\0'*(chunk_size - len(data))
            data = data[chunk_size:]

            if chunk_size == 512:
                pass
            elif not data:
                chunk += b'\0\0'
            else:
                chunk += bytes((next_track, next_sector))

            image.write_sector(track, sector, chunk)
            track, sector = next_track, next_sector
