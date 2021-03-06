#!/usr/bin/python
# -*- coding: utf-8 -*-

"""

Sub programs for operating some Keithley instruments

author : Eoin O'Farrell
email : phyoec@nus.edu.sg
last edited : July 2013

Classes for:
	Keithley 6221
	
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
import math
import numpy as np
import threading
import Queue

######################################################
# At the moment each of the instruments we use is a
# seperate class
#####################################################



class k6221:
	def __init__(self, address, compliance = 0.1, analogFilter = True, autorange = True, setupOption = "SAV0", doSetup = False, mode = "Wave", wave = "SIN", frequency = 9.2, amplitude = 10e-8):
		# The setup option sets the setup that we use if doSetup is True 

		self.Address = address
		self.Visa = VisaSubs.InitializeGPIB(address,0,term_chars = "\\n")
		# Other 6430 properties
		self.Compliance = compliance
		self.AnalogFilter = analogFilter
		self.AutoRange = autorange
		self.CurrentRange = currentRange
		self.Mode = mode
		self.Wave = wave
		self.DoSetup = doSetup
		self.SetupOption = SetupOption
		self.Output = False
		self.Frequency = frequency
		self.Amplitude = amplitude

		if doSetup:
			self.Visa.write("*RST")
			self.Visa.write("".join(("SYST:POS ",setupOption)))


	######################################
	# Initialization i.e. writing a load of SCPI
	#######################################

	def Initialize(self):
		
		# Assume that the source is in Sine mode and that there is no
		# offset
		# Determine if the output is on or off
		Reply = self.Visa.ask("OUTP:STAT?")
		self.Output = bool(Reply)
		time.sleep(.1)

		# if the output is on we now determine the parameters
		# amplitude, frequency, compliance ...
		if self.Output:
			Reply = self.Visa.ask("SOUR:CURR:COMP?")
			self.Compliance = float(Reply)
			Reply = self.Visa.ask("SOUR:CURR:FILT?")
			self.AnalogFilter = bool(Reply)
			Reply = self.Visa.ask("SOUR:CURR:RANG:AUTO?")
			self.AutoRange = bool(Reply)
			if not self.AutoRange:
				Reply = self.Visa.ask("SOUR:CURR:RANG?")
				self.CurrentRange = float(Reply)


		
		self.Visa.write("".join((":SOUR:FUNC:MODE ",self.Source)))
		# Configure the auto zero (reference)
		self.Visa.write(":SYST:AZER:STAT ON")
		self.Visa.write(":SYST:AZER:CACH:STAT 1")
		self.Visa.write(":SYST:AZER:CACH:RES")

		# Disable concurrent mode, measure I and V (not R)
		self.Visa.write(":SENS:FUNC:CONC 1")	
		if self.Source == "VOLT":
			self.Sense = "CURR"
		elif self.Source == "CURR":
			self.Sense = "VOLT"

		self.Visa.write("".join((":SENS:FUNC:ON ","\"%s\"," % self.Source,"\"%s\"" % self.Sense)))
		self.Visa.write("".join((":FORM:ELEM ","%s," % self.Source,"%s" % self.Sense)))
		self.Visa.write("".join((":SENS:",self.Sense,":RANG:AUTO 0")))
		
		# Set the complicance
		if not SkipCompliance:
			self.Visa.write("".join((":SENS:",self.Sense,":RANG 105e-9")))
			self.Visa.write("".join((":SENS:",self.Sense,":PROT:LEV %.3e" % self.Compliance)))

#		# Set some filters
		self.Visa.write("".join((":SENS:",self.Sense,":NPLC %.2f" % self.Integration)))
		if not SkipMath:
			self.Visa.write(":SENS:AVER:REP:COUN %d" % self.Repetition)
			self.Visa.write(":SENS:MED:RANK %d" % self.Median)
		
		self.Visa.write(":SOUR:DEL %.4f" % self.Delay)
		self.Visa.write(":TRIG:DEL %.4f" % self.Trigger)
		
		pass
	
	###########################################
	# Set the range and compliance
	#######################################
	
	def SetRangeCompliance(self, Range = 105, Compliance = 105):

		self.Compliance = Compliance
		self.Visa.write("".join((":SENS:",self.Sense,":PROT:LEV %.3e" % self.Compliance)))
		
		if Range:
			self.Visa.write("".join((":SENS:",self.Sense,":RANG ","%.2e" % Range)))
		else:
			self.Visa.write("".join((":SENS:",self.Sense,":RANG:AUTO 1")))
		
		pass

	##################################################
	# Read data
	################################################

	def ReadWave(self):
		Reply = self.Visa.ask("SOUR:WAVE:FREQ?")
		self.Frequency = float(Reply)
		Reply = self.Visa.ask("SOUR:WAVE:AMPL?")
		self.Amplitude = float(Reply)
		pass
	

	##################################################
	# Set source
	##################################################

	def SetWave(self,Amp,Freq):
		self.Visa.write("SOUR:WAVE:CURR %.4e" % Amp)
		self.Visa.write("SOUR:WAVE:FREQ %.4e" % Amp)		
		pass

	#################################################
	# Switch the output
	###############################################

	def SwitchOutput(self):
		self.Output = not self.Output		
		self.Visa.write("".join((":OUTP:STAT ","%d" % self.Output)))
		pass

	#################################################
	# Switch the wave
	###############################################

	def SwitchWave(self):
		self.Output = not self.Output
		if self.Output:
			self.Visa.write("SOUR:WAVE:ARM")
			self.Visa.write("SOUR:WAVE:INIT")
		else:
			self.Visa.write("SOUR:WAVE:ABOR")
		pass

	######################################################
	# Manual sweep, this sweep will be run as a separate process
	# so it doesn't block the program
	##################################################

	def RunSweep(self,Start,Stop,Step,Wait,Mode = "linear",**kwargs):
		#self.Visa.write("".join((":SOUR:",self.Source,":MODE FIX")))
		
		Targets = [Start, Stop]
		
		for kw in kwargs.keys():
			if kw == "mid":
				Mid = kwargs[kw]
				for i in Mid:
					Targets.insert(len(Targets)-1,i)

		Voltage = [Start]
		
		for i in range(1,len(Targets)):
			Points = int(1+abs(Targets[i]-Targets[i-1])/Step)
			if Mode == "linear":
				Voltage = np.hstack([Voltage,np.linspace(Targets[i-1],Targets[i],num = Points)[1:Points]])
			if Mode == "log":
				Voltage = np.hstack([Voltage,np.linspace(Targets[i-1],Targets[i],num = Points)[1:Points]])

		

#		self.Visa.write("".join((":SOUR:",self.Source," %.4e" % Voltage[0])))
		
		return Voltage


	###################################################
	# Print a description string 
	################################################
	
	def Description(self):
		DescriptionString = "Keithley6221"
		for item in vars(self).items():
			if item[0] == "Frequency" or item[0] == "Amplitude" or item[0] == "Address":
				DescriptionString = ", ".join((DescriptionString,"%s = %.3f" % item))


		DescriptionString = "".join((DescriptionString,"\n"))
		return DescriptionString

	############################################
	######### Ramp the source to a final value
	#########################################
	
	def Ramp(self,Finish):
		if self.Output:
			self.ReadData()
		VStart = self.Data[0]
		N = max(100,int(abs(Finish-VStart)/0.1))
		VSweep = np.linspace(VStart,Finish,num=N+1)

		if not self.Output:
			self.SwitchOutput()

		for i in range(len(VSweep)):
			self.SetSource(VSweep[i])
			time.sleep(0.05)

		self.ReadData()
		return

