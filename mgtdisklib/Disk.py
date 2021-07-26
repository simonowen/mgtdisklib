# Disk wrapper for MGT logical disk format.
#
# Part of https://github.com/simonowen/mgtdisklib

import struct, fnmatch, operator, functools
from enum import Enum
from typing import Tuple

from .Image import Image, MGTImage
from .File import File, FileType

class DiskType(Enum):
    SAMDOS = 1
    MASTERDOS = 2
    BDOS = 3

class Disk:
    def __init__(self):
        self.type = DiskType.SAMDOS
        self.dir_tracks = 4
        self.label = None
        self.serial = 0
        self.files = []
        self.compressed = False

    @staticmethod
    def open(path: str):
        """Load disk from disk image file"""
        image = Image.open(path)
        return Disk.from_image(image)

    @staticmethod
    def from_image(image: Image):
        """Construct a Disk object from a disk image"""
        disk = Disk()

        entry0 = image.read_sector(0, 1)
        if entry0[232:232+4] == bytes('BDOS', 'ascii'):
            disk.type = DiskType.BDOS
            if entry0[210]:
                disk.label = entry0[210:210+10] + entry0[250:250+6]
        elif entry0[210] != 0 and entry0[210] != 0xff:
            disk.type = DiskType.MASTERDOS
            disk.dir_tracks = max(4, min(4 + entry0[255], 39))
            if entry0[210] != ord('*'):
                 disk.label = entry0[210:210+10]
            disk.serial = struct.unpack('<H', entry0[252:252+2])

        if disk.label:
            disk.label = bytes(map(lambda x: x & 0x7f, disk.label)).decode('ascii', errors='replace').rstrip()

        for i in range(disk.dir_tracks * image.spt * 2):
            entry = Disk.read_dir(image, i)
            file = File.from_dir(entry)
            if file.type:
                file.data = Disk.read_data(image, file.type, file.sectors, file.start_track, file.start_sector)
                disk.files.append(file)
            elif not file.name[0]:
                break

        return disk

    def save(self, path: str, *, compressed: bool = False, spt: int = 10) -> None:
        """Save disk content to disk image"""
        if spt <= 0:
            raise ValueError("invalid sectors per track")
        image = self.to_image(spt=spt)
        image.save(path, compressed=compressed)

    def to_image(self, *, spt: int = 10) -> Image:
        """Generate MGT disk image from current contents"""
        if spt <= 0:
            raise ValueError("invalid sectors per track")
        image = MGTImage(spt=spt)
        track, sector = self.dir_tracks, 1
        index = 0

        for file in self.files:
            if index >= self.dir_tracks * spt:
                raise RuntimeError("too many files for directory")
            entry = file.to_dir(track, sector, spt=image.spt)
            Disk.write_dir(image, index, entry)
            track, sector = Disk.write_data(image, file.type, track, sector, file.data)
            index += 1

        return image

    def add_code_file(self, path: str, *, filename: str = None, at_index: int = None) -> None:
        """Add CODE file from path"""
        file = File.from_code_path(path, filename=filename)
        self.delete(file.name)
        self.files.insert(len(self.files) if at_index is None else at_index, file)

    def delete(self, pattern: str) -> int:
        """Delete files matching filename pattern"""
        files = len(self.files)
        self.files = [file for file in self.files if not fnmatch.fnmatch(file.name, pattern)]
        return files - len(self.files)

    def bam(self) -> None:
        """Combined Bitmap Address Map for all files"""
        return functools.reduce(operator.or_, (file.sector_map for file in self.files))

    def dir(self, *, spt: int = 10) -> None:
        """Display directory listing"""
        print(f'* {self.label or self.type.name}:\n')

        for i, file in enumerate(self.files):
            print(f'{i+1:3}  {file}')

        total_sectors = (80 * 2 * spt * 512) // 512
        dir_sectors = self.dir_tracks * spt
        used_sectors = sum(file.sectors for file in self.files)
        free_sectors = total_sectors - dir_sectors - used_sectors

        free_slots = self.dir_tracks * spt * 2 - len(self.files)
        print(f"\n{len(self.files):2} files, {free_slots:2} free slots, {used_sectors/2:3}K used, {free_sectors/2:3}K free")

    @staticmethod
    def dir_position(index: int, spt: int = 10) -> Tuple:
        """Calculate offset in image for zero-based directory entry"""
        track = index // (spt * 2)
        sector = 1 + (index % (spt * 2)) // 2
        offset = (index % 2) * 256
        return track, sector, offset

    @staticmethod
    def read_dir(image: Image, index: int) -> bytes:
        """Read zero-based directory entry"""
        if index < 0:
            raise IndexError(f'invalid directory index ({index})')
        track, sector, offset = Disk.dir_position(index, image.spt)
        data = image.read_sector(track, sector)
        return data[offset:offset+256]

    @staticmethod
    def write_dir(image: Image, index: int, entry: bytes) -> None:
        """Write zero-based directory entry"""
        if index < 0:
            raise IndexError(f'invalid directory index ({index})')
        elif len(entry) != 256:
            raise ValueError('directory entry should be 256 bytes')
        track, sector, offset = Disk.dir_position(index, image.spt)
        data = bytearray(image.read_sector(track, sector))
        data[offset:offset+256] = entry
        image.write_sector(track, sector, data)

    @staticmethod
    def read_data(image: Image, type: FileType, sectors: int, track: int, sector: int) -> bytes:
        """Read file data"""
        data = b''
        try:
            if File.is_contig_data_type(type):
                for _ in range(sectors):
                    data += image.read_sector(track, sector)
                    track, sector = Disk.next_sector(track, sector, image.spt)
            else:
                for _ in range(sectors):
                    chunk = image.read_sector(track, sector)
                    data += chunk[:-2]
                    track, sector = chunk[-2:]
        except Exception as e:
            pass
        return data

    @staticmethod
    def write_data(image: Image, type: FileType, track: int, sector: int, data: int) -> None:
        """Write file data, returning next unused sector location"""
        chunk_size = File.data_bytes_per_sector(type)

        for i in range(len(data) // chunk_size):
            offset = i * chunk_size
            chunk = data[offset:offset+chunk_size]
            next_track, next_sector = Disk.next_sector(track, sector, image.spt)

            if chunk_size == 512:
                pass
            elif offset + chunk_size == len(data):
                chunk += b'\0\0'
            else:
                chunk += bytes((next_track, next_sector))

            try:
                image.write_sector(track, sector, chunk)
                track, sector = next_track, next_sector
            except:
                raise RuntimeError('data area is out of space')

        return track, sector

    @staticmethod
    def next_sector(track: int, sector: int, spt: int = 10) -> Tuple:
        sector += 1
        if sector > spt:
            sector = 1
            track += 1
            if track == 80:
                track = 128
        return track, sector
