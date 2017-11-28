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

import rpyc
import visa as visa
import VisaSubs as VisaSubs
import string as string
import re as re
from collections import namedtuple
import time
import numpy as np

######################################################
# At the moment each of the instruments we use is a
# seperate class
#####################################################



class SrsLia:
	def __init__(self,address):
		self.Address = address
		self.Visa = VisaSubs.InitializeGPIB(address,0,term_chars = "\\n")
		# Other LIA properties
		self.Excitation = []
		self.Frequency = []
		self.Harmonic = []
		self.InternalSource = []
		self.Sensitivity = []
		self.Phase = []
		self.Tau = []
		self.Expand = []
		self.Offset = []

	################################################
	# Read one of the numeric parameters
	###############################################

	def ReadNumeric(self,command):
		Reply = self.Visa.ask("".join((command,"?")))
		Answer = float(Reply)
		return Answer

	##################################################
	# Read data (X, Y)
	################################################

	def ReadData(self):
		Reply = self.Visa.ask("SNAP?1,2,3,4")
		self.Data = [float(i) for i in Reply.split(",")]
		pass

	##################################################
	# Initialization for the LIA consists of reading the measurement
	# parameters
	##################################################

	def Initialize(self):
		self.Excitation = self.ReadNumeric("SLVL")
		self.Frequency = self.ReadNumeric("FREQ")
		self.Harmonic = self.ReadNumeric("HARM")
		self.Sensitivity = self.ReadNumeric("SENS")
		self.Phase = self.ReadNumeric("PHAS")
		self.Tau = self.ReadNumeric("OFLT")
		self.InternalSource = self.ReadNumeric("FMOD")
		self.Expand = np.empty(2)
		self.Offset = np.empty(2)
		self.ReadOffset()
		pass

	##################################################
	# Read the offsets
	##################################################

	def ReadOffset(self,**kwargs):
		
		# set the offsets to zero
		if "auto" in kwargs.keys():
			self.Visa.write("OEXP 1,0,0")
			self.Visa.write("OEXP 2,0,0")
			time.sleep(1)

			# auto set the offsets
			self.Visa.write("AOFF 1")
			self.Visa.write("AOFF 2")

		# Read the offsets
		for i in range(2):
			Reply = self.Visa.ask("".join(("OEXP? ","%d" % (i+1))))
			Reply = Reply.split(",")
			self.Offset[i] = float(Reply[0])
			self.Expand[i] = float(Reply[1])

		if "auto" in kwargs.keys():
			self.Visa.write("".join(("OEXP 1,","%.2f," % self.Offset[0],"%d" % kwargs["auto"])))
			self.Visa.write("".join(("OEXP 2,","%.2f," % self.Offset[1],"%d" % kwargs["auto"])))
			self.Expand[0] = kwargs["auto"]
			self.Expand[1] = kwargs["auto"]

		pass


	###################################################
	# Print a description string 
	################################################
	


	def Description(self):
		DescriptionString = "SrsLia"
		for item in vars(self).items():
			if item[0] == "Tau" or item[0] == "Excitation" or item[0] == "Frequency" or item[0] == "Harmonic" or item[0] == "Address" or item[0] == "Phase" or item[0] == "Sensitivity" or item[0] == "InternalSource":
				DescriptionString = ", ".join((DescriptionString,"%s = %.3f" % item))
			#elif item[0] == "Expand" or item[0] == "Offset":
			#	DescriptionString = ", ".join((DescriptionString,"%s = %.3f, %.3f" % item))


		DescriptionString = "".join((DescriptionString,"\n"))
		return DescriptionString



