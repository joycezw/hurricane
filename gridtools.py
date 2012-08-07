#
#   Grid processing tools
#
#       extract grids for classifer 
#
#                     by lemin (Jake Lee)
#

"""
TO DO list
    1. grid grouping loop takes long time => need to make it faster
        *** dictionary to matrix conversion need to be faster, too
    2. incremental classification for grid classifier

    
"""

import pdb
import numpy as np
import glob
import timeit
import time
from copy import copy
import sys
import getopt
import pickle


"""
    readMonth
        read files in a month dir and combine into one matrix
    NOT TESTED YET
"""
def readMonth(monthdir, pathdir="GFSdat", maxfiles=None):
    fnames = ''.join([pathdir,'/',monthdir,'/*.dat'])
    files = glob.glob(fnames)
    nfcnt = 0
    ret = None
    for f in files:
        if ret is None:
            ret = np.loadtxt(filename, skiprows=1) 
        else:
            ret = np.vstack((ret,np.loadtxt(filename, skiprows=1)))
        nfcnt += 1 
        if maxfiles is not None and nfcnt >= maxfiles:
            break
    return ret


"""
    readGrids
        read a single GFS file and create a dictionary based on grid size
"""
def readGrids(filename, gridsize=1):
    ret={}
    data = np.loadtxt(filename, skiprows=1) #, usecols=range(8))
    # grouping into grids
    if gridsize>0:
        dsize = 2*gridsize
        for lon in xrange(0,360,dsize):
            for lat in xrange(-90,90,dsize):
                temp = data[data[:,1]>=lat]
                temp = temp[temp[:,1]<=lat+dsize]
                temp = temp[temp[:,0]>=lon]
                temp = temp[temp[:,0]<=lon+dsize]
                #ret[(lat,lon,lat+dsize,lon+dsize)] = temp[:,2:] # take lat and lon out
                ret[(lat,lon,lat+dsize,lon+dsize)] = temp # MAYBE LOCATION INFO IS SIGNIFICANT
    else:
        for i in np.unique(data[:,0]):
            for j in np.unique(data[:,1]):
                ret[(i,j)] = data[data[:,0]==i][data[data[:,0]==i][:,1]==j]#[:,2:]
    return ret


"""
    readStrong
        read a single strong info and store in a matrix with time, lat, and lon columns
"""
def readStorm(filename):
    #data = np.loadtxt(filename,dtype={'names': ['id','lat','lon','wind','press','type','basin'],'formats': ['S10','S4','S4','i4','i4','S2','S2']} ) 
    #data = np.loadtxt(filename,dtype='S10') 
    data = [] 
    with open(filename,'r') as f:
        while True:
            try :
                fields = f.readline().split()
                if len(fields)==0: break

                #fname = ''.join(['g20',fields[0][2:], '.dat'])
                time = int(fields[0][2:])
                if fields[1][-1]=='S': lat = -float(fields[1][:-1])/10.
                else: lat = float(fields[1][:-1])/10.
                if fields[2][-1]=='W': lon = 360. - float(fields[2][:-1])/10.
                else: lon = float(fields[2][:-1])/10.
                #data.append((fname,lat,lon))
                data.append([time,lat,lon])
            except EOFError:    
                print "EOF reached!"
                break
    return np.array(data)

"""
    readStorms
        read all strom tracking information 
"""
def readStorms(pathdir="tracks", filterSt=None, filterEnd=None, filteropt='month'):
    ret=None
    fstorms = glob.glob('tracks/*.DAT')
    for fs in fstorms:
        if ret==None:
            ret = readStorm(fs)
        else:
            ret=np.vstack((ret, readStorm(fs)))
    #sort by date
    sortidx=ret[:,0].argsort(axis=0)
    ret = ret[sortidx,:]

    if filteropt=='month':
        # apply filter (month)
        if filterEnd is None:
            filterEnd = filterSt
        filterEnd = filterEnd + 0.01
        filterSt = filterSt*1.e06 
        filterEnd = filterEnd*1.e06 
    else:
        # apply filter (fulltime)
        filterSt = float(filterSt[2:])
        filterEnd = float(filterEnd[2:]) + 1
    if filterSt is not None:
        ret=ret[ret[:,0]>=filterSt]
        ret=ret[ret[:,0]<filterEnd]
    return ret



def usage():
    print "gridtools: "
    print "   options"
    print "   -s    start month (ie. 8.07 for July 2008)"
    print "   -e    end month (if not specified, use the same month with start)"
    print "   -t    hurricane tracking directory (default: tracks)"
    print "   -d    GFS data directory (default: GFSdat)"
    print "   -g    grid size (default: 1)"
    print "   -u    turn on undersampling the normal grid"
    print "   -o    output filename"
    print "   -h    show this"
    sys.exit()


def main(argv):
    opts, args = getopt.getopt(argv[1:],'t:s:e:d:g:uo:h')

    print opts, args
    targetDir = 'tracks'
    dataDir = 'GFSdat'
    gridsize = 1
    undersample = False
    endMonth = None
    startMonth = None
    for o,a in opts:
        if o == '-s': startMonth = float(a)
        elif o == '-e': endMonth = float(a)
        elif o == '-t': targetDir = a
        elif o == '-d': dataDir = a
        elif o == '-g': gridsize = a
        elif o == '-u': undersample = True
        elif o == '-o': outfile = a
        elif o == '-h': usage()
        else:
            assert False, "unhandled option"
    if endMonth is None:
        endMonth = startMonth

    print startMonth, outfile
    if startMonth is None or outfile is None: usage()
    
    storms = readStorms(targetDir, startMonth, endMonth) #"tracks",8.07)
    stormdates = np.unique(storms[:,0])

    for i in xrange(len(stormdates)):  
        trainD = None
        trainT = []

        sdate = str(int(stormdates[i]))
        fname = ''.join([dataDir,'/200',sdate[0:3],'/g200',sdate,'.dat'])
        print fname
        if sdate[-2:] != '00' and sdate[-2:] != '06' and sdate[-2:] != '12' and sdate[-2:] != '16':
            print "skip this file"
            continue

        stormsT = storms[storms[:,0]==stormdates[i]][:,1:] 
        stormsT -= (stormsT % (gridsize*2))
        stormsT = np.hstack((stormsT, stormsT+2))
        stormsT = [tuple(stormsT[j]) for j in xrange(stormsT.shape[0])]

        t0=time.time()
        data = readGrids(fname, gridsize)
        print time.time()-t0

        t0=time.time()

        if undersample:
            nsamples = 2*len(stormsT) # limit the number of normal data
            samples = np.random.random_integers(0,len(data.keys()),nsamples)
            idx=-1

        for k in data.keys():
            if undersample:
                idx+=1
                if not k in stormsT: 
                    if not idx in samples:
                        continue
                    
            if trainD is None:
                trainD = data[k].flat
            else:
                trainD = np.vstack((trainD, data[k].flat))

            if k in stormsT: 
                trainT.append(1)
            else:
                trainT.append(-1)
        print time.time()-t0

        print trainD.shape
        #t= timeit.Timer("readGrids('GFSdat/200807/g2008070106.dat', 1)")
        #print t.timeit()
        
        trainT = np.array(trainT)
        trainT.resize(trainD.shape[0],1)
        fhandle = file(outfile,'a')
        np.savetxt(fhandle, np.hstack((trainT,trainD)), delimiter=',', fmt='%1.3f') 
        fhandle.close()
        #np.save("5files.mat", np.hstack(trainT,trainD)) # binary file
        #np.savetxt(outfile, np.hstack((trainT,trainD)), delimiter=',') # store into csv

"""
    Redundant to main ... function for UI --- 
"""
def createMat(dataDir, trackDir, startf, endf, **optarg):
    storefn = optarg.pop("store", None)
    undersample = optarg.pop("undersample", False)
    gridsize = optarg.pop("gridsize", 1)
    genkeyf = optarg.pop("genkeyf", False)

    storms = readStorms(trackDir, startf, endf, filteropt='date') 
    stormdates = np.unique(storms[:,0])

    if storefn is None:
        trainD = None
        trainT = []
    if genkeyf:
        stokeys = []
        stormlocs = None
    
    for i in xrange(len(stormdates)):  
        if storefn is not None:
            trainD = None
            trainT = []

        sdate = str(int(stormdates[i]))
        fname = ''.join([dataDir,'/200',sdate[0:3],'/g200',sdate,'.dat'])
        print fname
        if sdate[-2:] != '00' and sdate[-2:] != '06' and sdate[-2:] != '12' and sdate[-2:] != '16':
            print "skip this file"
            continue

        stormsLoc = storms[storms[:,0]==stormdates[i]][:,1:] 
        stormsT = stormsLoc - (stormsLoc % (gridsize*2))
        stormsT = np.hstack((stormsT, stormsT+2))
        stormsT = [tuple(stormsT[j]) for j in xrange(stormsT.shape[0])]

        if genkeyf:
            if stormlocs is None:
                stormlocs = stormsLoc
            else:
                stormlocs = np.vstack((stormlocs, stormsLoc))

        data = readGrids(fname, gridsize)

        if undersample:
            nsamples = 2*len(stormsT) # limit the number of normal data
            samples = np.random.random_integers(0,len(data.keys()),nsamples)
            idx=-1

        for k in data.keys():
            if undersample:
                idx+=1
                if not k in stormsT: 
                    if not idx in samples:
                        continue
                    
            if trainD is None:
                trainD = data[k].flat
            else:
                trainD = np.vstack((trainD, data[k].flat))

            if k in stormsT: 
                trainT.append(1)
            else:
                trainT.append(-1)

            if genkeyf:
                stokeys.append(k)

        trainT = np.array(trainT)
        trainT.resize(trainD.shape[0],1)
        if storefn is not None:
            fhandle = file(storefn,'a')
            np.savetxt(fhandle, np.hstack((trainT,trainD)), delimiter=',', fmt='%1.3f') 
            fhandle.close()

    if genkeyf and storefn is not None:
        with open(storefn+'.keys', 'w') as f:
            pickle.dump(stokeys, f)
            pickle.dump(stormlocs, f)
            
    return np.hstack((trainT,trainD))
