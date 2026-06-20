# mgtdisklib

A Python library to access to the contents of SAM Coupé and MGT +D disk images.

NOTE: the libary API may not be completely stable before version 1.0.

Homepage: <https://github.com/simonowen/mgtdisklib>  
Module: <https://pypi.org/project/mgtdisklib/>

[![CI](https://github.com/simonowen/mgtdisklib/actions/workflows/main.yml/badge.svg)](https://github.com/simonowen/mgtdisklib/actions/workflows/main.yml)

----

## Using the library

### Installing the module

```shell
python -m pip install mgtdisklib
```

### Importing the module

```python
from mgtdisklib import Disk, Image, File
```

### Opening a disk image

```python
disk = Disk.open('image.mgt')
```

MGT/SAD/EDSK container files are supported, but only those containing a regular
80/2/10/512 or 80/2/9/512 format. The image file may be optionally compressed
with gzip.

### Saving the Disk contents to a new MGT image file

```python
disk.save('image2.mgt')
```

----

## Disk

Represents a logical SAM disk plus all its contents.

### Disk Types

`DiskType` is one of the following values:

```python
DiskType.SAMDOS         # SAMDOS (default).
DiskType.MASTERDOS      # MasterDOS.
DiskType.BDOS           # BDOS, used by Atom and Atom Lite.
```

### Disk Class Functions

```python
    def open(path: str) -> Disk:
        """Load disk from disk image file"""
    def from_image(image: Image) -> Disk:
        """Construct a Disk object from a disk image"""
```

### Disk Instance Functions

```python
    def save(self, path: str, *, compressed: bool = False) -> None:
        """Save disk content to disk image"""
    def to_image(self) -> Image:
        """Generate MGT disk image from current contents"""
    def add_code_file(self, path: str, *, filename: str | None = None, at_index: int | None = None) -> None:
        """Add CODE file from path"""
    def add_code_bytes(self, data: bytes, *, filename: str, at_index: int | None = None) -> None:
        """Add CODE file from bytes"""
    def delete(self, pattern: str) -> list[str]:
        """Delete files matching filename pattern, returns list of deleted names"""
    def dir(self) -> str:
        """Return directory listing"""
```

### Disk Instance Properties

- `type` - disk type (DiskType)
- `files` - array of `File` objects in directory order (File[])
- `dir_tracks` - number of directory tracks (usually 4) (int)
- `label` - disk volume label string (str | None)
- `serial` - MasterDOS unique disk number (int | None)
- `compressed` - _True_ if the source disk or image was gzipped (bool)
- `bootable` - _True_ if the disk is bootable (bool) [read-only]
- `sector_map` - combined Bitmap Address Map for all files (bitarray) [read-only]

----

## File

Represents a single file entry on a disk.

### File Types

`FileType` is one of the following values:

```python
FileType.NONE           # unused or deleted entry
FileType.ZX_BASIC       # ZX Spectrum BASIC
FileType.ZX_DATA        # ZX Spectrum numeric array
FileType.ZX_DATA_STR    # ZX Spectum string array
FileType.ZX_CODE        # ZX Spectrum code
FileType.ZX_SNP_48K     # ZX Spectrum 48K snapshot
FileType.ZX_MDRV        # ZX Spectrum microdrive file
FileType.ZX_SCREEN      # ZX Spectrum SCREEN$
FileType.SPECIAL        # Custom file entry
FileType.ZX_SNP_128K    # ZX Spectrum 128K snapshot
FileType.OPENTYPE       # ZX/SAM file stream
FileType.ZX_EXECUTE     # ZX interface executable
FileType.UNIDOS_DIR
FileType.UNIDOS_CREATE  
FileType.BASIC          # SAM Coupé BASIC
FileType.DATA           # SAM Coupé numeric array
FileType.DATA_STR       # SAM Coupé string array
FileType.CODE           # SAM Coupé code
FileType.SCREEN         # SAM Coupé SCREEN (mode 1-4)
FileType.DIR            # SAM Coupé MasterDOS directory
FileType.DRIVER_APP     # Driver application
FileType.DRIVER_BOOT    # Driver boot file
FileType.EDOS_NOMEN     # Entropy IDE DOS (abandoned)
FileType.EDOS_SYSTEM
FileType.EDOS_OVERLAY
FileType.HDOS_DOS       # SD IDE DOS
FileType.HDOS_DIR
FileType.HDOS_DISK
FileType.HDOS_TEMP
```

`TimeFormat` is one of the following values:

```python
TimeFormat.MASTERDOS    # Format used by MasterDOS.
TimeFormat.BDOS         # Format used by most BDOS and AL-BDOS versions.
TimeFormat.BDOS17       # Packed format for used by BDOS 1.7 or later.
```

### File Class Functions

```python
    def from_code_path(path: str, *, filename: str = None, start: int = 0x8000, execute: int = None) -> File:
        """Create CODE file from path"""
    def from_code_bytes(data: bytes, filename: str, *, start: int = 0x8000, execute: int = None) -> File:
        """Create CODE file from bytes"""
    def from_dir(data: bytes) -> File:
        """Create from 256-byte directory entry data"""
    def from_path(path: str) -> File:
        """Import file entry exported using save()"""
```

### File Instance Functions

```python
    def save(self, path: str) -> None:
        """Export directory entry and file content for later"""
    def to_dir(self, disk_map: bitarray | None = None, timefmt: TimeFormat = TimeFormat.MASTERDOS) -> tuple[bytes, bitarray]:
        """Create directory entry, allocate sectors, return (entry, updated disk_map)"""
```

### File Instance Properties

- `type` - file type (FileType)
- `hidden` - _True_ if file is hidden from SAM directory listing (bool)
- `protected` - _True_ if file is protected from deletion (bool)
- `name` - file name in ASCII without trailing spaces (str)
- `name_raw` - original 10-byte name, which could contain special characters (bytes)
- `sectors` - count of data sectors used (int) [read-only]
- `first_sector` - first data (track, sector) tuple (tuple[int, int] | None) [read-only]
- `sector_map` - bitmap of sectors used by this file, starting at track 4 sector 1 (bitarray) [read-only]
- `start` - file start address (int | None)
- `length` - file length in bytes (int) [read-only]
- `execute` - auto-execute line (BASIC) or address (CODE) (int | None)
- `time` - file date+time (datetime | None)
- `data_var` - variable name for numeric/string DATA types (str | None)
- `entry` - original 256-byte directory entry (bytes)
- `bootable` - _True_ if bootable in the first directory slot (bool) [read-only]
- `data` - file data (bytes)

Properties marked [read-only] are derived from the file data. `first_sector` and
`sector_map` are updated when a disk image is created containing the file.

----

## Image

Represents a disk image container in MGT/SAD/EDSK format.

### Image Class Functions

```python
    def open(path):
        """Create Image object from disk image file"""
```

Creating an `Image()` object will give a standard 80/2/10/512 MGT disk image.

### Image Instance Functions

```python
    def save(self, path: str, *, compressed: bool = False) -> None:
        """Save disk data to image file"""
    def read_sector(self, track: int, sector: int) -> bytes:
        """Read sector data for given sector location"""
    def write_sector(self, track: int, sector: int, data: bytes) -> None:
        """Write sector data to given sector location"""
    def sector_offset(self, track: int, sector: int) -> int:
        """Calculate sector data offset in image data"""
```

MGT tracks are numbered are 0-79 for the first side and 128-207 for the second.
Sectors are numbered 1-10, each being 512 bytes. Only regular 10-sector disk
images are supported.

The first 4 tracks of the first side contain the disk directory, and the
remainder of the disk holds data. The second side of the disk is only used once
the first side is full. Track 4 sector 1 holds the boot sector.

MasterDOS disks can be formatted to use up to 39 directory tracks, allowing up
to 778 files to be stored. This is 2 less than expected because the boot sector
remains in the same place for all disks.

### Image Instance Properties

- `path` - full path of the disk image (str | None)
- `compressed` - _True_ if the source image was gzipped (bool)
- `data` - raw disk data from image file (bytearray)

----
