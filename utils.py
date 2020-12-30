"""
Tools
"""

import pathlib
import lxml.etree as ET
import datetime as dt
import resource
from osgeo import gdal
import zipfile


def xml_read(xml_file):
    """ Validate xml syntax from filepath.

    Args:
        xml_file ([pathlib object]): [filepath to an xml file]
                 or zipfile object
    Returns:
        [bool]: [return True if a valid xml filepath is provided, 
        raises an exception if the xmlfile is invalid, empty, or doesn't exist ]
    """
    #todo change input variable name
    if isinstance(xml_file, pathlib.Path):
        if not pathlib.Path(xml_file).is_file():
            print(f'Error: Can\'t find xmlfile {xml_file}')
            return None
        tree = ET.parse(str(xml_file))
        root = tree.getroot()
    elif isinstance(xml_file, bytes):
        root = ET.fromstring(xml_file)

    return root


def memory_use(start_time):
    """
    Print memory usage and time taken by a process
    Args:
        start_time: datetime object containing start time of process
    Returns:
        N/A
    """
    print('\nAdding subswath layers')
    print(f"Memory usage so far: "
          f"{float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1000000} Gb")
    print(dt.datetime.now() - start_time)


def seconds_from_ref(t, t_ref):
    """
    Computes the difference in seconds between input date and a reference date (01/01/1981)
    Args:
        t: date as a string
        t_ref: reference time as a datetime
    Returns:
        integer
    """
    try:
        mytime = dt.datetime.strptime(t, '%Y-%m-%dT%H:%M:%S.%f')
    except ValueError:
        mytime = dt.datetime.strptime(t, '%Y-%m-%dT%H:%M:%S.%fZ')
    return int((mytime - t_ref).total_seconds())


def create_time(ncfile, t, ref='01/01/1981'):
    """
    Create time variable for netCDF file.
    Args:
        ncfile: netcdf file (already open)
        t: time as string
        ref: reference time as string (dd/mm/yyyy)
    Returns:
    """

    ref_dt = dt.datetime.strptime(ref, '%d/%m/%Y')
    nc_time = ncfile.createVariable('time', 'i4', ('time',))
    nc_time.long_name = 'reference time of satellite image'
    nc_time.units = f"seconds since {ref_dt.strftime('%Y-%m-%d %H:%M:%S')}"
    nc_time.calendar = 'gregorian'
    nc_time[:] = seconds_from_ref(t, ref_dt)

    return True


def initializer(self):
    """
       Traverse manifest file for setting additional variables
            in __init__
        Args:
            xmlFile:

        Returns:
    """

    self.zip = zipfile.ZipFile(self.input_zip)

    # Try and find main xml
    #todo: add s2 dterreng case
    allfiles = self.zip.namelist()
    if self.product_id + '.SAFE/manifest.safe' in allfiles:
        self.mainXML = self.product_id + '.SAFE/manifest.safe'

    root = xml_read(self.zip.read(self.mainXML))
    #root = xml_read(self.mainXML)
    sat = self.product_id.split('_')[0][0:2]

    # Set xml-files
    dataObjectSection = root.find('./dataObjectSection')
    for dataObject in dataObjectSection.findall('./'):
        if sat == 'S1':
            repID = dataObject.attrib['repID']
        elif sat == 'S2':
            repID = dataObject.attrib['ID']
        ftype = None
        href = None
        for element in dataObject.iter():
            attrib = element.attrib
            if 'mimeType' in attrib:
                ftype = attrib['mimeType']
            if 'href' in attrib:
                href = attrib['href'][1:]
        if sat == 'S2':
            if (ftype == 'text/xml' or ftype == 'application/xml') and href:
                self.xmlFiles[repID] = self.product_id + '.SAFE' + href
            elif ftype == 'application/octet-stream':
                self.imageFiles[repID] = self.product_id + '.SAFE' + href
        elif sat == 'S1':
            if ftype == 'text/xml' and href:
                self.xmlFiles[repID].append(self.product_id + '.SAFE' + href)

    # Set processing level
    if sat == 'S2':
        self.processing_level = 'Level-' + self.product_id.split('_')[1][4:6]
        gdalFile = str(self.xmlFiles['S2_{}_Product_Metadata'.format(self.processing_level)])
    elif sat == 'S1':
        gdalFile = str(self.mainXML)

    # Set gdal object
    #self.src = gdal.Open(gdalFile)
    self.src = gdal.Open('/vsizip/' + str(self.input_zip) + '/' + gdalFile)
    print((self.src))

    # Set global metadata attributes from gdal
    self.globalAttribs = self.src.GetMetadata()

    if sat == 'S1':
        # Set raster size parameters
        self.xSize = self.src.RasterXSize
        self.ySize = self.src.RasterYSize
        # Set polarisation parameters
        polarisations = root.findall('.//s1sarl1:transmitterReceiverPolarisation',
                                     namespaces=root.nsmap)
        for polarisation in polarisations:
            self.polarisation.append(polarisation.text)
        self.globalAttribs['polarisation'] = self.polarisation
        # Timeliness
        self.globalAttribs['ProductTimelinessCategory'] = root.find(
            './/s1sarl1:productTimelinessCategory', namespaces=root.nsmap).text

    return True

# Add function to clean work files?
