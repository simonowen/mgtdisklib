# Image wrapper for disk image containers (MGT/IMG/SAD/EDSK).
#
# Part of https://github.com/simonowen/mgtdisklib
#
# SPDX-License-Identifier: MIT

import gzip
import io
import os
import zipfile
from typing import Optional


class Image:
    def __init__(self, *, spt: int = 10) -> None:
        self.path: Optional[str] = None
        self.spt: int = spt
        self.compressed: bool = False
        self.data: bytearray = bytearray(80 * 2 * self.spt * 512)

    @staticmethod
    def is_img_image(data: bytes) -> bool:
        """Attempt to detect a DISCiPLE .img format disk image"""
        if len(data) == 819200 and data[0:2] != b'\x00\x00':
            if data[0x51fe:0x5200] == b'\x04\x02':
                return True  # sector chain found
            elif data[0xd3:0xd3+9] != bytes(9) and data[0xd3:0xd3+9] == data[0x5000:0x5009]:
                return True  # file header matches
        return False

    @staticmethod
    def open(path: str) -> 'Image':
        """Create Image object from disk image file"""

        if not zipfile.is_zipfile(path):
            with open(path, 'rb') as f:
                data = f.read()
        else:
            with zipfile.ZipFile(path, 'r') as z:
                file_exts = ('.mgt', '.dsk', '.img', '.sad')
                files = [name for name in z.namelist() if any(ext in name.lower() for ext in file_exts)]
                if len(files) != 1:
                    raise RuntimeError(f'{path} must contain a single disk image')
                with z.open(files[0], 'r') as f:
                    data = f.read()

        compressed: bool = False
        if data[:2] == b'\x1f\x8b':
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as gf:
                data = gf.read()
                compressed = True

        image: Optional[Image] = None
        if Image.is_img_image(data):
            image = IMGImage()
            image.spt = 10
        elif len(data) == 819200 or len(data) == 737280:
            image = MGTImage()
            image.spt = len(data) // (80 * 2 * 512)
        elif len(data) == 819222 or len(data) == 737302:
            image = SADImage()
            image.spt = (len(data) - 22) // (80 * 2 * 512)
        elif len(data) == 860416 or len(data) == 778496:
            image = EDSKImage()
            image.spt = (((len(data) - 0x100) // (80 * 2)) - 0x100) // 512
        else:
            raise RuntimeError(f'{path} is not a supported disk image')

        image.path = os.path.abspath(path)
        image.data = bytearray(data)
        image.compressed = compressed
        return image

    def save(self, path: str, *, compressed: bool = False) -> None:
        """Save disk data to image file"""
        if compressed:
            with gzip.open(path, 'wb') as f:
                f.write(self.data)
        else:
            with open(path, 'wb') as f2:
                f2.write(self.data)

    def read_sector(self, track: int, sector: int) -> bytes:
        """Read sector data for given sector location"""

        offset = self.sector_offset(track, sector)
        return bytes(self.data[offset:offset+512])

    def write_sector(self, track: int, sector: int, data: bytes) -> None:
        """Write sector data to given sector location"""

        if len(data) != 512:
            raise ValueError('sector data should be 512 bytes')

        offset = self.sector_offset(track, sector)
        self.data[offset:offset+512] = data

    def sector_offset(self, track: int, sector: int) -> int:
        """Calculate sector data offset in disk image"""
        raise NotImplementedError('only available in Image subclasses')


class MGTImage(Image):
    def sector_offset(self, track: int, sector: int) -> int:
        """Calculate sector data offset in MGT image"""

        if track < 0 or (track & 0x7f) >= 80 or sector < 1 or sector > self.spt:
            raise ValueError(f'invalid sector location: track {track} sector {sector}')

        return ((track & 0x7f) * self.spt * 2 + (track >> 7) * self.spt + (sector - 1)) * 512


class IMGImage(Image):
    def sector_offset(self, track: int, sector: int) -> int:
        """Calculate sector data offset in IMG image"""

        if track < 0 or (track & 0x7f) >= 80 or sector < 1 or sector > self.spt:
            raise ValueError(f'invalid sector location track {track} sector {sector}')

        return (((track >> 7) * 80 + (track & 0x7f)) * self.spt + (sector - 1)) * 512


class SADImage(Image):
    def sector_offset(self, track: int, sector: int) -> int:
        """Calculate sector data offset in SAD image"""

        if track < 0 or (track & 0x7f) >= 80 or sector < 1 or sector > self.spt:
            raise ValueError(f'invalid sector location track {track} sector {sector}')

        return 22 + (((track >> 7) * 80 + (track & 0x7f)) * self.spt + (sector - 1)) * 512


class EDSKImage(Image):
    def sector_offset(self, track: int, sector: int) -> int:
        """Calculate sector data offset in EDSK image"""

        if track < 0 or (track & 0x7f) >= 80 or sector < 1 or sector > self.spt:
            raise ValueError(f'invalid sector location track {track} sector {sector}')

        track_offset = 0x100 + ((track & 0x7f) * 2 + (track >> 7)) * (0x100 + self.spt * 512)
        sectors = [self.data[track_offset + 0x1a + i * 8] for i in range(self.spt)]
        return track_offset + 0x100 + sectors.index(sector) * 512
