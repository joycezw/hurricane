#!/usr/bin/python 

#
# User Interface for Hurricane Detection
#   
#   use PyGTK and Glade (glode-3) 
#
#                               by lemin (Jake Lee)
#


import sys
import os
import globDisp 
import gridtools as gdtool 
import PyML as ml
from PyML.classifiers.svm import loadSVM
try:
    import pygtk
    pygtk.require('2.0')
except:
    pass
try:
    import gtk, gobject, cairo
    import gtk.glade
except:
    print "failed to import gtk libraries!"
    sys.exit(1)
from matplotlib.backends.backend_gtkagg import FigureCanvasGTK
from matplotlib.backends.backend_gtkagg import NavigationToolbar2GTKAgg as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.widgets import SpanSelector
import pdb
import tempfile
import pickle
import shelve
import time
import numpy as np

class HurricaneUI:
    
    def __init__(self):
        gladefile = "HurricaneUI.glade"
        builder = gtk.Builder()
        builder.add_from_file(gladefile)
        self.window = builder.get_object("mainWindow")
        builder.connect_signals(self)

        self.figure = Figure(figsize=(10,10), dpi=75)
        self.axis = self.figure.add_subplot(111)

        self.lat = 50
        self.lon = -100
        self.globe= globDisp.GlobeMap(self.axis, self.lat, self.lon)

        self.canvas = FigureCanvasGTK(self.figure)  
        self.canvas.show()
        self.canvas.set_size_request(500,500)

        self.globeview = builder.get_object("map")
        self.globeview.pack_start(self.canvas, True, True)

        self.navToolbar = NavigationToolbar(self.canvas, self.globeview)
        self.navToolbar.lastDir = '/var/tmp'
        self.globeview.pack_start(self.navToolbar)
        self.navToolbar.show()

        self.gridcombo = builder.get_object("gridsize")
        cell=gtk.CellRendererText()
        self.gridcombo.pack_start(cell,True)
        self.gridcombo.add_attribute(cell, 'text', 0)
        #self.gridcombo.set_active(2)

        # read menu configuration  
        self.gridopt = builder.get_object("gridopt").get_active()
        self.chkDetected = builder.get_object("detectedopt")
        self.detectedopt = self.chkDetected.get_active()
        self.chkHurricane = builder.get_object("hurricaneopt")
        self.hurricaneopt = self.chkHurricane.get_active()
        model = builder.get_object("liststore1")
        index = self.gridcombo.get_active()
        self.gridsize = model[index][0]
        radio = [ r for r in builder.get_object("classifieropt1").get_group() if r.get_active() ][0]
        self.sClassifier = radio.get_label()
        self.start = builder.get_object("startdate")
        self.end = builder.get_object("enddate")

        self.chkUndersample = builder.get_object("undersample")
        self.chkGenKey = builder.get_object("genKey")

        # disable unimplemented classifier selection
        builder.get_object("classifieropt2").set_sensitive(False)
        builder.get_object("classifieropt3").set_sensitive(False)
        builder.get_object("classifieropt4").set_sensitive(False)

        self.btnStore =  builder.get_object("store")
        self.datapath = 'GFSdat'
        self.trackpath = 'tracks'
        builder.get_object("btnDatapath").set_current_folder(self.datapath)
        builder.get_object("btnTrackpath").set_current_folder(self.trackpath)
        self.btnDetect =  builder.get_object("detect")

        # current operation status
        self.stormlocs = None
        self.detected = None
        self.clssfr = None

        # for test drawing functions
        if os.path.exists('demo.detected'):
            with open('demo.detected','r') as f:
                self.detected = pickle.load(f)
                self.stormlocs = pickle.load(f)
                self.chkHurricane.set_label(str(self.stormlocs.shape[0])+" Hurricanes")
                self.chkDetected.set_label(str(self.detected.shape[0])+" Detected")

        self.setDisabledBtns()

        # draw Globe
        self.drawGlobe()


    def setDisabledBtns(self):
        self.chkDetected.set_sensitive(self.detected!=None)
        self.chkHurricane.set_sensitive(self.stormlocs!=None)
        self.btnStore.set_sensitive(self.clssfr!=None)
        self.btnDetect.set_sensitive(self.clssfr!=None)
    
    def drawGlobe(self):
        self.globe.drawGlobe(self.gridsize, self.gridopt)
        if self.hurricaneopt : self.globe.drawHurricanes(self.stormlocs)
        if self.detectedopt : self.globe.fillGrids(self.detected)
        
    def main(self):
        self.window.show_all()
        gtk.main()

    def redraw(self):
        self.axis.cla()
        self.drawGlobe()
        self.canvas.draw_idle()

    def gtk_main_quit(self,widget):
        gtk.main_quit()
 

    ###############################################################################
    #
    #  utility functions (dialogs)
    #
    def getFilenameToRead(self, stitle, save=False, filter='all'):
        chooser = gtk.FileChooserDialog(title=stitle, parent=self.window,
                                        action=gtk.FILE_CHOOSER_ACTION_OPEN if not save else gtk.FILE_CHOOSER_ACTION_SAVE,
                                        buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,gtk.STOCK_OPEN if not save else gtk.STOCK_SAVE,gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)

        if filter=='mat' or filter=='mdat':
            filter = gtk.FileFilter()
            filter.set_name("Matrix files")
            filter.add_pattern("*.mat")
            chooser.add_filter(filter)
        if filter=='svm':
            filter = gtk.FileFilter()
            filter.set_name("SVM")
            filter.add_pattern("*.svm")
            chooser.add_filter(filter)
        if filter=='dat' or filter=='mdat':
            filter = gtk.FileFilter()
            filter.set_name("Data")
            filter.add_pattern("*.dat")
            chooser.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        chooser.add_filter(filter)

        chooser.set_current_folder(os.getcwd())

        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            filen = chooser.get_filename()
        else: filen = None
        chooser.destroy()
        return filen


    def showMessage(self,msg):
        md = gtk.MessageDialog(self.window, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO, 
                                gtk.BUTTONS_CLOSE, msg)
        md.run()
        md.destroy()


    ###############################################################################
    #
    #  read data files and convert into a training matrix input 
    #
    def on_btnTrackpath_current_folder_changed(self,widget):
        self.trackpath = widget.get_current_folder()

    def on_btnDatapath_current_folder_changed(self,widget):
        self.datapath = widget.get_current_folder()

    def on_createMat_clicked(self,widget):
        filen = self.getFilenameToRead("Save converted matrix for training", True, filter='mat')
        if filen is not None:
            start = self.start.get_text()        
            end = self.end.get_text()        
            bundersmpl = self.chkUndersample.get_active()
            bgenkey = self.chkGenKey.get_active()

            ### FIX ME: currently gridsize for classification is fixed 1 (no clustering of grids - 2x2)
            if os.path.exists(filen): os.unlink(filen) # createMat append existing file, so delete it if exist
            gdtool.createMat(self.datapath, self.trackpath, start, end, store=filen, 
                             undersample=bundersmpl, genkeyf=bgenkey)
            self.showMessage("Matrix has been stored to "+filen)


    ###############################################################################
    #
    #   train the selected classifier
    #
    def on_train_clicked(self, widget):
        # FOR NOW, only SVM is supported
        if self.sClassifier == "SVM":
            filen = self.getFilenameToRead("Open training data",filter='mat')
            if filen is not None:
                data = ml.VectorDataSet(filen,labelsColumn=0)
                self.clssfr = ml.SVM()
                self.clssfr.train(data)
                # train finished. need to update button status
                self.setDisabledBtns()
                self.showMessage("Training SVM is done.")
        else :
            self.showMessage("The classifier is not supported yet!")

    def on_classifieropt_toggled(self,widget, data=None):
        self.sClassifier = widget.get_label()


    ###############################################################################
    #
    #   Classify on test data
    #
    def on_detect_clicked(self, widget):
        if self.clssfr is not None:
            filen = self.getFilenameToRead("Open hurricane data", filter='mdat')
            if filen is not None:
                fname = os.path.basename(filen)
                key, ext = os.path.splitext(fname)
                if ext == '.dat':
                    key = key[1:] # take 'g' out

                    #testData = gdtool.createMat(self.datapath, self.trackpath, key, key)
                    #result = self.clssfr.test(ml.VectorDataSet(testData,labelsColumn=0))
                    tmpfn = 'f__tmpDetected__'
                    if os.path.exists(tmpfn): os.unlink(tmpfn)
                    # for DEMO, undersampled the normal data -- without undersampling there are too many candidates
                    gdtool.createMat(self.datapath, self.trackpath, key, key, store=tmpfn, undersample=True, genkeyf=True)
                    bneedDel = True
                else:
                    tmpfn = fname
                    bneedDel = False
                result = self.clssfr.test(ml.VectorDataSet(tmpfn,labelsColumn=0))

                gdkeyfilen = ''.join([tmpfn,'.keys'])
                with open(gdkeyfilen, 'r') as f:
                    gridkeys = pickle.load(f)
                    self.stormlocs = pickle.load(f)
                predicted = result.getPredictedLabels()
                predicted = np.array(map(float,predicted))
                self.detected = np.array(gridkeys)[predicted==1]
                if bneedDel: 
                    os.unlink(tmpfn)
                    os.unlink(gdkeyfilen)

                snstroms = str(self.stormlocs.shape[0])
                sndetected = str(self.detected.shape[0])
                self.chkHurricane.set_label(snstroms+" Hurricanes")
                self.chkDetected.set_label(sndetected+" Detected")

                self.showMessage(''.join([sndetected,"/",snstroms," grids are predicted to have hurricane."]))
                if False:
                    with open('demo.detected','w') as f:
                        pickle.dump(self.detected,f)
                        pickle.dump(self.stormlocs,f)

                # test data tested. update buttons
                self.setDisabledBtns()
                self.redraw()
        else:
            self.showMessage("There is no trained classifier!")


    ###############################################################################
    #
    #   load and store trained classifier
    #
    def on_load_clicked(self, widget):
        filen = self.getFilenameToRead("Load Classifier",filter='svm')
        if filen is not None:
            #db = shelve.open(filen)
            #if db.has_key('clssfr'):
            #    self.clssfr = db['clssfr'] 
            #else:
            #    self.showMessage("Cannot find a classifier!")
            #db.close()
            #with open(filen, 'wb') as f:
            #    self.clssfr = pickle.load(f)

            datfn = self.getFilenameToRead("Open Training Data",filter='mat')
            if datfn is not None:
                data = ml.VectorDataSet(datfn,labelsColumn=0)
                self.clssfr = loadSVM(filen,data) ## Why do I need to feed data ???
            
            #self.clssfr = loadSVM(filen,None) ## edited PyML for this

            # classifier has been loaded. need to update button status
            self.setDisabledBtns()
            self.showMessage("The classifier has been loaded!")

    def on_store_clicked(self, widget):
        if self.clssfr is not None:
            filen = self.getFilenameToRead("Store Classifier", True, filter='svm')
            if filen is not None:
                #with open(filen, 'wb') as f:
                #    pickle.dump(self.clssfr,f)
                #db = shelve.open(filen)
                #db['clssfr'] = self.clssfr
                #db.close()

                self.clssfr.save(filen)
                self.showMessage("The classifier has been saved!")
        else:
            self.showMessage("There is no trained classifier!")


    ###############################################################################
    #
    #   Display Globe 
    #
    def on_right_clicked(self,widget):
        self.lon += 10
        # rotate Globe

    def on_left_clicked(self,widget):
        self.lon -= 10
        # rotate Globe

    def gridsize_changed_cb(self, widget):
        model = widget.get_model()
        index = widget.get_active()
        if index > -1:
            self.gridsize = model[index][0]
        self.redraw()

    def on_gridopt_toggled(self, widget):
        self.gridopt = not self.gridopt
        self.redraw()
        
    def on_Hurricane_toggled(self, widget):
        self.hurricaneopt = not self.hurricaneopt
        self.redraw()

    def on_detected_toggled(self, widget):
        self.detectedopt = not self.detectedopt 
        self.redraw()


if __name__ == "__main__":
    ui = HurricaneUI()
    ui.main()

