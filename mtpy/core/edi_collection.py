"""
Description:
To compute and encapsulate the properties of a set of EDI files

Author: fei.zhang@ga.gov.au

InitDate: 2017-04-20
"""

from __future__ import print_function
import sys
import os, glob
import logging
import csv
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, LineString, LinearRing
import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
import mtpy.core.mt as mt

from mtpy.utils.mtpylog import MtPyLog

logger = MtPyLog().get_mtpy_logger(__name__)
logger.setLevel(logging.DEBUG)

def is_it_in(anum, aseq):
    """
    check if anum is in asequence by a small tolerance
    :param anum:
    :param aseq:
    :return:
    """

    tolerance = 0.00001

    for an_number in aseq:
        if abs(anum-an_number)< tolerance:
            return True
        else:
            pass

    return False

class EdiCollection(object):
    """
    A super class to encapsulate the properties pertinent to a set of EDI files
    """

    def __init__(self, edilist, ptol=0.05):
        """
        constructor
        :param edilist: a list of edifiles with full path, for read-only
        :param ptol: period tolerance considered as equal, default 0.05 means 5%
        this param controls what freqs/periods are grouped together:
        10% may result more double counting of freq/period data than 5%.
        eg: E:\Data\MT_Datasets\WenPingJiang_EDI 18528 rows vs 14654 rows
        """
        self.edifiles = edilist
        logger.info("number of edi files in this collection: %s",
                    len(self.edifiles))
        assert len(self.edifiles) > 0

        self.num_of_edifiles = len(self.edifiles)  # number of stations
        print ("number of stations/edifiles = %s" % self.num_of_edifiles )

        self.ptol = ptol

        if self.edifiles is not None:
            self.mt_obj_list = [mt.MT(edi) for edi in self.edifiles]
        else:
            logger.error("None Edi file set")

        # get all frequencies from all edi files
        self.all_frequencies = None
        self.all_periods = self._get_all_periods()


        self.geopdf = self.create_mt_station_gdf()

        self.bound_box_dict = self.get_bounding_box()  # in orginal projection

        return


    def _get_all_periods(self):
        """
        from the list of edi files get a list of all unique frequencies.
        """
        if self.all_frequencies is not None:  # already initialized
            return

        # get all frequencies from all edi files
        all_freqs = []
        for mt_obj in self.mt_obj_list:
            all_freqs.extend(list(mt_obj.Z.freq))

        # sort all frequencies so that they are in ascending order,
        # use set to remove repeats and make an array
        self.all_frequencies = sorted(list(set(all_freqs)))

        logger.info("Number of MT Frequencies: %s", len(self.all_frequencies))

        all_periods = 1.0 / np.array(sorted(self.all_frequencies, reverse=True))

        #logger.debug("Type of the all_periods %s", type(all_periods))
        logger.info("Number of MT Periods: %s", len(all_periods))
        logger.debug(all_periods)

        return all_periods

    def get_periods_by_stats(self, percentage=50.0):
        """
        check the presence of each period in all edi files, keep a list of periods which are at least percentage present
        :return: a list of periods which are present in at least percentage edi files
        """
        adict={}
        for aper  in self.all_periods:
            afreq = 1.0/aper
            acount=0
            for mt_obj in self.mt_obj_list:
                #if afreq in mt_obj.Z.freq:
                if is_it_in(afreq, mt_obj.Z.freq):
                    acount= acount+1

            if (100.0*acount)/self.num_of_edifiles >= percentage:
                adict.update({aper:acount})
                #print (aper, acount)
            else:
                logger.info("Period %s is ignored", aper)

        mydict_ordered = sorted(adict.items(), key=lambda value: value[1], reverse=True)
        # for apair in mydict_ordered:
        #     print (apair)

        selected_periods = [pc[0] for pc in mydict_ordered]
        return selected_periods



    def create_mt_station_gdf(self, outshpfile=None):
        """
        create station location geopandas dataframe, and output to shape file outshpfile
        :return: gdf
        """

        mt_stations =[ ]

        for mtobj in self.mt_obj_list:
            mt_stations.append([mtobj.station, mtobj.lon, mtobj.lat, mtobj.elev, mtobj.utm_zone])

        pdf=pd.DataFrame(mt_stations, columns= ['StationId', 'Lon','Lat', 'Elev', 'UtmZone'])

        #print (pdf.head())

        mt_points = [Point(xy) for xy in zip(pdf.Lon, pdf.Lat)]
        # OR pdf['geometry'] = pdf.apply(lambda z: Point(z.Lon, z.Lat), axis=1)
        # if you want to df = df.drop(['Lon', 'Lat'], axis=1)
        #crs0 = {'init': 'epsg:4326'}  # WGS84
        crs0 = {'init': 'epsg:4283'}  # GDA94
        gdf = gpd.GeoDataFrame(pdf, crs=crs0, geometry=mt_points)

        if outshpfile is not None:
            gdf.to_file(outshpfile, driver='ESRI Shapefile')

        return gdf


    def plot_stations(self, savefile=None, showfig=True):
        """
        visualise the geopandas df of MT stations
        :return:
        """

        gdf=self.geopdf
        gdf.plot(figsize=(10, 6),  marker='o', color='blue', markersize=5)

        if savefile is not None:
            fig = plt.gcf()
            fig.savefig(savefile, dpi=300)

        if showfig is True:
            plt.show()

        return savefile

    def display_on_basemap(self):

        world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))

        logger.debug(world.shape)

        myax = world.plot(alpha=0.5)
        # myax.set_xlim([149,150])
        # myax.set_xlim([110, 155])
        # myax.set_ylim([-40, -10])

        myax.set_xlim((self.bound_box_dict['MinLon'],self.bound_box_dict['MaxLon']))
        myax.set_ylim((self.bound_box_dict['MinLat'],self.bound_box_dict['MaxLat']))

        myax2 = self.geopdf.plot(ax=myax, figsize=(10, 6), marker='o', color='blue', markersize=8)

        plt.show()

        return myax2

    def display_on_image(self):
        """
        display/overlay the MT properties on a background geo-referenced map image
        :return:
        """
        import examples.sandpit.plot_geotiff_imshow as plotegoimg

        myax = plotegoimg.plot_geotiff(geofile='tests/data/PM_Gravity.tif', show=False)

        margin= 0.02  # degree
        myax.set_xlim((self.bound_box_dict['MinLon'] -margin, self.bound_box_dict['MaxLon']+margin))
        myax.set_ylim((self.bound_box_dict['MinLat'] -margin, self.bound_box_dict['MaxLat'] + margin))

        myax2 = self.geopdf.plot(ax=myax, figsize=(10, 6), marker='o', color='r', markersize=10)

        plt.show()

        return myax2


    def create_csv_files_moved(self, dest_dir=None):
        """
        create csv moved/copied to shapefiles_creator.py
        :return:
        """
        if dest_dir is None:
            dest_dir = self.outputdir

        # summary csv file
        csvfname = os.path.join(dest_dir, "phase_tensor_tipper.csv")

        pt_dict = {}

        csv_header = ['station', 'freq', 'lon', 'lat', 'phi_min', 'phi_max', 'azimuth', 'skew', 'n_skew', 'elliptic',
                      'tip_mag_re', 'tip_mag_im', 'tip_ang_re', 'tip_ang_im']

        with open(csvfname, "wb") as csvf:
            writer = csv.writer(csvf)
            writer.writerow(csv_header)

        for freq in self.all_frequencies:
            ptlist = []
            for mt_obj in self.mt_obj_list:

                f_index_list = [ff for ff, f2 in enumerate(mt_obj.Z.freq)
                                if (f2 > freq * (1 - self.ptol)) and
                                (f2 < freq * (1 + self.ptol))]
                if len(f_index_list) > 1:
                    logger.warn("more than one fre found %s", f_index_list)

                if len(f_index_list) >= 1:
                    p_index = f_index_list[0]
                    # geographic coord lat long and elevation
                    # long, lat, elev = (mt_obj.lon, mt_obj.lat, 0)
                    station, lon, lat = (mt_obj.station, mt_obj.lon, mt_obj.lat)

                    pt_stat = [station, freq, lon, lat,
                               mt_obj.pt.phimin[0][p_index],
                               mt_obj.pt.phimax[0][p_index],
                               mt_obj.pt.azimuth[0][p_index],
                               mt_obj.pt.beta[0][p_index],
                               2 * mt_obj.pt.beta[0][p_index],
                               mt_obj.pt.ellipticity[0][p_index],  # FZ: get ellipticity begin here
                               mt_obj.Tipper.mag_real[p_index],
                               mt_obj.Tipper.mag_imag[p_index],
                               mt_obj.Tipper.angle_real[p_index],
                               mt_obj.Tipper.angle_imag[p_index]]

                    ptlist.append(pt_stat)
                else:
                    logger.warn('Freq %s NOT found for this station %s', freq, mt_obj.station)

            with open(csvfname, "ab") as csvf:  # summary csv for all freqs
                writer = csv.writer(csvf)
                writer.writerows(ptlist)

            csvfile2 = csvfname.replace('.csv', '_%sHz.csv' % str(freq))

            with open(csvfile2, "wb") as csvf:  # individual csvfile for each freq
                writer = csv.writer(csvf)

                writer.writerow(csv_header)
                writer.writerows(ptlist)

            pt_dict[freq] = ptlist

        return pt_dict


    def get_bounding_box(self, epsgcode=None):
        """

        :return: bounding box in given proj coord system
        """

        if epsgcode is None:
            new_gdf = self.geopdf
        else: # reproj
            new_gdf = self.geopdf.to_crs(epsg=epsgcode)


        tup = new_gdf.total_bounds

        bdict={"MinLon" : tup[0],
               "MinLat" : tup[1],
               "MaxLon" : tup[2],
               "MaxLat" : tup[3]
               }

        logger.debug(bdict)

        return bdict

    def show_prop(self):
        """
        show all properties
        :return:
        """
        print (len(self.all_periods), 'unique periods (s)', self.all_periods)
        print (len(self.all_frequencies), 'unique frequencies (Hz)', self.all_frequencies)

        print (self.bound_box_dict)

        self.plot_stations(savefile='/e/tmp/edi_collection_test.jpg')

        #self.display_on_basemap()

        self.display_on_image()

        #self.display_folium()

        return



    def create_phase_tensor_csv(self):
        """
        create phase tensor ellipse and tipper properties.
        :return:
        """
        return



if __name__ == "__main__":

    if len(sys.argv)<2:
        print ("USAGE: %s edi_dir OR edi_list " % sys.argv[0])
        sys.exit(1)
    else:
        argv1 = sys.argv[1]
        if os.path.isdir(argv1):
            edilist = glob.glob(argv1+'/*.edi')
            assert(len(edilist) > 0 ) # must has edi files
            obj=EdiCollection(edilist)

        elif os.path.isfile(argv1) and argv1.endswith('.edi'):
            obj=EdiCollection(sys.argv[1:])  # assume input is a list of EDI files
        else:
            pass

        # obj.show_prop()
        #
        # print(obj.get_bounding_box(epsgcode=28353))
        #
        # obj.create_mt_station_gdf(outshpfile='/e/tmp/edi_collection_test.shp')

        #########################################################################################
        # how to quick check the shape file created
        # fio info /e/tmp/edi_collection_test.shp
        #
        # {"count": 25, "crs": "+ellps=GRS80 +no_defs +proj=longlat", "name": "edi_collection_test",
        #  "driver": "ESRI Shapefile",
        #  "bounds": [136.77222222222224, -20.593694444444445, 136.93077777777776, -20.41086111111111],
        #  "crs_wkt": "GEOGCS[\"GDA94\",DATUM[\"Geocentric_Datum_of_Australia_1994\",
        #  SPHEROID[\"GRS_1980\",6378137,298.257222101]],PRIMEM[\"Greenwich\",0],
        #  UNIT[\"Degree\",0.017453292519943295]]",
        #  "schema": {"geometry": "Point",
        #             "properties": {"StationId": "str:80", "Lon": "float:24.15", "Lat": "float:24.15",
        #                  "Elev": "float:24.15", "UtmZone": "str:80"}}}
        #########################################################################################

        obj.create_csv_files_moved(dest_dir=sys.argv[2])

        myper = obj.get_periods_by_stats(percentage=10)

        print ("selected periods:")
        print(myper)