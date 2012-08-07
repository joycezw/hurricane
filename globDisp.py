#  GlobeMap
#
#      Globe display for Hurricane data and classification result
#
#   based on BaseMap of mpl_toolkits
#   ref. code from http://www.scipy.org/Cookbook/Matplotlib/Maps
#
#                                       by lemin (Jake Lee)
#


from mpl_toolkits.basemap import Basemap
import matplotlib.pyplot as plt
import numpy as np
import pdb


class GlobeMap:

    def __init__(self,ax, lat=50, lon=-100):
        # set up orthographic map projection with
        # perspective of satellite looking down at 50N, 100W.
        # use low resolution coastlines.
        # don't plot features that are smaller than 1000 square km.
        self.ax = ax 
        self.dispSize = 2. # twice bigger than actual size
        self.map = Basemap(projection='ortho', lat_0 = lat, lon_0 = lon,
                      resolution = 'l', area_thresh = 1000., ax=ax)

    def drawGlobe(self,grid=10, gridopt=True):
        # draw coastlines, country boundaries, fill continents.
        self.map.drawcoastlines(ax=self.ax)
        self.map.drawcountries(ax=self.ax)
        #self.map.fillcontinents(color = 'green')
        #self.map.drawmapboundary()
        #self.map.drawlsmask(land_color='#FFFFCC', ocean_color='#6699FF', lakes=True, ax=self.ax)
        self.map.drawlsmask(land_color='yellowgreen', ocean_color='#CCFFFF', lakes=True, ax=self.ax)

        # draw the edge of the self.map projection region (the projection limb)
        # draw lat/lon grid lines every 2 degrees.
        if gridopt:
            self.map.drawmeridians(np.arange(0, 360, grid),ax=self.ax)
            self.map.drawparallels(np.arange(-90, 90, grid),ax=self.ax)

        plt.draw()

    def drawSatellite(self):
        self.map.bluemarble()
        plt.draw()

    def drawHurricanes(self,hurricanes):
        # lat/lon coordinates 
        lats = list(hurricanes[:,0])
        lons = list(hurricanes[:,1])

        # compute the native self.map projection coordinates for cities.
        x,y = self.map(lons,lats)  # by __call__ function definition

        # take the positions on the backside of globe display out
        subidx = 0
        for i in xrange(len(x)):
            if x[i-subidx] >1e20 or y[i-subidx] > 1e20:
                x.pop(i-subidx)
                y.pop(i-subidx)
                subidx = subidx + 1

        # plot filled circles at the locations of the cities.
        self.map.plot(x,y,'ro', markersize=5*self.dispSize)
        plt.draw()
 

    def fillGrids(self,gridsCoord):
        for grid in gridsCoord:
            #self.map.drawgreatcircle(grid[1],grid[0],grid[3],grid[2])
            x, y = self.map([grid[1],grid[3]], [grid[0],grid[2]])
            if 1e30 in x or 1e30 in y: continue
            self.map.tissot((grid[1]+grid[3])/2., (grid[0]+grid[2])/2., (grid[3]-grid[1])*self.dispSize/2., 100)
        plt.draw()
