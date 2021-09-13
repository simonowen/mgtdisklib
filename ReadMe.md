# mgtdisklib

A Python library to give file-level access to the contents of SAM Coupé and MGT +D disk images.

NOTE: the library is currently a work in progress and the API is still subject to change.

Homepage: https://github.com/simonowen/mgtdisklib  
Module: https://pypi.org/project/mgtdisklib/

[![CI](https://github.com/simonowen/mgtdisklib/actions/workflows/main.yml/badge.svg)](https://github.com/simonowen/mgtdisklib/actions/workflows/main.yml)

----

## Using the library

### Installing the module

```
pip -m install mgtdisklib
```

### Importing the module

```python
from mgtdisklib import Disk, Image, File
```

### Opening a disk image:

```python
disk = Disk.open('image.mgt')
```

MGT/SAD/EDSK container files are supported, but only those containing a regular 80/2/10/512 or 80/2/9/512 format. The image file may be optionally compressed with gzip.

### Saving the Disk contents to a new MGT image file

```python
disk.save('image2.mgt')
```

----

## Disk

Represents a logical SAM disk plus all its contents.

### Class Functions

```python
    def open(path: str) -> Disk:
        """Load disk from disk image file"""
    def from_image(image: Image) -> Disk:
        """Construct a Disk object from a disk image"""
```

### Instance Functions

```python
    def save(self, path: str, *, compressed: bool = False, spt: int = 10) -> None:
        """Save disk content to disk image"""
    def to_image(self, *, spt: int = 10) -> Image:
        """Generate MGT disk image from current contents"""
    def add_code_file(self, path: str, *, filename: str = None, at_index: int = None) -> None:
        """Add CODE file from path"""
    def delete(self, pattern: str) -> int:
        """Delete files matching filename pattern"""
    def bam(self) -> bitarray:
        """Combined Bitmap Address Map for all files"""
    def dir(self, *, spt: int = 10) -> str:
        """Return directory listing"""
```

### Instance Variables

 - `type` - detected type: `DiskType.SAMDOS` (default), `DiskType.MASTERDOS` or `DiskType.BDOS`.
 - `files` - list of `File` objects in directory order.
 - `dir_tracks` - number of directory tracks (usually 4).
 - `label` - disk volume label string, or None.
 - `serial` - MasterDOS unique disk number, or None.
 - `compressed` - _True_ if the source disk was gzipped.

----

## File

### Types

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

### Class Functions
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

### Instance Functions
```python
    def save(self, path: str) -> None:
        """Export directory entry and file content for later"""
    def to_dir(self, start_track: int = 4, start_sector: int = 1, *, spt: int = 10, timefmt: TimeFormat = TimeFormat.BDOS) -> bytes:
        """Create directory entry from current file data"""
    def is_bootable(self) -> bool:
        """Check whether the file would be bootable in the first directory slot"""
```
### Instance Variables

- `type` - FileType (see above) [read-only]
- `hidden` - True if file is hidden from SAM directory listing
- `protected` - True is file is protected from deletion
- `name` - file name in ASCII without trailing spaces
- `name_raw` - original 10-byte name, which could contain special characters
- `sectors` - count of data sectors used (from sector bitmap) [read-only]
- `start_track` - first track of file data [read-only]
- `start_sector` - first sector of file data [read-only]
- `sector_map` - bitarray of sectors used by this file (starting track 4 sector 1) [read-only]
- `start` - file start address
- `length` - file length
- `execute` - auto-execute line/address, or None
- `time` - file time or None
- `data_var` - variable name for numeric/string DATA types [read-only]
- `entry` - original 256-byte directory entry
- `data` - raw file data, including 9-byte header and final sector padding

Some properties are read-only, reflecting the state as read from disk. Some of
them (including `start_track`, `start_sector` and `sector_map`) will be updated
as needed when a disk image is created containing them.

----

## Image

Represents a disk image container in MGT/SAD/EDSK format.

### Class Functions

```python
    def open(path):
        """Create Image object from disk image file"""
```

Creating an `Image()` object will give a standard 80/2/10/512 MGT disk image.

### Instance Functions

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
Sectors are numbered 1-10 for normal format disks, each being 512 bytes.

The first 4 tracks of the first side contain the disk directory, and the
remainder of the disk holds data. The second side of the disk is only used once
the first side is full. Track 4 sector 1 holds the boot sector.

### Instance Variables

- `path` - full path of the disk image.
- `spt` - sectors per track, usually 10.
- `compressed` - _True_ if the source image was gzipped.
- `data` - raw disk data from image file.

----
