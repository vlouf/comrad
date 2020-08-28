"""
📡 OZ Radar site information 📡

@creator: Valentin Louf <valentin.louf@bom.gov.au>
@project: s3car-server
@institution: Bureau of Meteorology
@date: 28/08/2020

.. autosummary::
    :toctree: generated/

    get_frequency_band
    check_update
    main
"""
import io
import os
import re
import filecmp

import requests
import pandas as pd


def get_frequency_band(wavelength: float) -> str:
    """
    Frequency bands in the microwave range are designated by letters. This
    standard is the IEEE radar bands.

    Parameter:
    ==========
    wavelength: float
        Wavelength in cm.

    Returns:
    ========
    band: str
        Radar frequency band designation.
    """
    # name, freq min, freq max
    ieee_freq_band_ghz = [
        ("L", 1, 2),
        ("S", 2, 4),
        ("C", 4, 8),
        ("X", 8, 12),
        ("Ku", 12, 18),
        ("K", 18, 27),
        ("Ka", 27, 40),
        ("V", 40, 75),
        ("W", 75, 110),
    ]

    ghz = 1e-9 * 300_000_000 / (wavelength * 1e-2)
    for band, fmin, fmax in ieee_freq_band_ghz:
        if ghz >= fmin and ghz <= fmax:
            return band

    # Freq band not found.
    raise ValueError("Invalid radar wavelength. Is the wavelength in cm?")


def check_update() -> bool:
    """
    Check if siteinfo.txt has been updated. Remove the old version and write
    the new one in case of update.

    Returns:
    ========
    updated: bool
        True if file has been updated.
    """
    r = requests.get(URL_SITE_INFO)
    content = r.content.decode("ascii")
    if len(content) == 0:
        raise ValueError(f"Problem with content of {URL_SITE_INFO}.")

    # Code never run and file doesn't exist in the first place.
    if not os.path.isfile(SITE_INFO_FILE):
        with open(SITE_INFO_FILE, "w+") as fid:
            fid.write(content)
        return True

    tempfile = os.path.join(CONFIG_DIR, "tmp_test.txt")
    with open(tempfile, "w+") as fid:
        fid.write(content)

    updated = False
    if not filecmp.cmp(SITE_INFO_FILE, tempfile):
        updated = True
        print("siteinfo.txt has been updated.")
        print("Removing old siteinfo.txt")
        os.remove(SITE_INFO_FILE)
        print("Writing new siteinfo.txt")
        os.rename(tempfile, SITE_INFO_FILE)

    try:
        os.remove(tempfile)
    except FileNotFoundError:
        pass

    return updated


def main():
    # Check if output already exists and if it needs to be updated.
    if not check_update() and os.path.isfile(OUTPUT_FILE):
        print(f"Configuration file {OUTPUT_FILE} doesn't have to be updated.")
        return None

    # If it comes to here, it needs to be updated.
    with open(SITE_INFO_FILE, "r") as fid:
        content = fid.read()

    # Reading the RADAR SITE DATA
    radar_site = ["id short_name site_lat site_lon site_alt type typetext SitesDB_ID".replace(" ", ",")]
    read = False
    for c in content.splitlines():
        if len(c) <= 1:
            continue
        if c.startswith("#"):
            continue
        if c.lstrip().startswith("0 "):
            continue
        if c.startswith("RADAR SITE DATA"):
            read = True
            continue
        if c.startswith("END RADAR SITE DATA"):
            read = False
            break
        line = c.lstrip()
        line = re.sub(" +", ",", line)
        line = re.sub("_+", "", line)
        if read:
            radar_site.append(line)

    radar_site = "\n".join(radar_site)

    # Reading the RADAR TYPE DATA
    radar_type = ["type typetext wavelength beamwidth Vbeamwidth".replace(" ", ",")]
    read = False
    for c in content.splitlines():
        if len(c) <= 1:
            continue
        if c.startswith("#"):
            continue
        if c.lstrip().startswith("0 "):
            continue
        if c.startswith("RADAR TYPE DATA"):
            read = True
            continue
        if c.startswith("END RADAR TYPE DATA"):
            read = False
            break
        line = c.lstrip()
        line = re.sub(" +", ",", line)
        if read:
            radar_type.append(line.replace("_", ""))

    radar_type = "\n".join(radar_type)

    # Build a nice and understandable CSV table:
    dfsite = pd.read_csv(io.StringIO(radar_site))
    dftype = pd.read_csv(io.StringIO(radar_type), index_col="type")

    # Merge the 2 table
    df = dfsite.merge(dftype, how="left", on="typetext")
    # Latitude is oriented toward the south (positive south), changing to North
    df.site_lat = -df.site_lat
    # Scale-factor for wavelength and beamwidths
    df[["wavelength", "beamwidth", "Vbeamwidth"]] /= 10
    # Get the frequency band
    df["band"] = df.wavelength.apply(get_frequency_band)
    df = df.set_index("id", drop=True)
    df.to_csv(OUTPUT_FILE, float_format="%g")
    print(f"{OUTPUT_FILE} written.")
    print("New radar type configuration table updated.")

    return None


if __name__ == "__main__":
    CONFIG_DIR = "/srv/data/s3car-server/config"
    SITE_INFO_FILE = os.path.join(CONFIG_DIR, "siteinfo.txt")
    URL_SITE_INFO = ""
    OUTPUT_FILE = os.path.join(CONFIG_DIR, "radar_site_list.csv")
    main()
