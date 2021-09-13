# File wrapper for MGT directory entries plus data.
#
# Part of https://github.com/simonowen/mgtdisklib

import os, struct
from enum import Enum, IntEnum
from datetime import datetime
from typing import Tuple, Optional
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

TYPE_NAMES = { 1:'ZX BASIC', 2:'ZX DATA ()', 3:'ZX DATA $()', 4:'ZX CODE',
    5:'ZX SNP 48K', 6:'ZX MDRV', 7:'ZX SCREEN$', 8:'SPECIAL', 9:'ZX SNP 128K',
    10:'OPENTYPE', 11:'ZX EXECUTE', 12:'UNIDOS DIR', 13:'UNIDOS CREATE', 16:'BASIC',
    17:'DATA ()', 18:'DATA $', 19:'CODE', 20:'SCREEN$', 21:'<DIR>', 22:'DRIVER APP',
    23:'DRIVER BOOT', 24:'EDOS NOMEN', 25:'EDOS SYSTEM', 26:'EDOS OVERLAY',
    28:'HDOS DOS', 29:'HDOS DIR', 30:'HDOS DISK', 31:'HDOS TEMP' }

class TimeFormat(Enum):
    MASTERDOS = 0
    BDOS = 1
    BDOS17 = 2

class File:
    def __init__(self):
        self.type: FileType = FileType.NONE
        self.data = bytearray()
        self.entry: bytes = bytes(256)
        self.hidden: bool = False
        self.protected: bool = False
        self.name_raw: bytes = bytes()
        self.name: str = ''
        self.start_track: Optional[int] = None
        self.start_sector: Optional[int] = None
        self.sector_map: bitarray = bitarray(endian='little')
        self.sectors: int = 0
        self.start: Optional[int] = None
        self.length: Optional[int] = None
        self.execute: Optional[int] = None
        self.time: Optional[datetime] = None
        self.dir: Optional[int] = None
        self.data_var: Optional[str] = None
        self.screen_mode: Optional[int] = None

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
    def from_code_path(path: str, *, filename: str = None, start: int = 0x8000, execute: int = None):
        """Create CODE file from path"""

        with open(path, 'rb') as f:
            data = f.read()

        filename = filename or os.path.splitext(os.path.basename(path))[0][:10]
        return File.from_code_bytes(data, filename, start=start, execute=execute)

    @staticmethod
    def from_code_bytes(data: bytes, filename: str, *, start: int = 0x8000, execute: int = None):
        """Create CODE file from bytes"""

        file = File.from_dir(bytes(256))
        file.type = FileType.CODE
        file.name = filename
        file.name_raw = bytes(f'{filename:10}', 'ascii')
        file.length = len(data)
        file.start = start
        file.execute = execute

        chunk_size = File.data_bytes_per_sector(file.type)
        file.data = file.code_data_header() + data
        file.data += bytes(-len(file.data) % chunk_size)   # pad to chunk size
        file.sectors = len(file.data) // chunk_size
        return file

    @staticmethod
    def from_path(path: str):
        """Import file entry exported using save()"""

        with open(path, 'rb') as f:
            file = File.from_dir(f.read(256))
            if file.type != FileType.NONE:
                file.data = f.read()
            return file

    @staticmethod
    def from_dir(data: bytes):
        """Create from 256-byte directory entry data"""

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
        file.sectors = file.sector_map.count(1) # trust bitmap over stored sector count [see MNEMOdemo1]
        file.time = File.unpack_time(data[245:245+5]) if File.is_sam_file_type(file.type) else None

        file.start = None
        file.length = None
        file.execute = None
        file.data_var = None
        file.screen_mode = None

        zx_start = File.le_word(data[214:214+2])
        zx_length = File.le_word(data[212:212+2])
        zx_execute = File.le_word(data[218:218+2])
        zx_datavar = chr(ord('a') + (data[216] & 0x3f) - 1)

        sam_start = File.triple_to_addr(data[236:236+3])
        sam_length = File.triple_to_len(data[239:239+3])
        sam_execute = File.triple_to_exec(data[242:242+3])
        sam_datavar = data[222:222+(data[221] & 0xf)].decode('ascii', errors='replace')

        if file.type == FileType.ZX_BASIC:
            file.start = zx_start
            file.length = zx_length
            file.execute = None if data[219] == 0xff else zx_execute
        elif file.type == FileType.ZX_DATA:
            file.start = zx_start
            file.length = zx_length
            file.data_var = zx_datavar
        elif file.type == FileType.ZX_DATA_STR:
            file.start = zx_start
            file.length = zx_length
            file.data_var = zx_datavar + '$'
        elif file.type == FileType.ZX_CODE:
            file.start = zx_start
            file.length = zx_length
            file.execute = None if data[219] == 0x00 else zx_execute
        elif file.type == FileType.ZX_SNP_48K:
            file.length = 0xc000
        elif file.type == FileType.ZX_SCREEN:
            file.start = zx_start
            file.length = zx_length
        elif file.type == FileType.SPECIAL:
            file.length = file.sectors * 512
        elif file.type == FileType.ZX_SNP_128K:
            file.length = 0x20001
        elif file.type == FileType.OPENTYPE:
            file.length = data[210] * 0x10000 + zx_length
        elif file.type == FileType.ZX_EXECUTE:
            file.length = 510
        elif file.type == FileType.BASIC:
            file.start = sam_start
            file.length = sam_length
            file.execute = File.triple_to_line(data[242:242+3])
        elif file.type == FileType.DATA:
            file.start = sam_start
            file.length = sam_length
            file.data_var = sam_datavar
        elif file.type == FileType.DATA_STR:
            file.start = sam_start
            file.length = sam_length
            file.data_var = sam_datavar + '$'
        elif file.type == FileType.CODE:
            file.start = sam_start
            file.length = sam_length
            file.execute = sam_execute
        elif file.type == FileType.SCREEN:
            file.start = sam_start
            file.length = sam_length
            file.screen_mode = 1 + (data[221] & 0x3)
        elif file.type == FileType.DRIVER_APP:
            file.start = sam_start
            file.length = sam_length
        elif file.type == FileType.DRIVER_BOOT:
            file.start = sam_start
            file.length = sam_length

        if file.type == FileType.DIR:
            file.dir = data[250]
        elif File.is_sam_file_type(file.type) and data[254] not in (0x00, 0xff):
            file.dir = data[254]
        else:
            file.dir = None

        return file

    def save(self, path: str) -> None:
        """Export directory entry and file content for later"""

        with open(path, 'wb') as f:
            f.write(self.to_dir())
            if self.type != FileType.NONE:
                f.write(self.data)

    def to_dir(self, start_track: int = 4, start_sector: int = 1, *, spt: int = 10, timefmt: TimeFormat = TimeFormat.BDOS) -> bytes:
        """Create directory entry from current file data"""

        data = bytearray(self.entry)
        if self.type == FileType.NONE:
            return data

        self.sectors = len(self.data) // File.data_bytes_per_sector(self.type)
        sector_map = File.contig_sector_map(self.sectors, start_track, start_sector, spt)

        data[0] = int(self.type) | (0x80 if self.hidden else 0) | (0x40 if self.protected else 0)
        data[1:1+10] = f'{self.name:10}'.encode('ascii', errors='replace')
        data[11:11+2] = struct.pack('>H', self.sectors) # big endian
        data[13] = start_track
        data[14] = start_sector
        data[15:15+195] = sector_map.tobytes()

        # Limited support for updating length/start/execute.
        if self.type == FileType.ZX_BASIC:
            data[218:218+2] = b'\xff\xff' if self.execute is None else File.word_to_le(self.execute)
        elif self.type == FileType.ZX_CODE:
            data[212:212+2] = File.word_to_le(self.length)
            data[214:214+2] = File.word_to_le(self.start)
            data[218:218+2] = File.word_to_le(self.execute)
        elif self.type == FileType.OPENTYPE:
            data[210] = 0 if self.length is None else self.length >> 16
            data[212:212+2] = File.word_to_le(self.length)
        elif self.type == FileType.BASIC:
            data[242:242+3] = File.line_to_triple(self.execute)
        elif self.type == FileType.CODE:
            data[236:236+3] = File.addr_to_triple(self.start)
            data[239:239+3] = File.len_to_triple(self.length)
            data[242:242+3] = File.exec_to_triple(self.execute)

        if File.is_sam_file_type(self.type):
            data[245:245+5] = File.pack_time(self.time, timefmt)

        return bytes(data)

    def is_bootable(self) -> bool:
        """Check whether the file would be bootable in the first directory slot"""

        if len(self.data) >= 0x104:
            return bytes([x & 0x5f for x in self.data[0x100:0x100+4]]) == bytes('BOOT', 'ascii')
        return False

    def code_data_header(self) -> bytes:
        """Generate 9-byte file data header for a CODE file"""

        header = bytearray(9)
        header[0] = self.type
        header[1:1+2] = File.len_to_triple(self.length)[1:]
        header[3:3+2] = File.addr_to_triple(self.start)[1:]
        header[5:5+2] = b'\xff\xff'
        header[7] = File.len_to_triple(self.length)[0]
        header[8] = File.addr_to_triple(self.start)[0]
        return bytes(header)

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
    def contig_sector_map(sectors: int, start_track: int, start_sector: int, spt: int = 10) -> bitarray:
        """Generate sector map of contiguous sectors from a given position"""
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
            data = time.day, 0x80 | (time.month << 3), time.year - 1900, (time.hour << 3) | (time.minute & 7), ((time.minute & 0x38) << 2) | (time.second >> 1)
        return bytes(data)

    @staticmethod
    def unpack_time(data: bytes) -> Optional[datetime]:
        """Unpack 5-byte date/time into datetime"""

        if data[0] == 0xff:
            return None
        elif data[1] & 0x80:  # BDOS >= 1.7a format?
            year, month, day = data[2], (data[1] & 0x78) >> 3, data[0]
            hours, mins, secs = (data[3] & 0xf8) >> 3, ((data[4] & 0xe0) >> 2) | (data[3] & 0x07), (data[4] & 0x1f) << 1
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
