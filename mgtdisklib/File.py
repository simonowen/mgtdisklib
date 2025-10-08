# File wrapper for MGT directory entries plus data.
#
# Part of https://github.com/simonowen/mgtdisklib
#
# SPDX-License-Identifier: MIT

import os
import struct
from datetime import datetime
from enum import Enum, IntEnum
from typing import Optional, Tuple

from bitarray import bitarray


class FileType(IntEnum):
    NONE = 0
    ZX_BASIC = 1
    ZX_DATA = 2
    ZX_DATA_STR = 3
    ZX_CODE = 4
    ZX_SNP_48K = 5
    ZX_MDRV = 6
    ZX_SCREEN = 7
    SPECIAL = 8
    ZX_SNP_128K = 9
    OPENTYPE = 10
    ZX_EXECUTE = 11
    UNIDOS_DIR = 12
    UNIDOS_CREATE = 13
    UNUSED_14 = 14
    UNUSED_15 = 15
    BASIC = 16
    DATA = 17
    DATA_STR = 18
    CODE = 19
    SCREEN = 20
    DIR = 21
    DRIVER_APP = 22
    DRIVER_BOOT = 23
    EDOS_NOMEN = 24
    EDOS_SYSTEM = 25
    EDOS_OVERLAY = 26
    UNUSED_27 = 27
    HDOS_DOS = 28
    HDOS_DIR = 29
    HDOS_DISK = 30
    HDOS_TEMP = 31


TYPE_NAMES = {
    FileType.NONE: '<none>',
    FileType.ZX_BASIC: 'ZX BASIC',
    FileType.ZX_DATA: 'ZX DATA ()',
    FileType.ZX_DATA_STR: 'ZX DATA $()',
    FileType.ZX_CODE: 'ZX CODE',
    FileType.ZX_SNP_48K: 'ZX SNP 48K',
    FileType.ZX_MDRV: 'ZX MDRV',
    FileType.ZX_SCREEN: 'ZX SCREEN$',
    FileType.SPECIAL: 'SPECIAL',
    FileType.ZX_SNP_128K: 'ZX SNP 128K',
    FileType.OPENTYPE: 'OPENTYPE',
    FileType.ZX_EXECUTE: 'ZX EXECUTE',
    FileType.UNIDOS_DIR: 'UNIDOS DIR',
    FileType.UNIDOS_CREATE: 'UNIDOS CREATE',
    FileType.BASIC: 'BASIC',
    FileType.DATA: 'DATA ()',
    FileType.DATA_STR: 'DATA $',
    FileType.CODE: 'CODE',
    FileType.SCREEN: 'SCREEN$',
    FileType.DIR: '<DIR>',
    FileType.DRIVER_APP: 'DRIVER APP',
    FileType.DRIVER_BOOT: 'DRIVER BOOT',
    FileType.EDOS_NOMEN: 'EDOS NOMEN',
    FileType.EDOS_SYSTEM: 'EDOS SYSTEM',
    FileType.EDOS_OVERLAY: 'EDOS OVERLAY',
    FileType.HDOS_DOS: 'HDOS DOS',
    FileType.HDOS_DIR: 'HDOS DIR',
    FileType.HDOS_DISK: 'HDOS DISK',
    FileType.HDOS_TEMP: 'HDOS TEMP',
}


class TimeFormat(Enum):
    MASTERDOS = 0
    BDOS = 1
    BDOS17 = 2


class File:
    HEADER_SIZE = 9

    def __init__(self) -> None:
        self.entry: bytes = bytes(256)
        self.type: FileType = FileType.NONE
        self.hidden: bool = False
        self.protected: bool = False
        self.name_raw: bytes = bytes()
        self.name: str = ''
        self.start_track: Optional[int] = None
        self.start_sector: Optional[int] = None
        self.sector_map: bitarray = bitarray(endian='little')
        self.start: Optional[int] = None
        self.execute: Optional[int] = None
        self.basic_length: Optional[int] = None
        self.time: Optional[datetime] = None
        self.dir: Optional[int] = None
        self.data_var: Optional[str] = None
        self.screen_mode: Optional[int] = None
        self.header = bytes()
        self.data = bytes()

    def __str__(self) -> str:
        """String representation of File, like directory text"""
        str = f'{self.name:10} {self.sectors:4}  '

        str += TYPE_NAMES.get(self.type, 'WHAT?')

        if self.type == FileType.BASIC:
            if self.execute is not None:
                str += f'{self.execute:6}'
        elif self.type == FileType.CODE:
            str += f' {self.start:6},{self.length}'
            if self.execute is not None:
                str += f',{self.execute}'
        elif self.type == FileType.SCREEN:
            str += f' [mode {self.screen_mode}]'
        elif self.type in (FileType.DATA, FileType.DATA_STR, FileType.ZX_DATA, FileType.ZX_DATA_STR):
            str += f' [{self.data_var}]'
        elif self.type == FileType.ZX_BASIC:
            if self.execute is not None:
                str += f'{self.execute:6}'
        elif self.type == FileType.ZX_CODE:
            str += f' {self.start:6},{self.length}'
            if self.execute is not None:
                str += f',{self.execute}'

        if self.time is not None:
            str = f'{str:43}' + self.time.strftime('%d/%m/%Y %H:%M')
        return str

    @staticmethod
    def from_code_path(path: str, *, filename: Optional[str] = None, start: int = 0x8000,
                       execute: Optional[int] = None) -> 'File':
        """Create CODE file from path"""

        with open(path, 'rb') as f:
            data = f.read()

        filename = filename or os.path.splitext(os.path.basename(path))[0][:10]
        return File.from_code_bytes(data, filename, start=start, execute=execute)

    @staticmethod
    def from_code_bytes(data: bytes, filename: str, *, start: int = 0x8000,
                        execute: Optional[int] = None) -> 'File':
        """Create CODE file from bytes"""

        file, _ = File.from_dir(bytes(256))
        file.type = FileType.CODE
        file.name = filename
        file.name_raw = bytes(f'{filename:10}', 'ascii')
        file.start = start
        file.execute = execute
        file.data = data
        return file

    @staticmethod
    def from_path(path: str) -> 'File':
        """Import file entry exported using save()"""

        with open(path, 'rb') as f:
            file, _ = File.from_dir(f.read(256))
            if file.type != FileType.NONE:
                file.data = f.read()
            return file

    @staticmethod
    def from_dir(data: bytes) -> Tuple['File', int]:
        """Create from 256-byte directory entry data, returns data length"""

        file = File()
        file.entry = data
        file.type = FileType(data[0] & 0x1f)
        file.hidden = True if data[0] & 0x80 else False
        file.protected = True if data[0] & 0x40 else False
        file.name_raw = data[1:1+10]
        file.name = file.name_raw.decode('ascii', errors='replace')[:10].rstrip(' \0')
        file.start_track = data[13]
        file.start_sector = data[14]
        file.sector_map = bitarray(endian='little')
        file.sector_map.frombytes(data[15:15+195])
        file.time = File.unpack_time(data[245:245+5]) if File.is_sam_file_type(file.type) else None

        num_sectors = file.sector_map.count(1)  # trust bitmap over stored sector count [see MNEMOdemo1]
        length = 0

        # zx_tape_id = data[211]
        zx_length = (data[210] * 0x10000) + File.le_word(data[212:212+2])
        zx_start = File.le_word(data[214:214+2])
        zx_basic_length = File.le_word(data[216:216+2])
        zx_autorun = None if data[219] == 0xff else File.le_word(data[218:218+2])
        zx_execute = None if data[219] == 0x00 else File.le_word(data[218:218+2])
        zx_datavar = chr(ord('a') + (data[216] & 0x3f) - 1)

        sam_start = File.triple_to_addr(data[236:236+3])
        sam_length = File.triple_to_len(data[239:239+3])
        sam_execute = File.triple_to_exec(data[242:242+3])
        sam_autorun = File.triple_to_line(data[242:242+3])
        sam_datavar = data[222:222+(data[221] & 0xf)].decode('ascii', errors='replace')

        if file.type == FileType.ZX_BASIC:
            length = zx_length
            file.start = zx_start
            file.basic_length = zx_basic_length
            file.execute = zx_autorun
        elif file.type == FileType.ZX_DATA:
            length = zx_length
            file.start = zx_start
            file.data_var = zx_datavar
        elif file.type == FileType.ZX_DATA_STR:
            length = zx_length
            file.start = zx_start
            file.data_var = zx_datavar + '$'
        elif file.type == FileType.ZX_CODE:
            length = zx_length
            file.start = zx_start
            file.execute = zx_execute
        elif file.type == FileType.ZX_SNP_48K:
            length = zx_length or (0x4000 * 3)  # only Uni-DOS sets this
            # TODO: Z80 regs
        #elif file.type == FileType.ZX_MDRV:
        #    pass
        elif file.type == FileType.ZX_SCREEN:
            file.start = zx_start
            length = zx_length
        elif file.type == FileType.SPECIAL:
            length = num_sectors * 512
            #file.header = data[211:256] # all custom?
        elif file.type == FileType.ZX_SNP_128K:
            length = zx_length or (1 + (0x4000 * 8))  # only Uni-DOS sets this
            # TODO: Z80 regs
        elif file.type == FileType.OPENTYPE:
            length = zx_length
        elif file.type == FileType.ZX_EXECUTE:
            length = zx_length or (512 - 2)  # only Uni-DOS sets this
            file.start = 0x1bd6
        elif file.type == FileType.UNIDOS_DIR:
            # Uni-DOS over-allocates, should be entries*256 rounded up to 512?
            length = num_sectors * 512
        elif file.type == FileType.UNIDOS_CREATE:
            length = num_sectors * 512
        elif file.type == FileType.BASIC:
            file.start = sam_start
            length = sam_length
            file.execute = sam_autorun
        elif file.type == FileType.DATA:
            file.start = sam_start
            length = sam_length
            file.data_var = sam_datavar
        elif file.type == FileType.DATA_STR:
            file.start = sam_start
            length = sam_length
            file.data_var = sam_datavar + '$'
        elif file.type == FileType.CODE:
            file.start = sam_start
            length = sam_length
            file.execute = sam_execute
        elif file.type == FileType.SCREEN:
            file.start = sam_start
            length = sam_length
            file.screen_mode = 1 + (data[221] & 0x3)
        elif file.type == FileType.DRIVER_APP:
            file.start = sam_start
            length = sam_length
        elif file.type == FileType.DRIVER_BOOT:
            file.start = sam_start
            length = sam_length

        if file.type == FileType.DIR:
            file.dir = data[250]
        elif File.is_sam_file_type(file.type) and data[254] not in (0x00, 0xff):
            file.dir = data[254]

        return file, length

    @property
    def length(self) -> int:
        """File length in bytes"""
        return len(self.data)

    @property
    def sectors(self) -> int:
        """Number of sectors used by file"""
        header_size = File.type_header_size(self.type)
        chunk_size = File.data_bytes_per_sector(self.type)
        return 0 if self.data is None else (header_size + len(self.data) + chunk_size - 1) // chunk_size

    @property
    def bootable(self) -> bool:
        """True if the file would be bootable in the first directory slot"""
        offset = 0x100 - File.type_header_size(self.type)
        if len(self.data) < offset+4:
            return False

        bootsig = bytes([x & 0x5f for x in self.data[offset:offset+4]])
        return bootsig == b'BOOT'

    def save(self, path: str) -> None:
        """Export directory entry and file content for later"""

        with open(path, 'wb') as f:
            f.write(self.to_dir())
            if self.data:
                f.write(self.data)

    def to_dir(self, start_track: int = 4, start_sector: int = 1, *, spt: int = 10,
               timefmt: TimeFormat = TimeFormat.BDOS) -> bytes:
        """Create directory entry from current file data"""

        if self.type == FileType.NONE:
            return self.entry

        sector_map = File.contig_sector_map(self.sectors, start_track, start_sector, spt)

        # Use original as a template until we support writing all fields.
        data = bytearray(self.entry or bytes(256))

        data[0] = int(self.type) | (0x80 if self.hidden else 0) | (0x40 if self.protected else 0)
        data[1:1+10] = f'{self.name:10}'.encode('ascii', errors='replace')
        data[11:11+2] = struct.pack('>H', self.sectors)  # big endian
        data[13] = start_track or 0
        data[14] = start_sector or 0
        data[15:15+195] = sector_map.tobytes()

        zx_start = File.word_to_le(self.start or 0)
        zx_length = File.word_to_le(self.length or 0)
        zx_execute = File.word_to_le(self.execute or 0)
        #zx_datavar = ord(self.data_var or 'a') - ord('a') + 1

        sam_start = File.addr_to_triple(self.start)
        sam_length = File.len_to_triple(self.length)
        sam_execute = File.exec_to_triple(self.execute)

        if self.type == FileType.ZX_BASIC:
            data[211:211+1] = b'\x00'
            data[218:218+2] = File.word_to_le(self.execute or 0xffff)
        #elif self.type == FileType.ZX_DATA:
        #    data[211:211+1] = b'\x01'
        #elif self.type == FileType.ZX_DATA_STR:
        #    data[211:211+1] = b'\x02'
        #    data[216] = zx_datavar
        elif self.type == FileType.ZX_CODE:
            data[211:211+1] = b'\x03'
            data[212:212+2] = zx_length
            data[214:214+2] = zx_start
            data[218:218+2] = zx_execute
        #elif self.type == FileType.ZX_SNP_48K:
        #    data[211:211+1] = b'\x03'
        #elif self.type == FileType.ZX_MDRV:
        #    pass
        #elif self.type == FileType.ZX_SCREEN:
        #    data[211:211+1] = b'\x03'
        #    if self.start is not None:
        #        data[212:212+2] = zx_length
        #        data[214:214+2] = zx_start
        #elif self.type == FileType.SPECIAL:
        #    pass
        #elif self.type == FileType.ZX_SNP_128K:
        #    data[211:211+1] = b'\x10'
        elif self.type == FileType.OPENTYPE:
            data[210] = 0 if self.length is None else self.length >> 16
            data[212:212+2] = zx_length
        #elif self.type == FileType.ZX_EXECUTE:
        #    pass
        elif self.type == FileType.BASIC:
            data[242:242+3] = File.line_to_triple(self.execute)
        #elif self.type == FileType.DATA:
        #    pass
        #elif self.type == FileType.DATA_STR:
        #    pass
        elif self.type == FileType.CODE:
            data[236:236+3] = sam_start
            data[239:239+3] = sam_length
            data[242:242+3] = sam_execute
        #elif self.type == FileType.SCREEN:
        #    pass
        #elif self.type == FileType.DIR:
        #    pass
        #elif self.type == FileType.DRIVER_APP:
        #    pass
        #elif self.type == FileType.DRIVER_BOOT:
        #    pass

        if File.is_sam_file_type(self.type):
            data[245:245+5] = File.pack_time(self.time, timefmt)

        return bytes(data)

    # Deprecated, use bootable propery instead, usually as Disk.bootable
    def is_bootable(self) -> bool:
        """Check whether the file would be bootable in the first directory slot"""
        return self.bootable

    @staticmethod
    def type_has_data_header(type: FileType) -> bool:
        """Return whether a given file type uses a 9-byte file header"""
        return type in (
            FileType.ZX_BASIC,
            FileType.ZX_DATA,
            FileType.ZX_DATA_STR,
            FileType.ZX_CODE,
            FileType.ZX_SCREEN,
            FileType.BASIC,
            FileType.DATA,
            FileType.DATA_STR,
            FileType.CODE,
            FileType.SCREEN,
            FileType.DRIVER_APP,
            FileType.DRIVER_BOOT)

    @staticmethod
    def type_header_size(type: FileType) -> int:
        """Return size of file header for a given file type"""
        return File.HEADER_SIZE if File.type_has_data_header(type) else 0

    @staticmethod
    def is_sam_file_type(type: FileType) -> bool:
        """Return whether the given type is a SAM file type"""
        return type >= FileType.BASIC

    @staticmethod
    def is_contig_data_type(type: FileType) -> bool:
        """Return whether file type uses contiguous data sectors instead of a chain"""
        # TODO: should these use the sector map instead?
        return type in (FileType.SPECIAL, FileType.UNIDOS_DIR)

    @staticmethod
    def data_bytes_per_sector(type: FileType) -> int:
        """Return how many bytes of each sector hold file data"""
        return 512 if File.is_contig_data_type(type) else 510

    @staticmethod
    def contig_sector_map(sectors: int, start_track: Optional[int], start_sector: Optional[int],
                          spt: int = 10) -> bitarray:
        """Generate sector map of contiguous sectors from a given position"""
        if not start_track or not start_sector:
            raise ValueError('missing start track and sector')
        elif start_sector > spt or start_sector < 1:
            raise ValueError('start sector out of range')
        elif sectors < 0:
            raise ValueError('sectors must be non-negative')
        sector_map = bitarray('0' * 1560, endian='little')
        offset = (start_track - 4 - (0 if start_track < 80 else (128 - 80))) * spt + (start_sector - 1)
        sector_map[offset:offset+sectors] = 1
        return sector_map

    @staticmethod
    def pack_time(time: Optional[datetime], format: TimeFormat = TimeFormat.BDOS) -> bytes:
        """Pack given date/time into 5 bytes"""
        if time is None:
            return b'\x00\x00\x00\x00\x00'
        elif format is TimeFormat.MASTERDOS:
            data = time.day, time.month, time.year % 100, time.hour, time.minute
        elif format is TimeFormat.BDOS:
            data = time.day, time.month, time.year - 1900, time.hour, time.minute
        elif format is TimeFormat.BDOS17:
            data = time.day, 0x80 | (time.month << 3), time.year - 1900, \
                    (time.hour << 3) | (time.minute & 7), ((time.minute & 0x38) << 2) | (time.second >> 1)
        return bytes(data)

    @staticmethod
    def unpack_time(data: bytes) -> Optional[datetime]:
        """Unpack 5-byte date/time into datetime"""

        if data[0] == 0xff:
            return None
        elif data[1] & 0x80:  # BDOS >= 1.7a format?
            year, month, day = data[2], (data[1] & 0x78) >> 3, data[0]
            hours, mins, secs = (
                (data[3] & 0xf8) >> 3,
                ((data[4] & 0xe0) >> 2) | (data[3] & 0x07),
                (data[4] & 0x1f) << 1)
        else:
            year, month, day = data[2], data[1], data[0]
            hours, mins, secs = data[3], data[4], 0

        year += 1900 + (100 if year < 80 else 0)
        try:
            return datetime(year, month, day, hours, mins, secs)
        except ValueError:
            return None

    @staticmethod
    def le_word(data: bytes) -> int:
        """Unpack unsigned 16-bit value from 2 bytes (little endian)"""
        return int(struct.unpack('<H', data)[0])

    @staticmethod
    def word_to_le(val: Optional[int]) -> bytes:
        """Pack unsigned 16-bit value to 2 bytes (little endian)"""
        return struct.pack('<H', 0 if val is None else (val & 0xffff))

    @staticmethod
    def unpack_triple(data: bytes) -> Tuple[int, int]:
        """Unpack 3-byte MGT value to 5-bit and 15-bit components"""
        return data[0] & 0x1f, (data[2] & 0x7f) * 256 + data[1]

    @staticmethod
    def triple_to_addr(data: bytes) -> int:
        """Convert 3-byte value to start address"""
        page, addr = File.unpack_triple(data)
        return page * 16384 + addr + 0x4000

    @staticmethod
    def triple_to_len(data: bytes) -> int:
        """Convert 3-byte page/offset to length"""
        pages, remain = File.unpack_triple(data)
        return pages * 16384 + remain

    @staticmethod
    def triple_to_exec(data: bytes) -> Optional[int]:
        """Convert 3-byte value to execute address"""
        page, offset = File.unpack_triple(data)
        return None if data[0] == 0xff else page * 16384 + offset

    @staticmethod
    def triple_to_line(data: bytes) -> Optional[int]:
        """Convert 3-byte value BASIC auto-start line number"""
        return None if data[0] == 0xff else (data[2] * 256 + data[1])

    @staticmethod
    def addr_to_triple(addr: Optional[int]) -> bytes:
        """Convert start address to 3-byte value"""
        if addr is None:
            return b'\x00\x00\x00'
        page, addr = ((addr >> 14) - 1) & 0x1f, (addr & 0x3fff) + 0x8000
        return struct.pack('<BH', page, addr)

    @staticmethod
    def len_to_triple(len: Optional[int]) -> bytes:
        """Convert length to 3-byte page/offset value"""
        if len is None:
            return b'\x00\x00\x00'
        pages, remain = (len >> 14) & 0x1f, len & 0x3fff
        return struct.pack('<BH', pages, remain)

    @staticmethod
    def exec_to_triple(exec: Optional[int]) -> bytes:
        """Convert execute address to 3-byte value"""
        if exec is None:
            return b'\xff\xff\xff'
        page, offset = (exec >> 14) & 0x1f, (exec & 0x3fff) + 0x8000
        return struct.pack('<BH', page, offset)

    @staticmethod
    def line_to_triple(line: Optional[int]) -> bytes:
        """Convert auto-start line number to 3-byte value"""
        if line and (line < 0 or line >= 0xff00):
            raise ValueError('line should be >=0 and < 65280')
        return b'\xff\xff\xff' if line is None else struct.pack('<BH', 0, line)
