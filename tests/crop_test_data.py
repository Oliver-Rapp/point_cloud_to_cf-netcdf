"""
Crop large test point cloud files to 100,000 points for fast round-trip testing.

Usage:
    python tests/crop_test_data.py

Outputs:
    /home/oliver/Documents/MET/Test_Point_Clouds/DJI_sample_100k.las
    /home/oliver/Documents/MET/Test_Point_Clouds/VNIR_sample_100k.ply
"""

import laspy
import numpy as np

DATA_DIR = "/home/oliver/Documents/MET/Test_Point_Clouds"
N = 100_000


def crop_las():
    src = f"{DATA_DIR}/DJI_202403241542_048_Zenmuse-L1_PPP.las"
    dst = f"{DATA_DIR}/DJI_sample_100k.las"

    print(f"Cropping LAS: {src}")
    with laspy.open(src) as f:
        chunk = next(f.chunk_iterator(N))
        header = laspy.LasHeader(
            point_format=f.header.point_format,
            version=f.header.version
        )
        header.offsets = f.header.offsets
        header.scales = f.header.scales
        for vlr in f.header.vlrs:   # preserve CRS VLRs
            header.vlrs.append(vlr)
        # Force Adjusted GPS Time flag (bit 0 = 1).
        # The source file's global_encoding bit is 0 (GPS Week Time), but the
        # actual GPS values (~395M seconds) are clearly Adjusted GPS Time.
        # This is a metadata inconsistency in the source file; correct it here.
        header.global_encoding.gps_time_type = laspy.header.GpsTimeType.STANDARD

        with laspy.open(dst, mode='w', header=header) as w:
            w.write_points(chunk)

    with laspy.open(dst) as f:
        count = f.header.point_count
    print(f"  Written {count} points to {dst}")


def crop_ply():
    """
    Crop a PLY file to N points by:
    1. Parsing the original header line by line (preserving comments that plyfile ignores)
    2. Writing a new header with updated point count
    3. Copying exactly N * bytes_per_point bytes of the original binary data

    This preserves the utm_crs comment even when it appears after property lines
    (non-standard but accepted by the project's get_ply_comment() reader).
    """
    src = f"{DATA_DIR}/2024-08-19-16-06-04-GMT_01_VNIR_1800_SN00845_FOVx2_geo.ply"
    dst = f"{DATA_DIR}/VNIR_sample_100k.ply"

    print(f"Cropping PLY: {src}")

    # PLY property type → byte size
    PLY_SIZES = {
        'char': 1, 'uchar': 1, 'int8': 1, 'uint8': 1,
        'short': 2, 'ushort': 2, 'int16': 2, 'uint16': 2,
        'int': 4, 'uint': 4, 'int32': 4, 'uint32': 4, 'float': 4, 'float32': 4,
        'double': 8, 'float64': 8, 'int64': 8, 'uint64': 8,
    }

    header_lines = []
    data_offset = 0
    bytes_per_point = 0

    with open(src, 'rb') as f:
        for raw_line in f:
            line = raw_line.decode('utf-8').rstrip('\n').rstrip('\r')
            header_lines.append(line)
            if line.startswith('property '):
                parts = line.split()
                bytes_per_point += PLY_SIZES.get(parts[1], 0)
            data_offset += len(raw_line)
            if line == 'end_header':
                break

    # Rebuild header with updated point count
    new_header = []
    for line in header_lines:
        if line.startswith('element vertex '):
            new_header.append(f'element vertex {N}')
        else:
            new_header.append(line)

    # Write new file
    with open(src, 'rb') as src_f, open(dst, 'wb') as dst_f:
        # Write new header
        for line in new_header:
            dst_f.write((line + '\n').encode('utf-8'))
        # Seek to start of binary data and copy N points
        src_f.seek(data_offset)
        dst_f.write(src_f.read(N * bytes_per_point))

    print(f"  Written {N} points to {dst}")
    print(f"  bytes_per_point={bytes_per_point}")
    # Verify comment preserved
    with open(dst, 'rb') as f:
        for line in f:
            l = line.decode('utf-8', errors='replace').strip()
            if l.startswith('comment'):
                print(f"  Comment: {l[:80]}...")
            if l == 'end_header':
                break


if __name__ == "__main__":
    crop_las()
    crop_ply()
    print("\nDone.")
