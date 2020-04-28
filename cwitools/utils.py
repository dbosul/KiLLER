"""Generic tools for saving files, etc."""
from astropy.io import fits
import cwitools
import numpy as np
import os
import pkg_resources
import sys
import warnings
from cwitools import coordinates
from PyAstronomy import pyasl

clist_template = {
    "INPUT_DIRECTORY":"./",
    "SEARCH_DEPTH":3,
    "OUTPUT_DIRECTORY":"./",
    "ID_LIST":[]
}

def get_instrument(hdr):
    if 'INSTRUME' in hdr:
        return hdr['INSTRUME']
    else:
        raise ValueError("Instrument not recognized.")

def get_specres(hdr):

    inst = get_instrument(hdr)

    if inst == 'PCWI':
        if 'MEDREZ' in hdr['GRATID']: return 2500
        else: return 5000

    elif inst == 'KCWI':

        grating, slicer = hdr['BGRATNAM'], hdr['IFUNAM']

        if grating == 'BL':
            R0 = 900
        elif grating == 'BM':
            R0 = 2000
        elif 'BH' in grating:
            R0 = 4500
        else:
            raise ValueError("Grating not recognized (header:BGRATNAM)")

        if slicer == 'Small':
            mul = 4
        elif slicer == 'Medium':
            mul = 2
        elif slicer == 'Large':
            mul = 1
        else:
            raise ValueError("Slicer not recognized (header:IFUNAM)")

        return mul * R0

    else:
        raise ValueError("Instrument not recognized.")

def get_skylines(inst, use_vacuum=False):

    if inst == 'PCWI':
        sky_file = 'palomar_lines.txt'
    elif inst == 'KCWI':
        sky_file = 'keck_lines.txt'
    else:
        raise ValueError("Instrument not recognized.")

    data_path = pkg_resources.resource_stream(__name__, 'data/sky/%s'% sky_file)
    data = np.loadtxt(data_path)
    
    if use_vacuum:
        data = pyasl.airtovac2(data)

    return data

def get_skymask(hdr):
    """Get mask of sky lines for specific instrument/resolution."""
    wav_type=hdr['CTYPE3']
    if wav_type=='AWAV':
        use_vacuum=False
    elif wav_type=='WAVE':
        use_vacuum=True
    else:
        raise ValueError("Wave type not recognized.")
    
    wav_axis = coordinates.get_wav_axis(hdr)
    wav_mask = np.zeros_like(wav_axis, dtype=bool)
    inst = get_instrument(hdr)
    res = get_specres(hdr)
    skylines = get_skylines(inst, use_vacuum=use_vacuum)

    for line in skylines:
        dlam = 1.4 * line / res #Get width of line from inst res.
        wav_mask[np.abs(wav_axis - line) <= dlam] = 1
    return wav_mask

def get_skybins(hdr):
    """Get sky-line masks in 2D bins."""
    wav_type=hdr['CTYPE3']
    if wav_type=='AWAV':
        use_vacuum=False
    elif wav_type=='WAVE':
        use_vacuum=True
    else:
        raise ValueError("Wave type not recognized.")
    inst = get_instrument(hdr)
    res = get_specres(hdr)
    skylines = get_skylines(inst, use_vacuum=use_vacuum)
    bin_list = []
    for line in skylines:
        onebin = [line-1.4*line/res, line+1.4*line/res]
        bin_list.append(onebin)
    return bin_list

def get_bunit(bunit,multi='1'):
    """Convert BUNIT values to FITS standards."""
    
    # Angstrom
    if '/A' in bunit:
        bunit=bunit.replace('/A','/angstrom')
    if 'A' in multi:
        multi=multi.replace('A','angstrom')
    
    # unconventional expressions
    if 'FLAM' in bunit:
        order=float(bunit.replace('FLAM',''))
        v0=u.erg/u.s/u.cm**2/u.angstrom*10**(-order)
    elif 'SB' in bunit:
        order=float(bunit.replace('SB',''))
        v0=u.erg/u.s/u.cm**2/u.angstrom/u.arcsec**2*10**(-order)
    else:
        v0=u.Unit(bunit)
                
    vout=(v0*u.Unit(multi))
    # convert to quatity
    if type(vout)==type(u.Unit('erg/s')):
        vout=u.Quantity(1,vout)
    vout=vout.cgs
    stout="{0.value:.0e} {0.unit:FITS}".format(vout)
    
    # handle arcsec
    if 'rad' in stout:
        vout=(vout*u.arcsec**2).cgs/u.arcsec**2
        stout="{0.value:.0e} {0.unit:FITS}".format(vout)
    
    # clean up
    if ' Ba ' in stout:
        vout=vout/u.Ba*u.erg/u.cm**3
        stout="{0.value:.0e} {0.unit:FITS}".format(vout)

    if ' g ' in stout:
        vout=vout/u.g*u.erg*u.s**2/u.cm**2
        stout="{0.value:.0e} {0.unit:FITS}".format(vout)
        
    stout=stout.replace('1e+00 ','')
    stout=stout.replace('10**','1e')
    
    return stout

def extractHDU(fits_in):
    type_in = type(fits_in)
    if type_in == fits.HDUList:
        return fits_in[0]
    elif type_in == fits.ImageHDU or type_in == fits.PrimaryHDU:
        return fits_in
    else:
        raise ValueError("Astropy ImageHDU, PrimaryHDU or HDUList expected.")

def matchHDUType(fits_in, data, header):
    """Return a HDU or HDUList with data/header matching the type of the input."""
    type_in = type(fits_in)
    if type_in == fits.HDUList:
        return fits.HDUList([fits.PrimaryHDU(data, header)])
    elif type_in == fits.ImageHDU:
        return fits.ImageHDU(data, header)
    elif type_in == fits.PrimaryHDU:
        return fits.PrimaryHDU(data, header)
    else:
        raise ValueError("Astropy ImageHDU, PrimaryHDU or HDUList expected.")

def get_fits(data, header=None):
    hdu = fits.PrimaryHDU(data, header=header)
    hdulist = fits.HDUList([hdu])
    return hdulist

def set_cmdlog(path):
    cwitools.command_log = path


def find_files(id_list, datadir, cubetype, depth=3):
    """Finds the input files given a CWITools parameter file and cube type.

    Args:
        params (dict): CWITools parameters dictionary.
        cubetype (str): Type of cube (e.g. icubes.fits) to load.

    Returns:
        list(string): List of file paths of input cubes.

    Raises:
        NotADirectoryError: If the input directory does not exist.

    """

    #Check data directory exists
    if not os.path.isdir(datadir):
        raise NotADirectoryError("Data directory (%s) does not exist. Please correct and try again." % datadir)

    #Load target cubes
    N_files = len(id_list)
    target_files = []
    typeLen = len(cubetype)

    for root, dirs, files in os.walk(datadir):

        if root[-1] != '/': root += '/'
        rec = root.replace(datadir, '').count("/")

        if rec > depth: continue
        else:
            for f in files:
                if f[-typeLen:] == cubetype:
                    for i,ID in enumerate(id_list):
                        if ID in f:
                            target_files.append(root + f)

    #Print file paths or file not found errors
    if len(target_files) < len(id_list):
        warnings.warn("Some files were not found:")
        for id in id_list:
            is_in = np.array([ id in x for x in target_files])
            if not np.any(is_in):
                warnings.warn("Image with ID %s and type %s not found." % (id, cubetype))


    return sorted(target_files)

def parse_cubelist(filepath):
    """Load a CWITools parameter file into a dictionary structure.

    Args:
        path (str): Path to CWITools .list file

    Returns:
        dict: Python dictionary containing the relevant fields and information.

    """
    global clist_template
    clist = {k:v for k, v in clist_template.items()}

    #Parse file
    listfile = open(filepath, 'r')
    for line in listfile:

        line = line[:-1] #Trim new-line character
        #Skip empty lines
        if line == "":
            continue

        #Add IDs when indicated by >
        elif line[0] == '>':
            clist["ID_LIST"].append(line.replace('>', ''))

        elif '=' in line:

            line = line.replace(' ', '')     #Remove white spaces
            line = line.replace('\n', '')    #Remove line ending
            line = line.split('#')[0]        #Remove any comments
            key, val = line.split('=') #Split into key, value pair
            if key.upper() in clist:
                clist[key] = val
            else:
                raise ValuError("Unrecognized cube list field: %s" % key)
    listfile.close()

    #Perform quick validation of input, but only warn for issues
    input_isdir = os.path.isdir(clist["INPUT_DIRECTORY"])
    if not input_isdir:
        warnings.warn("%s is not a directory." % clist["INPUT_DIRECTORY"])

    output_isdir = os.path.isdir(clist["OUTPUT_DIRECTORY"])
    if not output_isdir:
        warnings.warn("%s is not a directory." % clist["OUTPUT_DIRECTORY"])

    try:
        clist["SEARCH_DEPTH"] = int(clist["SEARCH_DEPTH"])
    except:
        raise ValuError("Could not parse SEARCH_DEPTH to int (%s)" % clist["SEARCH_DEPTH"])
    #Return the dictionary
    return clist

def output(str, log=None, silent=None):

    uselog = True

    #First priority, take given log
    if log != None:
        logfilename = log

    #Second priority, take global log file
    elif cwitools.log_file != None:
        logfilename = cwitools.log_file

    #If neither log set, ignore
    else:
        uselog = False

    #If silent is actively set to False by function call
    if silent == False:
        print(str, end='')

    #If silent is not set, but global 'silent_mode' is False
    elif silent == None and cwitools.silent_mode == False:
        print(str, end='')

    else: pass

    if uselog:
        logfile = open(logfilename, 'a')
        logfile.write(str)
        logfile.close()


def diagnosticPcolor(data):
    import matplotlib
    import matplotlib.pyplot as plt
    fig, ax  = plt.subplots(1, 1)
    ax.pcolor(data)
    #ax.contour(data)
    fig.show()
    plt.waitforbuttonpress()
    plt.close()
