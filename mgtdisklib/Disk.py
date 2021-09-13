# Disk wrapper for MGT logical disk format.
#
# Part of https://github.com/simonowen/mgtdisklib

import struct, fnmatch, operator, functools
from enum import Enum
from typing import List, Tuple, Optional
from bitarray import bitarray

from .Image import Image, MGTImage
from .File import File, FileType, TimeFormat

class DiskType(Enum):
    SAMDOS = 1
    MASTERDOS = 2
    BDOS = 3

class Disk:
    def __init__(self) -> None:
        self.type: DiskType = DiskType.SAMDOS
        self.dir_tracks: int = 4
        self.label: Optional[str] = None
        self.serial: Optional[int] = None
        self.files: List[File] = []
        self.compressed: bool = False

    def __str__(self) -> str:
        """String representation of Disk, as directory listing"""
        return self.dir()

    @staticmethod
    def open(path: str):
        """Load disk from disk image file"""
        image = Image.open(path)
        return Disk.from_image(image)

    @staticmethod
    def from_image(image: Image):
        """Construct a Disk object from a disk image"""
        disk = Disk()
        label_raw: Optional[bytes] = None

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

        for i in range(disk.dir_tracks * image.spt * 2):
            entry = Disk.read_dir(image, i)
            file = File.from_dir(entry)
            if file.type:
                file.data = Disk.read_data(image, file.type, file.sectors, file.start_track, file.start_sector)
                disk.files.append(file)
            elif not file.name:
                break

        return disk

    def save(self, path: str, *, compressed: bool = False, spt: int = 10) -> None:
        """Save disk content to disk image"""
        if spt <= 0:
            raise ValueError(f'invalid sectors per track ({spt})')
        image = self.to_image(spt=spt)
        image.save(path, compressed=compressed)

    def to_image(self, *, spt: int = 10) -> Image:
        """Generate MGT disk image from current contents"""
        if spt <= 0:
            raise ValueError(f'invalid sectors per track ({spt})')
        image = MGTImage(spt=spt)
        track, sector = self.dir_tracks, 1
        index = 0
        timefmt = TimeFormat.MASTERDOS if self.type is DiskType.MASTERDOS else TimeFormat.BDOS

        for file in self.files:
            if index >= self.dir_tracks * spt * 2:
                raise RuntimeError(f'too many files (>= {self.dir_tracks * spt * 2}) for directory')
            entry = file.to_dir(track, sector, spt=image.spt, timefmt=timefmt)
            track, sector = Disk.write_data(image, file.type, track, sector, file.data)
            Disk.write_dir(image, index, entry)
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
        self.files = [file for file in self.files if not fnmatch.fnmatch(file.name.lower(), pattern.lower())]
        return files - len(self.files)

    def bam(self) -> bitarray:
        """Combined Bitmap Address Map for all files"""
        return functools.reduce(operator.or_, (file.sector_map for file in self.files))

    def dir(self, *, spt: int = 10) -> str:
        """Generate directory listing"""
        str = f'* {self.label or self.type.name}:\n'

        for i, file in enumerate(self.files):
            str += f'{i+1:3}  {file}\n'

        total_sectors = (80 * 2 * spt * 512) // 512
        dir_sectors = self.dir_tracks * spt
        used_sectors = sum(file.sectors for file in self.files)
        free_sectors = total_sectors - dir_sectors - used_sectors

        free_slots = self.dir_tracks * spt * 2 - len(self.files)
        str += f"\n{len(self.files):2} files, {free_slots:2} free slots, {used_sectors/2:3}K used, {free_sectors/2:3}K free\n"
        return str

    @staticmethod
    def dir_position(index: int, spt: int = 10) -> Tuple[int, int, int]:
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
    def write_data(image: Image, type: FileType, track: int, sector: int, data: bytes) -> Tuple[int, int]:
        """Write file data, returning next unused sector location"""
        chunk_size = File.data_bytes_per_sector(type)

        for i in range(len(data) // chunk_size):
            offset = i * chunk_size
            chunk = data[offset:offset+chunk_size]

            try:
                next_track, next_sector = Disk.next_sector(track, sector, image.spt)
            except ValueError:
                raise RuntimeError('data area is out of space')

            if chunk_size == 512:
                pass
            elif offset + chunk_size == len(data):
                chunk += b'\0\0'
            else:
                chunk += bytes((next_track, next_sector))

            image.write_sector(track, sector, chunk)
            track, sector = next_track, next_sector

        return track, sector

    @staticmethod
    def next_sector(track: int, sector: int, spt: int = 10) -> Tuple[int, int]:
        """Determine next sector position after given sector"""
        if track < 0 or (track & 0x7f) >= 80 or sector < 1 or sector > spt:
            raise ValueError(f'invalid sector position (track {track} sector {sector})')
        sector += 1
        if sector > spt:
            sector = 1
            track += 1
            if track == 80:
                track = 128
        return track, sector
