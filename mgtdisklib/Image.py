# Image wrapper for disk image containers (MGT/SAD/EDSK).
#
# Part of https://github.com/simonowen/mgtdisklib

import os, gzip
from typing import Optional

class Image:
    def __init__(self, *, spt: int = 10) -> None:
        self.path: Optional[str] = None
        self.spt: int = spt
        self.compressed: bool = False
        self.data: bytearray = bytearray(80 * 2 * self.spt * 512)

    @staticmethod
    def open(path: str):
        """Create Image object from disk image file"""
        with open(path, 'rb') as f:
            data = bytearray(f.read())
            if data[:2] == b'\x1f\x8b':
                with gzip.open(path, 'rb') as f:
                    data = bytearray(f.read())
                    compressed = True
            else:
                compressed = False

        if len(data) == 819200 or len(data) == 737280:
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
        image.data = data
        image.compressed = compressed
        return image

    def save(self, path: str, *, compressed: bool = False) -> None:
        """Save disk data to image file"""
        if compressed:
            with gzip.open(path, 'wb') as f:
                f.write(self.data)
        else:
            with open(path, 'wb') as f:
                f.write(self.data)

    def read_sector(self, track: int, sector: int) -> bytes:
        """Read sector data for given sector location"""

        offset = self.sector_offset(track, sector)
        #print(f'Reading track {track} sector {sector} @{offset}')
        return bytes(self.data[offset:offset+512])

    def write_sector(self, track: int, sector: int, data: bytes) -> None:
        """Write sector data to given sector location"""

        if len(data) != 512:
            raise ValueError('sector data should be 512 bytes')

        offset = self.sector_offset(track, sector)
        #print(f'Writing track {track} sector {sector} @{offset}')
        self.data[offset:offset+512] = data

    def sector_offset(self, track: int, sector: int) -> int:
        """Calculate sector data offset in image data"""

        if track < 0 or (track & 0x7f) >= 80 or sector < 1 or sector > self.spt:
            raise ValueError(f'invalid sector location: track {track} sector {sector}')

        return ((track & 0x7f) * self.spt * 2 + (track >> 7) * self.spt + (sector - 1)) * 512

class MGTImage(Image):
    pass

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
