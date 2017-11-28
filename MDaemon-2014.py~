#!/usr/bin/python
# -*- coding: utf-8 -*-

"""

Sub programs for operation of Oxford Mercury iPS

author : Eoin O'Farrell
email : phyoec@nus.edu.sg
last edited :  Feb 2014


	The daemon listens for commands to change the field etc
	The daemon broadcasts the Field and a status message
	The daemon is assigned to port 18861
	The status messages are as follows:
	0 = Idle (this includes holding at set)
	1 = Going to set/Busy also includes procedures
	carried out after reaching the set e.g. putting the magnet into persistent mode
	2 = Sweeping as part of a job

	By definition the magnet is in persistent mode if the switch heater is off
	including if the magnet is at zero and the source is at zero

"""

import SocketUtils as SocketUtils
import logging
import visa as visa
import VisaSubs as VisaSubs
import string as string
import re as re
import time
import numpy as np
import asyncore
from datetime import datetime

class MControl():

	# Initialization call, initialize visas for the Mercury IPS and perform some startup
	# queries on the instrument
	# Server, server always runs at 18861
	# Important parameters
	# Field
	# Heater
	# AToB (amps to tesla)
	# Lock - Lock the deamon from performing actions, typically if the heater has just been
	# switched
	# The target current either as part of a sweep or going to a fixed value
	# Mode: Sweep or Set (including set to zero)
	
	def __init__(self):
		# Connect visa to the magnet
		self.Visa = VisaSubs.InitializeSerial("ASRL8", term_chars = "\\n")
		# Open the socket
		address = ('localhost',18861)
		self.Server = SocketUtils.SockServer(address)
		# Define some important parameters for the magnet
		self.Field = 0.0
		self.Current = 0.0
		self.Heater = 0
		self.PersistentCurrent = 0.0
		self.AToB = 0.0
		
		self.Lock = False
		self.LockTime = 0.0
		self.DelayedAction = False

		self.TargetCurrent = 0.0
		self.TargetSweep = 0.0
		self.TargetRate = 2.2
		self.MaxRate = 2.2
		self.CurrentLimit = 0.0
		self.TargetHeater = False

		self.SweepNow = False
		self.Busy = False
		self.Mode = 0 # 0 = Set mode, 1 = Sweep mode
		return

	#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
	# COMMUNICATION PROGRAMS
	#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

	############################################
	# Function to read one of the numeric signals
	###########################################
	
	def MagnetReadNumeric(self, Command):
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
	
	def MagnetReadField(self):
		# Form the query string (Now only for GRPZ)
		if self.Heater:
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
		if not self.Heater:
			self.PersistentCurrent = Answer
			Answer = Answer / self.AToB
		else:
			self.Current = Answer * self.AToB
		
		self.Field = Answer
		return

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
		elif Answer == "OFF":
			Valid = 0
			self.Heater = False
		else:
			Valid = -1

		return Valid

	##################################################
	# Turn the switch heater ON (1) or OFF (0)
	####################################################
	
	def MagnetSetHeater(self, State):
		
		HeaterBefore = self.Heater
		if State == 1:
			Reply = self.Visa.ask("SET:DEV:GRPZ:PSU:SIG:SWHT:ON")
		elif State == 0:
			Reply = self.Visa.ask("SET:DEV:GRPZ:PSU:SIG:SWHT:OFF")
		else:
			print "Error cannot set switch heater\n"
			
		Answer = string.rsplit(Reply,":",1)[1]
		if Answer == "VALID":
			Valid = 1
		elif Answer == "INVALID":
			Valid = 0
		self.MagnetReadHeater()
		if self.Heater != HeaterBefore:
			print "Heater switched ... locking for 2 minutes..."
			self.Lock = True
			self.LockTime = datetime.now()
			
		return Valid

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
		
		self.MagnetReadHeater()
		SourceCurrent = self.MagnetReadNumeric("CURR")
		PersistCurrent = self.MagnetReadNumeric("PCUR")

		if self.Heater == 1:
			Switchable = True
		elif self.Heater == 0 and abs(SourceCurrent - PersistCurrent) <= 0.05:
			Switchable = True
		elif self.Heater == 0 and abs(SourceCurrent - PersistCurrent) >= 0.05:
			Switchable = False

		Action = self.MagnetReadAction()
		if Action == "RTOZ" or Action == "RTOS":
			Switchable = 0
	
		return Switchable

	##########################################################
	# On start get parameters
	##########################################################

	def MagnetOnStartUp(self):

		self.MagnetReadHeater()
		self.AToB = self.MagnetReadConfNumeric("ATOB")
		self.MagnetReadField()
		self.CurrentLimit = self.MagnetReadConfNumeric("CLIM")
		self.TargetCurrent = self.Field * self.AToB

		if self.Heater:
			HeaterString = "ON"
		else:
			HeaterString = "OFF"

		print "Connected to magnet... Heater is %s, Field is %.3f, Magnet conversion = %.3f A/T, Maximum current = %.3f" % (HeaterString, self.Field, self.AToB, self.CurrentLimit)

		return

	##########################################################
	# Set the leads current, ignore the switch heater state, busy etc
	##########################################################
	
	def SourceGoSet(self,NewSet,Rate):

		if abs(NewSet) <= self.CurrentLimit:
			CSet = NewSet
		else:
			CSet = np.copysign(self.CurrentLimit,NewSet)
					
		## Accepted keyword arguments are rate and sweep
		self.MagnetSetNumeric("CSET",CSet)
		# If a rate is defined set it


		if Rate >= self.MaxRate:
			Rate = self.MaxRate
		self.MagnetSetNumeric("RCST", Rate)

		SetRate = self.MagnetReadNumeric("RCST")
		
		self.MagnetSetAction("RTOS")
		self.Busy = True
		print "Ramping source to %.4f A at %.4f A/m\n" % (CSet,SetRate)

		return		

	
	def UpdateStatus(self):
		
		if self.SweepNow:
			Status = 2
		elif self.Busy:
			# Going to a set point
			Status = 1
		else:
			# Idle
			Status = 0
			
		return Status

	# Interpret a message from the socket
	def ReadMsg(self,Msg):
		Msg = Msg.split(" ")
		GotAction = False
		if Msg[0] == "SET":
			try:
				NewTarget = float(Msg[1])
				FinalHeater = int(Msg[2])
				self.TargetHeater = bool(FinalHeater)
				NewTargetI = NewTarget * self.AToB
				if abs(self.TargetCurrent-NewTargetI) > 0.05:
					# The target is new
					GotAction = True
					self.Mode = 0
					self.TargetCurrent = NewTargetI
					self.TargetRate = self.MaxRate
					print "Got new set point from socket %.2f T" % self.TargetCurrent/self.AToB
			
			except:
				pass
		if Msg[0] == "SWP":
			
			
			try:
				NewTarget = float(Msg[1])
				SweepTarget = float(Msg[2])
				SweepRate = float(Msg[3])
				FinalHeater = int(Msg[4])
				self.TargetHeater = bool(FinalHeater)
				NewTargetI = NewTarget * self.AToB
				SweepTargetI = SweepTarget * self.AToB
				if (abs(self.TargetCurrent-SweepTarget) > 0.05) and (abs(self.TargetSweep-SweepTarget) > 0.05):
					GotAction = True
					self.Mode = 1
					self.TargetCurrent = NewTargetI
					self.TargetSweep = SweepTargetI
					self.TargetRate = SweepRate
					print "Got new sweep point from socket from %.2f to " % (self.TargetCurrent/self.AToB,self.TargetSweep/self.AToB,self.TargetRate)
			
			except:
				pass
			
			if self.Busy and GotAction:
				print "Warning... Busy, but got action request... Executing new action"

		return GotAction

if __name__ == '__main__':

	# Initialize a daemon
	control = MControl()
	control.MagnetOnStartUp()
	HeaterBusy = False
	
	while 1:
		
		# Read the field and update status
		control.MagnetReadField()
		StatusMsg = control.UpdateStatus()
		# Push the reading to clients
		for j in control.Server.handlers:
			j.to_send = ",%.5f %d" % (control.Field, StatusMsg)
			SocketMsg = j.received_data
			if SocketMsg and SocketMsg != "-":
				GotAction = control.ReadMsg(SocketMsg)
		asyncore.loop(count=1,timeout=0.001)
		if not control.Server.handlers:
			GotAction = False
		
		# Now we should do stuff depending on the socket and what we 
		# were doing before reading the socket
		# In order of precedence
		# 1. We are locked, waiting for the switch heater -> delay any actions
		# 2. We got a new action
		# 3. We are busy
		# 4. No new action, not busy... just chillin'!

		if control.Lock:
			# Check if we can release the lock
			Wait = datetime.now() - control.LockTime
			if Wait.seconds >= 120.0:
				# Unlock
				control.Lock = False
				print "Unlocking..."
			if GotAction:
				# If there was an action, set a flag
				control.DelayedAction = True
		
		if control.DelayedAction or GotAction:
			control.Busy = True

		if control.Busy and not control.Lock:
			# Now there are a lot of possible scenarios that need to be handled
			# 1. The heater is off  => set the source to the persistent current so it
			# can be switched on
			if not control.Heater and not HeaterBusy:
				if (control.MagnetReadAction() != "RTOS"):
					# Set the source to the persistent current
					control.SourceGoSet(control.PersistentCurrent,control.MaxRate)
				if control.MagnetCheckSwitchable:
					# If the magnet is switchable switch it
					control.MagnetSetHeater(1)
			# The heater is on

			elif control.Mode == 0 and not HeaterBusy:
				# We are in constant set mode
				if abs(control.Current - control.TargetCurrent) > abs(control.TargetCurrent) * 0.005:
					# We are not at the target
					if (control.MagnetReadAction() != "RTOS"):
						# We are not ramping, so ramp
						control.SourceGoSet(control.TargetCurrent,control.MaxRate)
				else:
					# We are at the target
					control.MagnetSetAction("HOLD")
					if control.TargetHeater:
						# Heater should be left on so we are done!
						control.Busy = False
						print "Task completed!\n"
					else:
						HeaterBusy = True

			elif control.Mode == 1 and not HeaterBusy:
				# We are in sweep mode
				if control.SweepNow:
					# We are now sweeping, check if the sweep is finished
					if abs(control.Current - control.TargetSweep) < abs(control.TargetSweep) * 0.005:
						# We are at the sweep target
						control.SweepNow = False
						control.MagnetSetAction("HOLD")
						if control.TargetHeater:
							# Heater should be left on so we are done!
							control.Busy = False
							print "Task completed!\n"
						else:
							HeaterBusy = True
				else:
					# We are not sweeping yet
					if abs(control.Current - control.TargetCurrent) > abs(control.TargetCurrent) * 0.005:
						# We are not at the initial target
						if (control.MagnetReadAction() != "RTOS"):
							# We are not ramping, so ramp
							control.SourceGoSet(control.TargetCurrent,control.MaxRate)
					else:
						# We are at the initial target so start the sweep
						control.MagnetSetAction("HOLD")
						control.SourceGoSet(control.TargetSweep,control.SweepRate)
						self.SweepNow = True

			elif HeaterBusy:
				# The sweep is done but the heater should be switched off
				if control.MagnetCheckSwitchable() and control.Heater:
					# Switch the heater off
					control.MagnetSetHeater(0)
				elif not control.Heater:
					# Ramp the source to zero
					control.SourceGoSet(0.0,control.MaxRate)
					HeaterBusy = False
					control.Busy = False
					print "Task completed!"

		time.sleep(0.4)


