#!/usr/bin/python
# -*- coding: utf-8 -*-

"""

Sub programs for operation of the PicoWatt and Leiden TCS to control temperature

author : Eoin O'Farrell
email : phyoec@nus.edu.sg
last edited : August 2013


	The daemon listens for commands to change the control loop or setpoint
	The daemon broadcasts the current temperature

ToDo:
	
	Listen
	Broadcast
	Initialize
	ReadPico
	CalcPID
	SetTCS

"""

import SocketUtils as SocketUtils
import logging
import visa as visa
import VisaSubs as VisaSubs
import string as string
import re as res
import time
import numpy as np
import asyncore
import PIDControl

class TControl():

	# Initialization call, initialize visas for the TCS, Picowatt and the
	# Server, server always runs at 18871
	def __init__(self):
		self.PicoVisa = visa.instrument("GPIB0::20::INSTR",delay=0.04)
		self.PicoVisa.write("HDR0")
		self.PicoVisa.write("ARN 1")
		self.PicoVisa.write("REM 1")
		self.TCSVisa = VisaSubs.InitializeSerial("ASRL5",idn="ID?",term_chars="\\n")
		address = ('localhost',18871)
		self.Server = SocketUtils.SockServer(address)
		self.ResThermometer = 1
		self.Temperature = 0.0
		self.PicoChannel = 0
		self.PicoRange = 0
		self.SetTemp = -1
		self.Status = -1
		self.TCSHeater = [0,0,0]
		self.TCSRange = [1,1,1]
		self.TCSCurrent = [0,0,0]
		self.ConstCurrent = False
		self.CurrentConst = 0
		self.DeltaTemp = 0
		self.MaxTemp = 5000
		self.MaxCurrent = 25000
		self.ErrorTemp = 10 # The acceptable error in temperature
		self.ErrorDeltaTemp = 10 # The acceptable stability
		self.Sweep = False
		self.SweepStart = 0
		self.SweepFinish = 0
		self.SweepRate = 0 # rate in mK/s
		self.SweepTime = 0
		self.SweepDirection = 1.0
		return


	def SetTCS(self,Source,Current):
		if Current < 0:
			Current = 0
		elif Current > self.MaxCurrent:
			Current = self.MaxCurrent
		# Current in microAmp
		# print Current
		Source = Source + 1
		command = " ".join(("SETDAC","%d" % Source,"0","%d" % Current))
		
		NEWPID = pid.update(control.Temperature)
		NEWPID = int(NEWPID)
		self.TCSVisa.ask(command)
		return

	def ReadPico(self):
		# Get the resistance of the current channel of the picowatt
		self.PicoVisa.write("ADC")
		time.sleep(0.4)
		Answer = self.PicoVisa.ask("RES ?")
		Answer = Answer.strip()
		try:
			self.ResThermometer = float(Answer)
		except:			
			self.ResThermometer = self.ResThermometer
			pass
		return

	def ReadPicoRange(self):
		Answer = self.PicoVisa.ask("RAN ?")
		Answer = Answer.strip()
		self.PicoRange = int(Answer)
		return

	def SetPicoChannel(self,Channel):
		self.PicoVisa.write("INP 0")
		Command = "".join(("MUX ","%d" % Channel))
		self.PicoVisa.write(Command)
		time.sleep(3)
		self.PicoVisa.write("INP 1")
		time.sleep(10)
		return

	def ReadTCS(self):
		Answer = self.TCSVisa.ask("STATUS?")
		Reply = Answer.split("\t")[1]
		Reply = Reply.split(",")
		Range = Reply[1::4]
		Current = Reply[2::4]
		Heaters = Reply[3::4]
		TMP = [1,10,100,1000]
		for i in range(3):
			self.TCSHeater[i] = int(Heaters[i])
		for i in range(3):
			self.TCSCurrent[i] = int(Current[i])*TMP[int(Range[i])-1]
		return

	def CalcTemperature(self,Calibration,factor=0):
		logR = np.log10(self.ResThermometer)-factor
		RPoly = np.ones((len(Calibration),))
		OldT = self.Temperature
		for i in range(1,len(RPoly)):
			RPoly[i] = logR * RPoly[i-1]
		self.Temperature = np.power(10,(np.sum(np.multiply(RPoly,Calibration))))
		self.DeltaTemp = abs(self.Temperature - OldT)
		return

	def UpdateStatus(self):
		# TDaemon has modes:
		# -2 = No set heater off
		# -1 = constant current
		# 0 = Going to set
		# 1 = At set point
		# 2 = Sweeping
		OldStatus = self.Status
		if self.ConstCurrent:
			self.Status = -1
		elif self.Sweep:
			self.Status = 2
		elif self.SetTemp <= 0:
			# There is no set point
			self.Status = -1
		elif (abs(self.SetTemp - self.Temperature) < self.ErrorTemp) and abs(self.DeltaTemp) <= self.ErrorDeltaTemp:
			# We are at the set point
			self.Status = 1
		else:
			# Going to Set
			self.Status = 0
		return

	# Interpret a message from the socket
	def ReadMsg(self,Msg):
		Msg = Msg.split(" ")
		GotSet = False
		if Msg[0] == "SET":
			try:
				NewSet = float(Msg[1])
				if abs(self.SetTemp-NewSet) > 5:
					if NewSet <= self.MaxTemp:
						self.SetTemp = NewSet
						GotSet = True
					else:
						self.SetTemp = self.MaxTemp
						GotSet = True
					print "Got set point from socket %.2f" % self.SetTemp
					self.ConstCurrent = False
					self.Sweep = False
			except:
				pass
		if Msg[0] == "SWP":
			try:
				self.SweepStart = float(Msg[1])
				self.SweepFinish = float(Msg[2])
				self.SweepRate = abs(float(Msg[3]))
				self.Sweep = True
				self.SweepTime = time.time()
				self.ConstCurrent = False
				print "Got temperature sweep from %.2f mK to %.2f mK at %.2f mK/s" % (self.SweepStart, self.SweepFinish, self.SweepRate)
				if self.SweepFinish >= self.SweepStart:
					self.SweepDirection = 1.0
				else:
					self.SweepDirection = -1.0
			except:
				pass
		if Msg[0] == "CST":
			try:
				self.CurrentConst = float(Msg[1])
				self.ConstCurrent = True
				self.Sweep = False
				print "Got constant current point from socket %.2f micro amps" % self.CurrentConst
			except:
				pass
		if Msg[0] == "T_ERROR":
			try:
				self.ErrorTemp = float(Msg[1])
			except:
				pass
		if Msg[0] == "DT_ERROR":
			try:
				self.ErrorDeltaTemp = float(Msg[1])
			except:
				pass
	
		return GotSet

	def TCSSwitchHeater(self,Heater):
		CommandVec = np.zeros((12,))
		CommandVec[2+Heater*4] = 1
		CommandStr = ""
		print "Heater %d Switched" % Heater
		for i in CommandVec:
			CommandStr = "".join((CommandStr, "%d," % i))
		CommandStr = CommandStr[:-1]
		self.TCSVisa.ask(" ".join(("SETUP",CommandStr)))
		return


##################### Calibrations
SO703 = [7318.782092,-13274.53584,10276.68481,-4398.202411,1123.561007,-171.3095557,14.43456504,-0.518534965]
SO914 = [5795.148097375,-11068.032226486,9072.821104899,-4133.466851312,1129.955799406,-185.318021359,16.881907269,-0.658939155]
MATS56 = [19.68045382,-20.19660902,10.13318296,-2.742724207,0.385556989,-0.022178276]

if __name__ == '__main__':

	# Initialize a PID controller

	pid = PIDControl.PID(P=10,I=1,D=0,Derivator=0,Integrator=0,Integrator_max=15000,Integrator_min=-2000)

	control = TControl()
	control.SetPicoChannel(3)

	# Main loop
	control.ReadTCS()

	while 1:
		
		# Read the picowatt and calculate the temperature
		control.ReadPico()
		control.CalcTemperature(SO703)
		# Push the reading to clients
		for j in control.Server.handlers:
			j.to_send = ",%.3f %d" % (control.Temperature, control.Status)
			SocketMsg = j.received_data
			if SocketMsg:
				GotSet = control.ReadMsg(SocketMsg)
				if GotSet:
					pid.setPoint(control.SetTemp)
		asyncore.loop(count=1,timeout=0.001)
		
		control.UpdateStatus()

		# Now we should do some PID stuff
		if control.Sweep:
			deltaTime = time.time() - control.SweepTime
			control.setTemp = deltaTime * control.SweepRate * control.SweepDirection + control.SweepStart
			pid.setPoint(control.setTemp)
			if (control.setTemp - control.SweepFinish)*control.SweepDirection >= 0:
				# Sweep has finished
				control.Sweep = False
			elif not control.Server.handlers:
				control.Sweep = False

		
		if control.Status >= 0:
			NEWPID = pid.update(control.Temperature)
			NEWPID = int(NEWPID)
			if NEWPID < 0:
				NEWPID = 0
			if NEWPID > control.MaxCurrent:
				NEWPID = control.MaxCurrent

		if control.Status == -1 and control.TCSHeater[2] == 1:
			# status is unset and the heater is on turn it off
			control.TCSSwitchHeater(2)
			control.ReadTCS()
		elif control.Status == -2:
			if control.TCSHeater[2] == 0:
			# the status is constant current --> Turn heater on to con
				control.TCSSwitchHeater(2)
			control.SetTCS(2,control.CurrentConst)
			control.ReadTCS()
		elif control.Status >= 0 and control.TCSHeater[2] == 0:
			# status is go to set and heater is off --> turn it on
			control.TCSSwitchHeater(2)
			control.ReadTCS()
		elif control.Status >= 0 and control.TCSHeater[2] == 1:
			control.SetTCS(2,NEWPID)
			control.TCSCurrent[2] = NEWPID

		time.sleep(0.4)

	control.TCSVisa.close()

