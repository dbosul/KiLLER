"""CWITools library for handling of parameter (.param) files.

This module contains functions for loading, creating and saving CWITools
parameter files, which are needed to make use of the CWITools.reduction module.


"""
from astropy.io import fits
import numpy as np
import sys

parameterTypes = {  "TARGET_NAME":str,
                    "TARGET_RA":float,
                    "TARGET_DEC":float,
                    "RA_ALIGN":float,
                    "DEC_ALIGN":float,
                    "INPUT_DIRECTORY":str,
                    "OUTPUT_DIRECTORY":str,
                    "SEARCH_DEPTH":int,
                    "ID_LIST":list
                 }

def loadparams(paramPath):
    """Load a CWITools parameter file into a dictionary structure.

    Args:
        paramPath (str): Path to CWITools parameter file.

    Returns:
        dict: Python dictionary containing CWITools parameters

    """
    global parameterTypes

    params = { x:None for x in parameterTypes.keys() }
    params["ID_LIST"] = []

    for line in open(paramPath,'r'):

        if line[0]=='>': params["ID_LIST"].append(line.replace('>',''))
        elif '=' in line:
            line = line.replace(' ','')     #Remove white spaces
            line = line.replace('\n','')    #Remove line ending
            line = line.split('#')[0]       #Remove any comments

            key,val = line.split('=')

            if key.upper()=='NONE' or val=='': params[key]=None
            elif parameterTypes[key]==float: params[key]=float(val)
            elif parameterTypes[key]==int: params[key]=int(val)
            else: params[key]=val

    for p in parameterTypes.keys():
        if not params.has_key(p):
            print("WARNING: Parameter %s missing from %s."%(p,paramPath))
            params[p] = None

    return params

def findfiles(params,cubeType):
    """Finds the input files given a CWITools parameter file and cube type.

    Args:
        params (dict): CWITools parameters dictionary.
        cubeType (str): Type of cube (e.g. icubes.fits) to load.

    Returns:
        string list: List of file paths of input cubes.

    """
    print(("Locating %s files:" % cubeType))

    #Check data directory exists
    if not os.path.isdir(params["INPUT_DIRECTORY"]):
        print(("Data directory (%s) does not exist. Please correct and try again." % params["DATA_DIR"]))
        sys.exit()

    #Load target cubes
    datadir = params["INPUT_DIRECTORY"]
    depth   = params["SEARCH_DEPTH"]
    id_list = params["ID_LIST"]
    N_files = len(id_list)


    target_files = ["" for i in range(N) ]
    for root, dirs, files in os.walk(datadir):
        rec = root.replace(datadir,'').count("/")
        if rec > depth: continue
        else:
            for f in files:
                if cubeType in f:
                    for i,ID in enumerate(id_list):
                        if ID in f:
                            target_files[i] = os.path.join(root,f)

    #Print file paths or file not found errors
    incomplete = False
    for i,f in enumerate(target_files):
        if f!="": print(f)
        else:
            incomplete = True
            print(("File not found: ID:%s Type:%s" % (id_list[i],cubeType)))

    #Current mode - exit if incomplete
    if incomplete:
        print("Some input files are missing. Please make sure files exist or comment out the relevant lines paramfile with '#'")
        sys.exit()

    print("")

    return target_files