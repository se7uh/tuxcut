# -*- coding: utf-8 -*- 

###########################################################################
## Python code generated with wxFormBuilder (version Nov  7 2017)
## http://www.wxformbuilder.org/
##
## PLEASE DO *NOT* EDIT THIS FILE!
###########################################################################

import wx
import wx.xrc
import wx.dataview

###########################################################################
## Class MainFrame
###########################################################################

class MainFrame ( wx.Frame ):
	
	def __init__( self, parent ):
		super().__init__(
			parent, 
			id=wx.ID_ANY,
			title="TuxCut",
			pos=wx.DefaultPosition,
			size=wx.Size(750, 400),
			style=wx.CAPTION | wx.CLOSE_BOX | wx.MINIMIZE_BOX | wx.RESIZE_BORDER
		)
		
		self.SetMinSize(wx.Size(750, 400))
		
		main_sizer = wx.BoxSizer(wx.VERTICAL)
		
		protection_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.cb_protection = wx.CheckBox(
			self,
			wx.ID_ANY,
			"Protect My Computer",
			wx.DefaultPosition,
			wx.DefaultSize
		)
		protection_sizer.Add(self.cb_protection, 0, wx.ALL, 5)
		main_sizer.Add(protection_sizer, 0, 0, 5)
		
		self.hosts_view = wx.dataview.DataViewListCtrl(
			self,
			wx.ID_ANY,
			wx.DefaultPosition,
			wx.Size(-1, -1),
			wx.dataview.DV_ROW_LINES | wx.DOUBLE_BORDER
		)
		self.hosts_view.SetFont(
			wx.Font(
				10,
				wx.FONTFAMILY_DEFAULT,
				wx.FONTSTYLE_NORMAL,
				wx.FONTWEIGHT_NORMAL,
				False
			)
		)
		
		main_sizer.Add(self.hosts_view, 1, wx.ALL | wx.EXPAND, 5)
		
		self.SetSizer(main_sizer)
		self.Layout()
		
		self.toolbar = self.CreateToolBar(0, wx.ID_ANY)
		self.toolbar.Realize()
		
		self.Centre(wx.BOTH)
		
		self.cb_protection.Bind(wx.EVT_CHECKBOX, self.toggle_protection)
	
	def __del__( self ):
		pass
	
	
	# Virtual event handlers, overide them in your derived class
	def toggle_protection( self, event ):
		event.Skip()
	

