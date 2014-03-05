# -*- coding: utf-8 -*-
"""
Created on Wed Feb 26 08:18:31 2014

@author: max
 
Creating ice persistency maps from NSIDC sea ice concentration charts

* Bin2GeoTiff -- converting binary NSIDC maps to GeoTIFF
* CreateIcePercistanceMap -- create ice persistence map
* CreateMaxMinIce -- create min/max ice maps
* EPSG3411_2_EPSG3575 -- reproject raster from EPSG:3411 to EPSG:3575
* ReprojectShapefile -- reproject shapefiles from EPSG:3411 to EPSG:3575

Documentation before each function and at https://github.com/npolar/RemoteSensing/wiki/Sea-Ice-Frequency

"""

import struct, numpy, gdal, gdalconst, glob, os, osr

def EPSG3411_2_EPSG3575(infile):
    '''
    reprojects the infile from NSIDC 3411 to EPSG 3575
    outputfiel has 25km resolution
    '''
    
    (infilepath, infilename) = os.path.split(infile)
    (infileshortname, extension) = os.path.splitext(infilename)
    outfile = infilepath + '\\EPSG3575\\' + infileshortname + '_EPSG3575.tif'
    print ' Reproject ', infile, ' to ', outfile 
    os.system('gdalwarp -s_srs EPSG:3411 -tr 25000 -25000 -t_srs EPSG:3575 -of GTiff ' + infile + ' ' + outfile)
    
def ReprojectShapefile(infile, inproj = "EPSG:3411", outproj = "EPSG:3575"):
    '''
    Reprojects the shapefile given in infile
    
    inproj and outproj in format "EPSG:3575", for the filename the ":" is 
    removed in the function
    
    Assumes existence of folder as "EPSG3575" or "EPSG32633" or...
    '''
    
    #Define outputfile name
    (infilepath, infilename) = os.path.split(infile)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
    
    reprshapepath = infilepath + '\\' + outproj[0:4] + outproj[5:9]
    reprshapeshortname = infileshortname + '_' + outproj[0:4] + outproj[5:9]
    reprshapefile = reprshapepath + '\\'+ reprshapeshortname + extension
    
    #Reproject using ogr commandline
    print 'Reproject Shapefile ', infile    
    os.system('ogr2ogr -s_srs ' + inproj + ' -t_srs ' + outproj + ' '  + reprshapefile + ' ' + infile )
    print 'Done Reproject'

    return reprshapefile    

def Bin2GeoTiff(infile,outfilepath ):
    '''
        This function takes the NSIDC charts, being a flat binary string, and converts them to GeoTiff. 
        This function takes the NSIDC charts, being a flat binary string, and converts them to GeoTiff. Some details here:
        http://geoinformaticstutorial.blogspot.no/2014/02/reading-binary-data-nsidc-sea-ice.html

        Info on the ice concentration charts: http://nsidc.org/data/docs/daac/nsidc0051_gsfc_seaice.gd.html 
        Info on the map projection: http://nsidc.org/data/polar_stereo/ps_grids.html

        The GeoTiff files are map projected to EPSG:3411, being the NSIDC-specific projection.
        There also exists a GeoTiff reprojected to EPSG:3575 which is the NP-standard for Barents/Fram-Strait.
        Details on how to map project are found here:
        http://geoinformaticstutorial.blogspot.no/2014/03/geocoding-nsidc-sea-ice-concentration.html
        
    '''
    
    #Define file names 
    (infilepath, infilename) = os.path.split(infile)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
        
    outfile = outfilepath + infileshortname + '.tif'
    #Dimensions from https://nsidc.org/data/docs/daac/nsidc0051_gsfc_seaice.gd.html
    height = 448
    width = 304
    
    #for this code, inspiration found at https://stevendkay.wordpress.com/category/python/
    icefile = open(infile, "rb")
    contents = icefile.read()
    icefile.close()
    
    # unpack binary data into a flat tuple z
    s="%dB" % (int(width*height),)
    z=struct.unpack_from(s, contents, offset = 300)
    
    nsidc = numpy.array(z).reshape((448,304))
    #nsidc = numpy.rot90(nsidc, 3)
    
    #write the data to a Geotiff
    
    driver = gdal.GetDriverByName("GTiff")
    outraster = driver.Create(outfile,  width, height,1, gdal.GDT_Int16 )
    if outraster is None: 
        print 'Could not create '
        return
    
    geotransform = (-3850000.0, 25000.0 ,0.0 ,5850000.0, 0.0, -25000.0)
    outraster.SetGeoTransform(geotransform)
    outband = outraster.GetRasterBand(1)
    #Write to file     
    outband.WriteArray(nsidc)
    
    spatialRef = osr.SpatialReference()
    #spatialRef.ImportFromEPSG(3411)  --> this one does for some reason NOT work, but proj4 does
    spatialRef.ImportFromProj4('+proj=stere +lat_0=90 +lat_ts=70 +lon_0=-45 +k=1 +x_0=0 +y_0=0 +a=6378273 +b=6356889.449 +units=m +no_defs')
    outraster.SetProjection(spatialRef.ExportToWkt() )
    outband.FlushCache()
    
    #Clear arrays and close files
    outband = None
    outraster = None
    nsidc = None
    
    #reproject to EPSG3575
    EPSG3411_2_EPSG3575(outfile)
    
    
def CreateIcePercistanceMap(inpath, outfilepath):
    '''
    Creates map showing percentage ice coverage over a given period
    This function creates the ice persistence charts. 
    The function loops through each concentration map, if the value is larger
    than 38 = 15.2%, the value of "100.0 / NumberOfDays" is added --> if there 
    is ice every single day, that pixel will be "100"

    Output is available both as EPSG:3411 and EPSG:3575    
    '''
    
    #register all gdal drivers
    gdal.AllRegister()
    
    # Iterate through all rasterfiles
    filelist = glob.glob(outfilepath + '*.tif')
    
    #Determine Number of Days from available ice chart files
    NumberOfDays = len(filelist)
    print ", number of days:  ", NumberOfDays
    
    firstfilename = filelist[0]
    #Define file names 
    (infilepath, infilename) = os.path.split(firstfilename)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
        
    outfile = inpath + 'icechart_persistencemap.tif'
    
    #open the IceChart
    icechart = gdal.Open(firstfilename, gdalconst.GA_ReadOnly)
    if firstfilename is None:
        print 'Could not open ', firstfilename
        return
    #get image size
    rows = icechart.RasterYSize
    cols = icechart.RasterXSize    
    #create output images
    driver = icechart.GetDriver()
    outraster = driver.Create(outfile, cols, rows, 1, gdal.GDT_Float64 )
    if outraster is None: 
        print 'Could not create ', outfile
        return
    
    # Set Geotransform and projection for outraster
    outraster.SetGeoTransform(icechart.GetGeoTransform())
    outraster.SetProjection(icechart.GetProjection())
    
    rows = outraster.RasterYSize
    cols = outraster.RasterXSize
    raster = numpy.zeros((rows, cols), numpy.float) 
    outraster.GetRasterBand(1).WriteArray( raster )
    
    #Create output array and fill with zeros
    outarray = numpy.zeros((rows, cols), numpy.float)    
    
    #Loop through all files to do calculation
    for infile in filelist:
        
        (infilepath, infilename) = os.path.split(infile)
        print 'Processing ', infilename
        
        #open the IceChart
        icechart = gdal.Open(infile, gdalconst.GA_ReadOnly)
        if infile is None:
            print 'Could not open ', infilename
            return
        
        #get image size
        rows = icechart.RasterYSize
        cols = icechart.RasterXSize
                
        #get the bands 
        outband = outraster.GetRasterBand(1)
        

        
        #Read input raster into array
        iceraster = icechart.ReadAsArray()
        
        #Array calculation with numpy -- much faster
        outarray = numpy.where( (iceraster >=  38), (outarray + ( 100.0 / NumberOfDays ) ) , outarray)
        outarray = numpy.where( (iceraster ==   251), 251 , outarray)
        outarray = numpy.where( (iceraster ==   252), 252 , outarray)
        outarray = numpy.where( (iceraster ==   253), 253 , outarray)
        outarray = numpy.where( (iceraster ==   254), 254 , outarray)
        outarray = numpy.where( (iceraster ==   255), 255 , outarray)
    
       
        #Clear iceraster for next loop -- just in case
        iceraster = None
        
    outband.WriteArray(outarray)
    outband.FlushCache()
       

    #Clear arrays and close files
    outband = None
    iceraster = None
    outraster = None
    outarray = None
    
    #reproject to EPSG3575
    EPSG3411_2_EPSG3575(outfile)
    
    return outfile
    print 'Done Creating Persistence Map'
    
def CreateMaxMinIce(inpath, outfilepath):   
    ''' 
         Creates maximum and minimum ice map, GeoTIFF and shapefile
         maximum = at least one day ice at this pixel
         minimum = every day ice at this pixel
         In addition a file simply giving the number of days with ice
         
         The poly shapefile has all features as polygon, the line shapefile
         only the max or min ice edge
    
    '''
    
    #register all gdal drivers
    gdal.AllRegister()
    
    # Iterate through all rasterfiles
    filelist = glob.glob(outfilepath + '*.tif')
    
    #Determine Number of Days from available ice chart files
    NumberOfDays = len(filelist)
    
    #Files are all the same properties, so take first one to get info
    firstfilename = filelist[0]
    
    #Define file names 
    (infilepath, infilename) = os.path.split(firstfilename)             #get path and filename seperately
    (infileshortname, extension) = os.path.splitext(infilename)
    
    outfile =  inpath + 'icechart_NumberOfDays.tif'   
    outfilemax = inpath + 'icechart_maximum.tif'
    outfilemin = inpath + 'icechart_minimum.tif'
    
    outshape_polymax = inpath + 'icechart_poly_maximum.shp'
    outshape_polymin = inpath + 'icechart_poly_minimum.shp'
    outshape_polymax2 = inpath + 'icechart_poly_maximum2.shp'
    outshape_polymin2 = inpath + 'icechart_poly_minimum2.shp'
    outshape_linemax = inpath + 'icechart_line_maximum.shp'
    outshape_linemin = inpath + 'icechart_line_minimum.shp'
    
    outshape_tempmax = inpath + 'icechart_tempmax.shp'
    outshape_tempmin = inpath + 'icechart_tempmin.shp'
   
    #open the IceChart
    icechart = gdal.Open(firstfilename, gdalconst.GA_ReadOnly)
    if firstfilename is None:
        print 'Could not open ', firstfilename
        return
    #get image size
    rows = icechart.RasterYSize
    cols = icechart.RasterXSize    
    #create output images
    driver = icechart.GetDriver()
    outraster = driver.Create(outfile, cols, rows, 1, gdal.GDT_Float64 )
    if outraster is None: 
        print 'Could not create ', outfile
        return    
    
    outrastermax = driver.Create(outfilemax, cols, rows, 1, gdal.GDT_Float64 )
    if outrastermax is None: 
        print 'Could not create ', outfilemax
        return
    
    outrastermin = driver.Create(outfilemin, cols, rows, 1, gdal.GDT_Float64 )
    if outrastermin is None: 
        print 'Could not create ', outfilemin
        return
   
    # Set Geotransform and projection for outraster
    outraster.SetGeoTransform(icechart.GetGeoTransform())
    outraster.SetProjection(icechart.GetProjection())
    outrastermax.SetGeoTransform(icechart.GetGeoTransform())
    outrastermax.SetProjection(icechart.GetProjection())
    
    outrastermin.SetGeoTransform(icechart.GetGeoTransform())
    outrastermin.SetProjection(icechart.GetProjection())
    
    rows = outrastermax.RasterYSize
    cols = outrastermax.RasterXSize
    raster = numpy.zeros((rows, cols), numpy.float) 
    
    outraster.GetRasterBand(1).WriteArray( raster )    
    outrastermax.GetRasterBand(1).WriteArray( raster )
    outrastermin.GetRasterBand(1).WriteArray( raster )
    
    #Create output array and fill with zeros
    outarray = numpy.zeros((rows, cols), numpy.float)    
    outarraymax = numpy.zeros((rows, cols), numpy.float)
    outarraymin = numpy.zeros((rows, cols), numpy.float)
    
    
    #Loop through all files to do calculation
    for infile in filelist:
        
        (infilepath, infilename) = os.path.split(infile)
        print 'Processing ', infilename
        
        #open the IceChart
        icechart = gdal.Open(infile, gdalconst.GA_ReadOnly)
        if infile is None:
            print 'Could not open ', infilename
            return
        
        #Read input raster into array
        iceraster = icechart.ReadAsArray()
        
        #Array calculation with numpy -- much faster
        outarray = numpy.where( (iceraster >=  38), outarray + 1 , outarray)
        outarray = numpy.where( (iceraster ==   251), 251 , outarray)
        outarray = numpy.where( (iceraster ==   252), 252 , outarray)
        outarray = numpy.where( (iceraster ==   253), 253 , outarray)
        outarray = numpy.where( (iceraster ==   254), 254 , outarray)
        outarray = numpy.where( (iceraster ==   255), 255 , outarray)
               
        #Clear iceraster for next loop -- just in case
        iceraster = None
    
    
    #get the bands 
    outband = outraster.GetRasterBand(1)    
    outbandmax = outrastermax.GetRasterBand(1)
    outbandmin = outrastermin.GetRasterBand(1)

    #Calculate the maximum-map from the NumberOfDays outarray
    outarraymax = numpy.where( (outarray == 0), 0, 1 )
    outarraymax = numpy.where( (outarray ==   251), 251 , outarraymax)
    outarraymax = numpy.where( (outarray ==   252), 252 , outarraymax)
    outarraymax = numpy.where( (outarray ==   253), 253 , outarraymax)
    outarraymax = numpy.where( (outarray ==   254), 254 , outarraymax)
    outarraymax = numpy.where( (outarray ==   255), 255 , outarraymax)
    
    #Calculate the minimum-map from the NumberOfDays outarray
    outarraymin = numpy.where( (outarray == NumberOfDays), 1, 0 )
    outarraymin = numpy.where( (outarray ==   251), 251 , outarraymin)
    outarraymin = numpy.where( (outarray ==   252), 252 , outarraymin)
    outarraymin = numpy.where( (outarray ==   253), 253 , outarraymin)
    outarraymin = numpy.where( (outarray ==   254), 254 , outarraymin)
    outarraymin = numpy.where( (outarray ==   255), 255 , outarraymin)
    
    #Write all arrays to file
    outband.WriteArray(outarray)
    outband.FlushCache()    
    
    outbandmax.WriteArray(outarraymax)
    outbandmax.FlushCache()
    
    outbandmin.WriteArray(outarraymin)
    outbandmin.FlushCache()
    
    #Clear arrays and close files
    outband = None
    outbandmax = None
    outbandmin = None
    iceraster = None
    outraster = None    
    outrastermax = None
    outrastermin = None
    outarray = None
    outarraymax = None
    outarraymin = None     
    
    ##### CONVERSION TO SHAPEFILE #######################    
    print '\n Convert ', outfilemax, ' to shapefile.'
    os.system('gdal_polygonize.py ' + outfilemax + ' -f "ESRI Shapefile" ' + outshape_polymax + ' icechart_poly_maximum DN' )
    #os.system('ogr2ogr ' + outshape_polymax + ' ' +  outshape_polymax + ' -sql "SELECT *, OGR_GEOM_AREA AS area FROM input"')
    
    print '\n Convert ', outfilemin, ' to shapefile.'
    os.system('gdal_polygonize.py ' + outfilemin + ' -f "ESRI Shapefile" ' + outshape_polymin + ' icechart_poly_minimum DN' ) 
    print "add area layer to polygon"
    os.system('ogr2ogr '+ outshape_tempmax + ' ' + outshape_polymax + ' -sql "SELECT *, OGR_GEOM_AREA AS area FROM icechart_poly_maximum" ' )
    os.system('ogr2ogr '+ outshape_tempmin + ' ' + outshape_polymin + ' -sql "SELECT *, OGR_GEOM_AREA AS area FROM icechart_poly_minimum" ')
    #os.remove(outshape_polymax)
    #os.remove(outshape_polymin)
    print "select iceedge"
    os.system('ogr2ogr -sql "SELECT * FROM icechart_tempmax WHERE DN=1 AND area > 10000000000000.0" ' +  outshape_polymax2 + ' ' + outshape_tempmax )
    os.system('ogr2ogr -sql "SELECT * FROM icechart_tempmin WHERE DN=1 AND area > 10000000000000.0" ' +  outshape_polymin2 + ' ' + outshape_tempmin )
    
    ### Create polyline showing ice edge
    # Convert polygon to lines
    print 'Convert ice edge map to Linestring Map'
    os.system('ogr2ogr -progress -nlt LINESTRING -where "DN=1" ' + outshape_linemax + ' ' + outshape_polymax2)
    os.system('ogr2ogr -progress -nlt LINESTRING -where "DN=1" ' + outshape_linemin + ' ' + outshape_polymin2)
    
    #Reproject to EPSG:3575
    ReprojectShapefile(outshape_polymax)
    ReprojectShapefile(outshape_polymin)
    ReprojectShapefile(outshape_linemax)
    ReprojectShapefile(outshape_linemin)
  
    #reproject to EPSG3575
    EPSG3411_2_EPSG3575(outfilemax)        
    EPSG3411_2_EPSG3575(outfilemin) 
    EPSG3411_2_EPSG3575(outfile) 
    print 'Done Creating Max/Min Maps'        
    return outfilemax, outfilemin
    
     
     
##############################################################################

###   Core of Program follows here ###

##############################################################################


infilepath = 'U:\\SSMI\\IceConcentration\\NASATEAM\\final-gsfc\\north\\daily\\2012\\'
outfilepath = 'C:\\Users\\Max\\Desktop\\test\\'


#filelist = glob.glob(infilepath + 'nt_201202*.bin')

#Get all files from given month
startyear = 1994
stopyear = 1995
month = 3


#Create filelist including all files for the given month between startyear and stopyear inclusive
filelist = []
for year in range(startyear, stopyear + 1):
    foldername = 'U:\\SSMI\\IceConcentration\\NASATEAM\\final-gsfc\\north\\daily\\' + str(year) + '\\'
    if month < 10: 
        file_searchstring = 'nt_' + str(year) + '0' + str(month) + '*.bin'
    else:
        file_searchstring = 'nt_' + str(year)  + str(month) + '*.bin'
    
    foldersearchstring = foldername + file_searchstring
    filelist.extend(glob.glob(foldersearchstring))
    print filelist

for icechart in filelist:
    #Convert NSIDC files to GeoTiff
    print'convert ', icechart
    Bin2GeoTiff(icechart, outfilepath)

    
CreateIcePercistanceMap(outfilepath, outfilepath)

max_ice, min_ice = CreateMaxMinIce(outfilepath, outfilepath)