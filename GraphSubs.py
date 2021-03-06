#!/usr/bin/python
# -*- coding: utf-8 -*-

"""

Sub programs for doing the measurements

author : Eoin O'Farrell
email : phyoec@nus.edu.sg
last edited : July 2013

Explantion:

	There are 3 variables in our instrument:
	1 Temperature
	2 Field
	3 Device parameter; e.g. Backgate V, Topgate V, Current, Angle (one day)

	Typically a measurement will fix two of these and vary the other.
	The controls for temperature and field are controlled by external
	services that can be called by the measurement. The measurement
	invokes a localhost for each of these services and can then
	access certain methods
	
	The generic ports for these are
	Magnet: 18861
	Temperature: 18871

	Data from these processes can also be accessed through named pipes

	Device parameters are so far controlled in situ in the measurement
	loop. This should probably also be changed to be consistent

ToDo:
	
	InitializeInstruments
	ScanInstruments
	InitializeDataFile
	WriteDataFile
	CloseDataFile
	GraphData

"""
import string as string
import re as re
import time
import multiprocessing
import numpy as np
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import sys
import os

def MakeGraph(conn):

	win = pg.GraphicsWindow(title = "test")
	win.resize(300,300)

	p1 = win.addPlot(title = "test")

	curve = p1.plot(pen = 'y')
	timer = QtCore.QTimer()

	CurveData = np.random.normal(size=(10,1000))

	def Update():
		global CurveData
		try:
			ConnData = conn.recv()
			ConnData = [float(i) for i in ConnData]
			CurveData = np.append(CurveData,ConnData)
			curve.setData(CurveData)
		except EOFError:
			print "Graph connection closed\n"
			timer.stop()
			QtGui.QApplication.quit()
			


		

	timer.timeout.connect(Update)
	timer.start(0)

	if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        	QtGui.QApplication.instance().exec_()
		

