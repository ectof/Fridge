#!/usr/bin/python
# -*- coding: utf-8 -*-

"""

Sub programs for operation of the Oxford Mercury iPS

author : Eoin O'Farrell
email : phyoec@nus.edu.sg
last edited : July 2013

Explantion:

	The magnet is run from a service (an rPyC class)
	that is remote from the foreground
	measurement. The backgrounding is achieved through the rPyC module of
	python. Only certain functions are available (exposed) to the measurement,
	the others are effectively internal functions for the magnet.

	The exposed commands are indicated below, of the exposed commands
	exposed_MagnetGoToSet is run asynchronously i.e. so that the measurement can
	proceed while the magnet is sweeping. The other exposed commands are for
	measureing and should be run synchronously.

	The main program of the magnet just starts the server which will then
	be available to clients.

	The magnet runs listens on port 18661


Methods written:


	exposed_MagnetReadNumeric
	exposed_MagnetReadField
	MagnetReadConfNumeric
	MagnetSetNumeric
	MagnetSetHeater
	MagnetReadHeater
	MagnetReadAction
	MagnetSetAction
	MagnetCheckSwitchable
	MagnetGoCurrent
	exposed_MagnetGoToSet

ToDo:
	
	Make a magnet server using Qt and rcPy


"""

import rpyc
import visa as visa
import VisaSubs as VisaSubs
import string as string
import re as re
from collections import namedtuple
import time


class MagnetService(rpyc.Service):


	############################################
	# Initialization call for the class
	###########################################

	def __init__(self,info):
		#print info
		self.Visa = VisaSubs.InitializeSerial("ASRL8", term_chars = "\\n")
		self.Heater = []
		self.Persistent = False
		self.BConversion =  self.MagnetReadConfNumeric("ATOB")
		self.MagnetReadHeater()
	
	############################################
	# Function to read one of the numeric signals
	###########################################

	def exposed_MagnetReadNumeric(self, Command):
		# Form the query string (Now only for GRPZ)
		Query = "".join(("READ:DEV:GRPZ:PSU:SIG:",Command))
		Reply = self.Visa.ask(Query)
		# Find the useful part of the response
		Answer = string.rsplit(Reply,":",1)[1]
	
		# Some regex to get rid of the appended units
		Answer = re.split("[a-zA-Z]",Answer,1)[0]
		Answer = float(Answer)
	
		return Answer

	############################################
	# Function to read the field in Tesla specifically
	###########################################

	def exposed_MagnetReadField(self):
		# Form the query string (Now only for GRPZ)
		if not self.Persistent:
			Query = "READ:DEV:GRPZ:PSU:SIG:FLD"
		else:
			# For some reason the command PFLD doesn't work
			Query = "READ:DEV:GRPZ:PSU:SIG:PCUR"

		Reply = self.Visa.ask(Query)
		# Find the useful part of the response
		Answer = string.rsplit(Reply,":",1)[1]
		
		# Some regex to get rid of the appended units
		Answer = re.split("[a-zA-Z]",Answer,1)[0]
		Answer = float(Answer)
		if self.Persistent:
			Answer = Answer / self.BConversion

		return Answer

	#########################################
	# Read one of the numeric configs
	########################################

	def MagnetReadConfNumeric(self, Command):
		# Form the query string (Now only for GRPZ)
		Query = "".join(("READ:DEV:GRPZ:PSU:",Command))
		Reply = self.Visa.ask(Query)
		# Find the useful part of the response
		Answer = string.rsplit(Reply,":",1)[1]
		
		# Some regex to get rid of the appended units
		Answer = re.split("[a-zA-Z]",Answer,1)[0]
		Answer = float(Answer)

		return Answer

	################################################
	# Function to set one of the numeric signals
	#############################################

	def MagnetSetNumeric(self, Command, Value):
		# Form the query string (Now only for GRPZ)
		writeCmd = "SET:DEV:GRPZ:PSU:SIG:%s:%.4f" % (Command, float(Value))
		Reply = self.Visa.ask(writeCmd)

		Answer = string.rsplit(Reply,":",1)[1]
		if Answer == "VALID":
			Valid = 1
		elif Answer == "INVALID":
			Valid = 0
		else:
			Valid = -1

		return Valid

	#############################################################
	# Function to read the switch heater state returns boolean
	###########################################################

	def MagnetReadHeater(self):
		Reply = self.Visa.ask("READ:DEV:GRPZ:PSU:SIG:SWHT")
		Answer = string.rsplit(Reply,":",1)[1]
		if Answer == "ON":
			Valid = 1
			self.Heater = True
			self.Persistent = False
		elif Answer == "OFF":
			Valid = 0
			self.Heater = False
			self.Persistent = True
		else:
			Valid = -1

		return Valid

	##################################################
	# Turn the switch heater ON (1) or OFF (0)
	####################################################

	def MagnetSetHeater(self, State):
		
		HeaterBefore = self.MagnetReadHeater()
		if State == 1:
			Reply = self.Visa.ask("SET:DEV:GRPZ:PSU:SIG:SWHT:ON")	
		elif State == 0:
			Reply = self.Visa.ask("SET:DEV:GRPZ:PSU:SIG:SWHT:OFF")
		else:
			print "Error cannot set switch heater\n"

		Answer = string.rsplit(Reply,":",1)[1]
		if Answer == "VALID":
			Heater = 1
		elif Answer == "INVALID":
			Heater = 0
		else:
			Heater = -1

		HeaterAfter = self.MagnetReadHeater()	
		if HeaterAfter != HeaterBefore:
			print "Heater Switched! Waiting 2 min\n"
			time.sleep(120)
			print "Finished wait!\n"

		return Heater

	#######################################################
	# Read the current magnet action e.g. HOLD, RTOZ etc.
	##########################################################

	def MagnetReadAction(self):
		
		Reply = self.Visa.ask("READ:DEV:GRPZ:PSU:ACTN")
		Answer = string.rsplit(Reply,":",1)[1]
		return Answer

	########################################################
	# Set the action for the magnet
	######################################################

	def MagnetSetAction(self, Command):
		
		Reply = self.Visa.ask("".join(("SET:DEV:GRPZ:PSU:ACTN:",Command)))	

		Answer = string.rsplit(Reply,":",1)[1]
		if Answer == "VALID":
			Valid = 1
		elif Answer == "INVALID":
			Valid = 0
		else:
			Valid = -1

		return Valid

	##########################################################
	# Check if it is safe to switch the switch heater
	#######################################################

	def MagnetCheckSwitchable(self):
		
		Heater = self.MagnetReadHeater()
		SourceCurrent = self.exposed_MagnetReadNumeric("CURR")
		PersistCurrent = self.exposed_MagnetReadNumeric("PCUR")

		if Heater == 1:
			Switchable = 1
		elif Heater == 0 and abs(SourceCurrent - PersistCurrent) <= 0.1:
			Switchable = 1
		elif Heater == 0 and abs(SourceCurrent - PersistCurrent) >= 0.1:
			Switchable = 0

		Action = self.MagnetReadAction()
		if Action == "RTOZ" or Action == "RTOS":
			Switchable = 0
	
		return Heater, Switchable

	##########################################################
	# Set the leads current, ignore the switch heater state
	##########################################################

	def MagnetGoCurrent(self, CSet, **kwargs):
		## Accepted keyword arguments are rate and sweep
		self.MagnetSetNumeric("CSET",CSet)
		# If a rate is defined set it
		QueryRate = kwargs.get("rate",False)
		if QueryRate:
			self.MagnetSetNumeric("RCST", QueryRate)
		
		SetRate = self.exposed_MagnetReadNumeric("RCST")

		self.MagnetSetAction("RTOS")
		print "Ramping source to %.4f A at %.4f A/m\n" % (CSet,SetRate)
		QuerySweep = kwargs.get("sweep",False)
		if not QuerySweep:
			# Job is not a sweep so track the magnet until done and then hold
			while abs(self.exposed_MagnetReadNumeric("CURR")-CSet) >= 0.05:
				time.sleep(3)
			self.MagnetSetAction("HOLD")
		else:
			print "Sweep started, exiting!\n"

	##########################################################
	# Set the coil, and begin a sweep if required
	########################################################

	def exposed_MagnetGoToSet(self, BSet, FinishHeater, **kwargs):

		# FinishHeater = 0 or 1
		# Accepted kwargs are rate and sweep
		print "Go to set call received!\n"

		self.MagnetSetAction("HOLD")

		QueryRate = kwargs.get("rate",False)
		QuerySweep = kwargs.get("sweep",False)

		# Check if the magnet is persistent and the current in the coil
		MagnetState = self.MagnetCheckSwitchable()

		BConversion = self.MagnetReadConfNumeric("ATOB")
		ISet = BSet * BConversion

		if MagnetState[0] == 1:
			ICoil = self.exposed_MagnetReadNumeric("CURR")
		
		elif MagnetState[0] == 0:
			ICoil = self.exposed_MagnetReadNumeric("PCUR")

		#################################

		if abs(ICoil - ISet) <= 0.05 and FinishHeater == MagnetState[0]:
			# The current is correct and the SW heater is correct, done!
			Status = 1
		
		elif abs(ICoil - ISet) <= abs(ISet*0.001) and FinishHeater != MagnetState[0]:
			# The current is correct but the heater is not
			if MagnetState[1] == 1:
				# magnet is switchable, switch it and then wait 4 min!
				self.MagnetSetHeater(FinishHeater)
				Status = 1

			elif MagnetState[1] == 0:
				# magnet is not switchable, set the leads current and ramp to set
				self.MagnetGoCurrent(ICoil)
				# Check the state
				Switchable = self.MagnetCheckSwitchable()
				if Switchable[1] == 1:
					self.MagnetSetHeater(FinishHeater)
					Status = 1
				else:
					Status = -1

		elif abs(ICoil - ISet) > 0.05:
			# The current is not correct
			if MagnetState[0] == 1:
				# Heater is on, go to set
				self.MagnetGoCurrent(ISet,rate = QueryRate,sweep = QuerySweep)
				Status = 1

			elif MagnetState[0] == 0:
				# Heater is not on, recursive call to switch it on
				self.exposed_MagnetGoToSet(ICoil/BConversion,1) 
				self.MagnetGoCurrent(ISet,rate = QueryRate,Sweep = QuerySweep)
				Status = 1

			# if the final heater state is for the heater to be off, turn it off
		if FinishHeater == 0 and not QuerySweep:
			Switchable = self.MagnetCheckSwitchable()
			if Switchable[1] == 1:
				self.MagnetSetHeater(FinishHeater)
				Status = 1
				# Ramp the source down
				self.MagnetGoCurrent(0)
			else:
				Status = -1
			
			if BSet != 0.0:
				self.Persistent = True

		# Check if the magnet is already at the set
		return Status
		
	
	
	
if __name__ == "__main__":

	from rpyc.utils.server import ThreadedServer
    	t = ThreadedServer(MagnetService, port = 18861)
	t.start()

