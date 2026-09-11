"""HYPSRV (asm:2344) -- the hyperwarp tunnel, and the zoom cache GRAPH needs.

Called every frame.  Two jobs:

  1. Cache ZOOMTB entries for the ship and both photons, so SHPSRV and the
     display kernel can scale them without repeating the lookup.
  2. While the hyperwarp screen is up, pull the two photons -- repurposed as
     tunnel stars -- down the tunnel: subtract a zoom-derived amount from their
     YDEL and decrement their ZDEL, which is what makes them streak past.

It RETURNS while the tunnel is up, and falls through into GRAPH otherwise -- so
during a hyperwarp no object animation runs at all.
"""

from . import byte as b
from . import romdata as rom
from .state import (HCOLP1, HOLDM0, PROGST, PROGST_HYPER, VECTP1, YDELP0,
                    ZDELP0, ZPOSP1)

ZOOMTB = rom.tab("ZOOMTB")


def hypsrv(mach):
    """HYPSRV.  Returns True when GRAPH should run afterwards."""
    m = mach.m
    m[HOLDM0] = ZOOMTB[m[HCOLP1 + 1]]        # the ship's lift, for SHPSRV
    m[VECTP1] = ZOOMTB[m[ZPOSP1]]            # the near photon's zoom
    m[VECTP1 + 1] = ZOOMTB[m[ZPOSP1 + 1]]    # ... and the far one's

    if not (m[PROGST] & PROGST_HYPER):
        return True

    for x in (1, 0):
        y = m[ZDELP0 + x]
        fall = (ZOOMTB[y] >> 4) & 0x07
        a, _ = b.adc(b.neg(fall), m[YDELP0 + x], c=True)
        if a & 0x80:
            a = 0x00                         # clamp rather than wrap
        m[YDELP0 + x] = a
        y = (y - 1) & 0xFF
        if y != 0:
            m[ZDELP0 + x] = y
    return False
