"""AprilTag family patterns as printable black/white module grids.

The 36h11 code table and payload layout come from the official AprilTag
``tag36h11.c`` (codes 0..23 pinned here). The official table places payload
bit 0 at the top-left cell, while OpenCV's ``generateImageMarker`` renders the
same code rotated by 180 degrees; the derived white-cell order below is
flipped accordingly so it matches ``cv2.aruco.DICT_APRILTAG_36h11`` bit for
bit. ``tests/test_apriltag_family.py`` verifies that alignment for all 24 IDs.

Pinned upstream: AprilRobotics/apriltag b7c0ebe9aa20f82ec7a828579004f9e706bfecd9,
tag36h11.c SHA256 38ff6e308067eb32ccf624e9cc5e7a75b45ad82b3cf9f80980cb86ebaa88512b.
"""

# Copyright (C) 2013-2016, The Regents of The University of Michigan.
# All rights reserved.
# This software was developed in the APRIL Robotics Lab under the
# direction of Edwin Olson, ebolson@umich.edu. This software may be
# available under alternative licensing terms; contact the address above.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the Regents of The University of Michigan.

from dataclasses import dataclass

from beartype import beartype

_TAG36H11_CODES: tuple[int, ...] = (
    0x0000000D7E00984B,
    0x0000000DDA664CA7,
    0x0000000DC4A1C821,
    0x0000000E17B470E9,
    0x0000000EF91D01B1,
    0x0000000F429CDD73,
    0x000000005DA29225,
    0x00000001106CBA43,
    0x0000000223BED79D,
    0x000000021F51213C,
    0x000000033EB19CA6,
    0x00000003F76EB0F8,
    0x0000000469A97414,
    0x000000045DCFE0B0,
    0x00000004A6465F72,
    0x000000051801DB96,
    0x00000005EB946B4E,
    0x000000068A7CC2EC,
    0x00000006F0BA2652,
    0x000000078765559D,
    0x000000087B83D129,
    0x000000086CC4A5C5,
    0x00000008B64DF90F,
    0x00000009C577B611,
)

_TAG36H11_BIT_X: tuple[int, ...] = (
    1, 2, 3, 4, 5, 2, 3, 4, 3, 6, 6, 6, 6, 6, 5, 5, 5, 4,
    6, 5, 4, 3, 2, 5, 4, 3, 4, 1, 1, 1, 1, 1, 2, 2, 2, 3,
)
_TAG36H11_BIT_Y: tuple[int, ...] = (
    1, 1, 1, 1, 1, 2, 2, 2, 3, 1, 2, 3, 4, 5, 2, 3, 4, 3,
    6, 6, 6, 6, 6, 5, 5, 5, 4, 6, 5, 4, 3, 2, 5, 4, 3, 4,
)


@beartype
@dataclass(frozen=True, slots=True)
class TagFamily:
    """A tag family rendered as an 8x8 module grid (True means black ink)."""

    name: str
    hamming: int
    module_side: int
    codes: tuple[int, ...]
    white_cells: tuple[tuple[int, int], ...]

    def tag_modules(self, tag_id: int) -> tuple[tuple[bool, ...], ...]:
        if not 0 <= tag_id < len(self.codes):
            raise ValueError(f"tag id must be in 0..{len(self.codes) - 1}: {tag_id}")
        code = self.codes[tag_id]
        bit_count = len(self.white_cells)
        grid = [[True] * self.module_side for _ in range(self.module_side)]
        for index, (row, column) in enumerate(self.white_cells):
            if (code >> (bit_count - 1 - index)) & 1:
                grid[row][column] = False
        return tuple(tuple(row) for row in grid)


TAG36H11 = TagFamily(
    name="tag36h11",
    hamming=11,
    module_side=8,
    codes=_TAG36H11_CODES,
    white_cells=tuple(
        (7 - bit_y, 7 - bit_x) for bit_x, bit_y in zip(_TAG36H11_BIT_X, _TAG36H11_BIT_Y)
    ),
)
