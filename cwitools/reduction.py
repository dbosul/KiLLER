"""Stack input cubes into a master frame using a CWITools parameter file.
"""

from .. import libs

from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales

from scipy.ndimage.filters import convolve
from shapely.geometry import box, Polygon

import argparse
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import sys
import time

from .. import libs

from astropy.io import fits

import argparse
import numpy as np
import sys
import matplotlib.pyplot as plt

from .. imports libs

from astropy.io import fits
import argparse
import sys

from .. imports libs

from astropy.io import fits as fits

import argparse
import numpy as np
import sys

def wav_crop(inpFits,wav0,wav1"):
    """Crop a data cube to a given wavelength range.

    Args:
        inpFits (astrop FITS object): Cube (FITS) to be cropped.
        wav0 (float): Lower wavelength limit, in Angstrom.
        wav1 (float): Upper wavelength limit, in Angstrom.

    """
    cube = inpFits[0].data.copy()
    header = inpFits[0].header.copy()

    #Get indices of upper and lower bound
    index0,index1 = libs.cubes.getband(wav0,wav1,header)

    #Crop cube
    cropped_cube = cube[index0:index1]

    #Make new FITS object with modified header
    header["CRPIX3"] -= index0
    croppedFits = fits.HDUList([fits.PrimaryHDU(cropped_cube)])
    croppedFits[0].header = header

    return croppedFits


def trim(fitsList, xcrop=None, ycrop=None, wcrop=None):
    """Trims axes of each input cube according to CWITools parameter file.

    Args:
        paramPath (str): Path to CWITools parameter file.
        cubeType (str): Type of cube to work with (e.g. icubes.fits)
        fileExt (str): New file extension for output cubes (Default: .c.fits)
        xcrop (int tuple): Indices of range to crop x-axis to. Default: None.
        ycrop (int tuple): Indices of range to crop y-axis to. Default: None.
        wcrop (int tuple): Wavelength range to crop cube to. Default: None.

    Returns:
        list: List of trimmed FITS (astropy) objects

    """
    trimmedFits_List = []

    #Trim each cube
    for fitsFile in fitsList:

        data = fitsFile[0].data.copy()
        header = fitsFile[0].header.copy()

        if xcrop==None: xcrop=[0,-1]
        if ycrop==None: ycrop=[0,-1]
        if wcrop==None: zcrop=[0,-1]
        else: zcrop=getband(wcrop[0],wcrop[1],header)

        #Crop cube
        cropData = f[0].data[zcrop[0]:zcrop[1],ycrop[0]:ycrop[1],xcrop[0]:xcrop[1]].copy()
        data = cropData

        #Change RA/DEC/WAV reference pixels
        header["CRPIX1"] -= xcrop[0]
        header["CRPIX2"] -= ycrop[0]
        header["CRPIX3"] -= zcrop[0]

        #Make FITS for trimmed data and add to list
        trimmed_HDU = fits.PrimaryHDU(data)
        trimmed_HDU.header = header
        trimmed_HDUList = fits.HDUList(trimmed_HDU)
        trimmedFits_list.append(trimmed_HDUList)

    return trimmedFits_List


def fixwcs(paramPath,icubeType,instrument,fixRADEC=True,fixWav=False,skyLine=None,RA=None, DEC=None):
    """Corrects the world-coordinate system of data cubes using interactive tools.

    Args:
        paramPath (str): Path to the CWITools parameter file.
        icubeType (str): Type of icube to work with (e.g. icubes.fits, icuber.fits)
        instrument (str): Which CWI we're working with here (PCWI/KCWI)
        fixRADEC (bool): Fix the spatial axes (Default: True)
        fixWav (bool): Fix the wavelength axis (Default: True)
        skyLine (float): Known wavelength of a fittable sky-line.
            This parameter is required for fixing the wavelength solution.
        RA (float): RA (dd.dd) of source to use (overrides param file)
        DEC (float): DEC (dd.dd) of source to use (overrides param file)

    """

    #Load params
    params = libs.params.loadparams(paramPath)

    #Find icubes files
    ifileList = libs.params.findfiles(params,icubeType)

    #Run through all images now and perform corrections
    for i,fileName in enumerate(ifileList):

        #Get current CD matrix
        crval1,crval2,crval3 = ( fits[i][0].header["CRVAL%i"%(k+1)] for k in range(3) )
        crpix1,crpix2,crpix3 = ( fits[i][0].header["CRPIX%i"%(k+1)] for k in range(3) )

        #Get RA/DEC values if fixWAV requested
        if fixRADEC:

            radecFITS = fits.open(fileName)
            crval1,crval2,crpix1,crpix2 = libs.cubes.fixRADEC(radecFITS,RA,DEC)
            radecFITS.close()

        #Get wavelength WCS values if fixWav requested
        if fixWav:

            skyFile   = fileName.replace('icube','scube')
            skyFITS   = fitsIO.open(skyFile)
            crval3,crpix3 = libs.cubes.fixWav(skyFITS,inst[i],skyLine=skyLine)
            skyFITS.close()

        #Create lists of crval/crpix values, whether updated or not
        crvals = [ crval1, crval2, crval3 ]
        crpixs = [ crpix1, crpix2, crpix3 ]


        #Make list of relevant cubes to be corrected - scube doesn't matter as much
        cubes = ['icube','scube','ocube','vcube']

        #Load fits, modify header and save for each cube type
        for c in cubes:

            #Get filepath for this cube
            filePath = fileName.replace('icube',c)

            #Try to load, but continue upon failure
            try: f = fitsIO.open(filePath)
            except:
                print("Could not open %s. Cube will not be corrected." % filePath)
                continue

            #Fix each of the header values
            for k in range(3):

                f[0].header["CRVAL%i"%(k+1)] = crvals[k]
                f[0].header["CRPIX%i"%(k+1)] = crpixs[k]

            #Save WCS corrected cube
            wcPath = filePath.replace('.fits','.wc.fits')
            f[0].writeto(wcPath,overwrite=True)
            print("Saved %s"%wcPath)

def coadd(fileList,PA=0,pxThresh=0.5,expThresh=0.1,varData=False):
    """Coadd a list of fits images into a master frame.

    Args:
        fileList: List of paths of cubes to be coadded.
        pxThresh (float): Minimum fractional pixel overlap.
            This is the overlap between an input pixel and a pixel in the
            output frame. If a given pixel from an input frame covers less
            than this fraction of an output pixel, its contribution will be
            rejected.
        expThresh (float): Minimum exposure time, as fraction of maximum.
            If an area in the coadd has a stacked exposure time less than
            this fraction of the maximum overlapping exposure time, it will be
            trimmed from the coadd. Default: 0.1.
        PA (float): The desired position-angle of the output data.
        plot (bool): For debugging purposes, show plots of pixel mapping.
        varData (bool): Set to TRUE when coadding variance.

    Returns:
        astropy FITS object tuple: the stacked FITS.

    """

    #DEBUG PLOTTING MODE
    plot=False

    #
    # STAGE 0: PREPARATION
    #

    # Open custom FITS-3D objects
    fitsList = [fits.open(f) for f in fileList]

    # Extract basic header info
    hdrList    = [ f[0].header for f in fitsList ]
    wcsList    = [ WCS(h) for h in hdrList ]
    pxScales   = np.array([ proj_plane_pixel_scales(wcs) for wcs in wcsList ])

    # Get 2D headers, WCS and on-sky footprints
    h2DList    = [ get2DHeader(h) for h in hdrList]
    w2DList    = [ WCS(h) for h in h2DList ]
    footPrints = np.array([ w.calc_footprint() for w in w2DList ])

    # Exposure times
    expTimes = []
    for i,h in enumerate(hdrList):
        if h.has_key("TELAPSE"): expTimes.append(h["TELAPSE"])
        else: expTimes.append(h["EXPTIME"])

    # Extract into useful data structures
    xScales,yScales,wScales = ( pxScales[:,i] for i in range(3) )
    pxAreas = [ (xScales[i]*yScales[i]) for i in range(len(xScales)) ]
    # Determine coadd scales
    coadd_xyScale = np.min(np.abs(pxScales[:,:2]))
    coadd_wScale  = np.min(np.abs(pxScales[:,2]))



    #
    # STAGE 1: WAVELENGTH ALIGNMENT
    #

    # Check that the scale (Ang/px) of each input image is the same
    if len(set(wScales))!=1:

        print("ERROR: Wavelength axes must be equal in scale for current version of code.")
        print("Continue stacking without wavelength alignment? (y/n) >")
        answer = input("")
        if not( answer=="y" or answer=="Y" or answer=="yes" ): sys.exit()
        else: print("Proceeding with stacking without any wavelength axis shifts.")

    else:

        # Get common wavelength scale
        cd33 = hdrList[0]["CD3_3"]

        # Get lower and upper wavelengths for each cube
        wav0s = [ h["CRVAL3"] - (h["CRPIX3"]-1)*cd33 for h in hdrList ]
        wav1s = [ wav0s[i] + h["NAXIS3"]*cd33 for i,h in enumerate(hdrList) ]

        # Get new wavelength axis
        wNew = np.arange(min(wav0s)-cd33, max(wav1s)+cd33,cd33)

        print("Aligning wavelength axes.",end='')

        # Adjust each cube to be on new wavelenght axis
        for i,f in enumerate(fitsList):

            print(('.'), end=' ')

            # Pad the end of the cube with zeros to reach same length as wNew
            f[0].data = np.pad( f[0].data, ( (0, len(wNew)-f[0].header["NAXIS3"]), (0,0) , (0,0) ) , mode='constant' )

            # Get the wavelength offset between this cube and wNew
            dw = (wav0s[i] - wNew[0])/cd33

            # Split the wavelength difference into an integer and sub-pixel shift
            intShift = int(dw)
            spxShift = dw - intShift

            # Perform integer shift with np.roll
            f[0].data = np.roll(f[0].data,intShift,axis=0)

            # Create convolution matrix for subpixel shift (in effect; linear interpolation)
            K = np.array([ spxShift, 1-spxShift ])

            # Shift data along axis by convolving with K
            if varData: K=np.power(K,2)

            f[0].data = np.apply_along_axis(lambda m: np.convolve(m, K, mode='same'), axis=0, arr=f[0].data)

            f[0].header["NAXIS3"] = len(wNew)
            f[0].header["CRVAL3"] = wNew[0]
            f[0].header["CRPIX3"] = 1

        print("")


    #
    # Stage 2 - SPATIAL ALIGNMENT
    #

    #Take first header as template for coadd header
    hdr0 = h2DList[0]

    #Get 2D WCS
    wcs0 = WCS(hdr0)

    #Get plate-scales
    dx0,dy0 = proj_plane_pixel_scales(wcs0)

    #Make aspect ratio in terms of plate scales 1:1
    if   dx0>dy0: wcs0.wcs.cd[:,0] /= dx0/dy0
    elif dy0>dx0: wcs0.wcs.cd[:,1] /= dy0/dx0
    else: pass

    #Set coadd canvas to desired orientation

    #Try to load orientation from header
    pa0 = None
    for rotKey in ["ROTPA","ROTPOSN"]:
        if rotKey in hdr0:
            pa0=hdr0[rotKey]
            break

    #If no value was found, set to desired PA so that no rotation takes place
    if pa0==None:
        print("No header key for PA (ROTPA or ROTPOSN) found in first input file. Cannot guarantee output PA.")
        pa0 = PA

    #Rotate WCS to the input PA
    wcs0 = rotate(wcs0,pa0-PA)

    #Set new WCS - we will use it later to create the canvas
    wcs0.wcs.set()

    # We don't know which corner is which for an arbitrary rotation, so map each vertex to the coadd space
    x0,y0 = 0,0
    x1,y1 = 0,0
    for fp in footPrints:
        ras,decs = fp[:,0],fp[:,1]
        xs,ys = wcs0.all_world2pix(ras,decs,0)

        xMin,yMin = np.min(xs),np.min(ys)
        xMax,yMax = np.max(xs),np.max(ys)

        if xMin<x0: x0=xMin
        if yMin<y0: y0=yMin

        if xMax>x1: x1=xMax
        if yMax>y1: y1=yMax

    #These upper and lower x-y bounds to shift the canvas
    dx = int(round((x1-x0)+1))
    dy = int(round((y1-y0)+1))

    #
    ra0,dec0 = wcs0.all_pix2world(x0,y0,0)
    ra1,dec1 = wcs0.all_pix2world(x1,y1,0)

    #Set the lower corner of the WCS and create a canvas
    wcs0.wcs.crpix[0] = 1
    wcs0.wcs.crval[0] = ra0
    wcs0.wcs.crpix[1] = 1
    wcs0.wcs.crval[1] = dec0
    wcs0.wcs.set()

    hdr0 = wcs0.to_header()

    #
    # Now that WCS has been figured out - make header and regenerate WCS
    #
    coaddHdr = hdrList[0].copy()

    coaddHdr["NAXIS1"] = dx
    coaddHdr["NAXIS2"] = dy
    coaddHdr["NAXIS3"] = len(wNew)

    coaddHdr["CRPIX1"] = hdr0["CRPIX1"]
    coaddHdr["CRPIX2"] = hdr0["CRPIX2"]
    coaddHdr["CRPIX3"] = 1

    coaddHdr["CRVAL1"] = hdr0["CRVAL1"]
    coaddHdr["CRVAL2"] = hdr0["CRVAL2"]
    coaddHdr["CRVAL3"] = wNew[0]

    coaddHdr["CD1_1"]  = wcs0.wcs.cd[0,0]
    coaddHdr["CD1_2"]  = wcs0.wcs.cd[0,1]
    coaddHdr["CD2_1"]  = wcs0.wcs.cd[1,0]
    coaddHdr["CD2_2"]  = wcs0.wcs.cd[1,1]

    coaddHdr2D = get2DHeader(coaddHdr)
    coaddWCS   = WCS(coaddHdr2D)
    coaddFP = coaddWCS.calc_footprint()


    #Get scales and pixel size of new canvas
    coadd_dX,coadd_dY = proj_plane_pixel_scales(coaddWCS)
    coadd_pxArea = (coadd_dX*coadd_dY)

    # Create data structures to store coadded cube and corresponding exposure time mask
    coaddData = np.zeros((len(wNew),coaddHdr["NAXIS2"],coaddHdr["NAXIS1"]))
    coaddExp  = np.zeros_like(coaddData)

    W,Y,X = coaddData.shape

    if plot:
        fig1,ax = plt.subplots(1,1)
        for fp in footPrints:
            ax.plot( -fp[0:2,0],fp[0:2,1],'k-')
            ax.plot( -fp[1:3,0],fp[1:3,1],'k-')
            ax.plot( -fp[2:4,0],fp[2:4,1],'k-')
            ax.plot( [ -fp[3,0], -fp[0,0] ] , [ fp[3,1], fp[0,1] ],'k-')
        for fp in [coaddFP]:
            ax.plot( -fp[0:2,0],fp[0:2,1],'r-')
            ax.plot( -fp[1:3,0],fp[1:3,1],'r-')
            ax.plot( -fp[2:4,0],fp[2:4,1],'r-')
            ax.plot( [ -fp[3,0], -fp[0,0] ] , [ fp[3,1], fp[0,1] ],'r-')

        fig1.show()
        plt.waitforbuttonpress()

        plt.close()

        plt.ion()

        grid_width  = 2
        grid_height = 2
        gs = gridspec.GridSpec(grid_height,grid_width)

        fig2 = plt.figure(figsize=(12,12))
        inAx  = fig2.add_subplot(gs[ :1, : ])
        skyAx = fig2.add_subplot(gs[ 1:, :1 ])
        imgAx = fig2.add_subplot(gs[ 1:, 1: ])

    # Run through each input frame
    for i,f in enumerate(fitsList):

        #Get shape of current cube
        w,y,x = f[0].data.shape

        # Create intermediate frame to build up coadd contributions pixel-by-pixel
        buildFrame = np.zeros_like(coaddData)

        # Fract frame stores a coverage fraction for each coadd pixel
        fractFrame = np.zeros_like(coaddData)

        # Get wavelength coverage of this FITS
        wavIndices    = np.ones(f[0].data.shape[0],dtype=bool)
        wavIndices[wNew<wav0s[i]] = 0
        wavIndices[wNew>wav1s[i]] = 0

        # Convert to a flux-like unit if the input data is in counts
        if "electrons" in f[0].header["BUNIT"]:

            # Scale data to be in counts per unit time
            if varData: f[0].data /= expTimes[i]**2
            else: f[0].data /= expTimes[i]

            f[0].header["BUNIT"] = "electrons/sec"

        print(("Mapping %s to coadd frame (%i/%i)"%(fileList[i],i+1,len(fitsList))), end=' ')

        if plot:
            inAx.clear()
            skyAx.clear()
            imgAx.clear()
            inAx.set_title("Input Frame Coordinates")
            skyAx.set_title("Sky Coordinates")
            imgAx.set_title("Coadd Coordinates")
            imgAx.set_xlabel("X")
            imgAx.set_ylabel("Y")
            skyAx.set_xlabel("RA (hh.hh)")
            skyAx.set_ylabel("DEC (dd.dd)")
            xU,yU = x,y
            inAx.plot( [0,xU], [0,0], 'k-')
            inAx.plot( [xU,xU], [0,yU], 'k-')
            inAx.plot( [xU,0], [yU,yU], 'k-')
            inAx.plot( [0,0], [yU,0], 'k-')
            inAx.set_xlim( [-5,xU+5] )
            inAx.set_ylim( [-5,yU+5] )
            #inAx.plot(qXin,qYin,'ro')
            inAx.set_xlabel("X")
            inAx.set_ylabel("Y")
            xU,yU = X,Y
            imgAx.plot( [0,xU], [0,0], 'r-')
            imgAx.plot( [xU,xU], [0,yU], 'r-')
            imgAx.plot( [xU,0], [yU,yU], 'r-')
            imgAx.plot( [0,0], [yU,0], 'r-')
            imgAx.set_xlim( [-0.5,xU+1] )
            imgAx.set_ylim( [-0.5,yU+1] )
            for fp in footPrints[i:i+1]:
                skyAx.plot( -fp[0:2,0],fp[0:2,1],'k-')
                skyAx.plot( -fp[1:3,0],fp[1:3,1],'k-')
                skyAx.plot( -fp[2:4,0],fp[2:4,1],'k-')
                skyAx.plot( [ -fp[3,0], -fp[0,0] ] , [ fp[3,1], fp[0,1] ],'k-')
            for fp in [coaddFP]:
                skyAx.plot( -fp[0:2,0],fp[0:2,1],'r-')
                skyAx.plot( -fp[1:3,0],fp[1:3,1],'r-')
                skyAx.plot( -fp[2:4,0],fp[2:4,1],'r-')
                skyAx.plot( [ -fp[3,0], -fp[0,0] ] , [ fp[3,1], fp[0,1] ],'r-')


            #skyAx.set_xlim([ra0+0.001,ra1-0.001])
            skyAx.set_ylim([dec0-0.001,dec1+0.001])


        # Loop through spatial pixels in this input frame
        for yj in range(y):

            print(("."), end=' ')
            sys.stdout.flush()

            for xk in range(x):

                # Define BL, TL, TR, BR corners of pixel as coordinates
                inPixVertices =  np.array([ [xk-0.5,yj-0.5], [xk-0.5,yj+0.5], [xk+0.5,yj+0.5], [xk+0.5,yj-0.5] ])

                # Convert these vertices to RA/DEC positions
                inPixRADEC = w2DList[i].all_pix2world(inPixVertices,0)

                # Convert the RA/DEC vertex values into coadd frame coordinates
                inPixCoadd = coaddWCS.all_world2pix(inPixRADEC,0)

                #Create polygon object for projection of this input pixel onto coadd grid
                pixIN = Polygon( inPixCoadd )


                #Get bounding pixels on coadd grid
                xP0,yP0,xP1,yP1 = (int(x) for x in list(pixIN.bounds))


                if plot:
                    inAx.plot( inPixVertices[:,0], inPixVertices[:,1],'kx')
                    skyAx.plot(-inPixRADEC[:,0],inPixRADEC[:,1],'kx')
                    imgAx.plot(inPixCoadd[:,0],inPixCoadd[:,1],'kx')

                #Get bounds of pixel in coadd image
                xP0,yP0,xP1,yP1 = (int(round(x)) for x in list(pixIN.exterior.bounds))

                # Upper bounds need to be increased to include full pixel
                xP1+=1
                yP1+=1


                # Run through pixels on coadd grid and add input data
                for xC in range(xP0,xP1):
                    for yC in range(yP0,yP1):

                        try:
                            # Define BL, TL, TR, BR corners of pixel as coordinates
                            cPixVertices =  np.array( [ [xC-0.5,yC-0.5], [xC-0.5,yC+0.5], [xC+0.5,yC+0.5], [xC+0.5,yC-0.5] ]   )

                            # Create Polygon object and store in array
                            pixCA = box( xC-0.5, yC-0.5, xC+0.5, yC+0.5 )

                            # Calculation fractional overlap between input/coadd pixels
                            overlap = pixIN.intersection(pixCA).area/pixIN.area

                            #print overlap
                            # Add fraction to fraction frame
                            fractFrame[wavIndices,yC,xC] += overlap

                            if varData: overlap=overlap**2

                            # Add data to build frame
                            buildFrame[:,yC,xC] += overlap*f[0].data[:,yj,xk]

                        except: continue
        if plot:
            fig2.canvas.draw()
            plt.waitforbuttonpress()

        #Calculate ratio of coadd pixel area to input pixel area
        pxAreaRatio = coadd_pxArea/pxAreas[i]

        # Max value in fractFrame should be pxAreaRatio - it's the biggest fraction of an input pixel that can add to one coadd pixel
        # We want to use this map now to create a flatFrame - where the values represent a covering fraction for each pixel
        flatFrame = fractFrame/pxAreaRatio

        #Replace zero-values with inf values to avoid division by zero when flat correcting
        flatFrame[flatFrame==0] = np.inf

        #Perform flat field correction for pixels that are not fully covered
        buildFrame /= flatFrame

        #Zero any pixels below user-set pixel threshold, and set flat value to inf
        buildFrame[flatFrame<pxThresh] = 0
        flatFrame[flatFrame<pxThresh] = np.inf

        # Create 3D mask of non-zero voxels from this frame
        M = flatFrame<np.inf

        # Add weight*data to coadd (numerator of weighted mean with exptime as weight)
        if varData: coaddData += (expTimes[i]**2)*buildFrame
        else: coaddData += expTimes[i]*buildFrame

        #Add to exposure mask
        coaddExp += expTimes[i]*M
        coaddExp2D = np.sum(coaddExp,axis=0)
        print("")


    if plot: plt.close()

    # Create 1D exposure time profiles
    expSpec = np.mean(coaddExp,axis=(1,2))
    expXMap = np.mean(coaddExp,axis=(0,1))
    expYMap = np.mean(coaddExp,axis=(0,2))

    # Normalize the profiles
    expSpec/=np.max(expSpec)
    expXMap/=np.max(expXMap)
    expYMap/=np.max(expYMap)

    # Convert 0s to 1s in exposure time cube
    ee = coaddExp.flatten()
    ee[ee==0] = 1
    coaddExp = np.reshape( ee, coaddData.shape )

    # Divide by sum of weights (or square of sum)

    if varData: coaddData /= coaddExp**2
    else: coaddData /= coaddExp

    # Create FITS object
    coaddHDU = fits.PrimaryHDU(coaddData)
    coaddFITS = fits.HDUList([coaddHDU])
    coaddFITS[0].header = coaddHdr

    #Exposure time threshold, relative to maximum exposure time, below which to crop.
    useW = expSpec>expThresh
    useX = expXMap>expThresh
    useY = expYMap>expThresh

    #Trim the data
    coaddFITS[0].data = coaddFITS[0].data[useW]
    coaddFITS[0].data = coaddFITS[0].data[:,useY]
    coaddFITS[0].data = coaddFITS[0].data[:,:,useX]

    #Get 'bottom/left/blue corner of cropped data
    W0 = np.argmax(useW)
    X0 = np.argmax(useX)
    Y0 = np.argmax(useY)

    #Update the WCS to account for trimmed pixels
    coaddFITS[0].header["CRPIX3"] -= W0
    coaddFITS[0].header["CRPIX2"] -= Y0
    coaddFITS[0].header["CRPIX1"] -= X0

    #Create FITS for variance data if we are propagating that
    return coaddFITS