# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Please edit this list and import only required elements
from __future__ import unicode_literals
import webnotes
from webnotes.utils import add_days, cint, cstr, flt, get_defaults, getdate
from webnotes.model.doc import addchild, make_autoname
from webnotes.model.utils import getlist
from webnotes.model.code import get_obj
from webnotes import msgprint, errprint
sql = webnotes.conn.sql
from controllers.stock import StockController

class DocType(StockController):
	def __init__(self, doc, doclist=[]):
		self.doc = doc
		self.doclist = doclist
		self.defaults = get_defaults()
		self.tname = 'Purchase Receipt Item'
		self.fname = 'purchase_receipt_details'
		self.count = 0

	def autoname(self):
		self.doc.name = make_autoname(self.doc.naming_series+'.#####')

	def get_default_schedule_date(self):
		get_obj(dt = 'Purchase Common').get_default_schedule_date(self)

	def validate_fiscal_year(self):
		get_obj(dt = 'Purchase Common').validate_fiscal_year(self.doc.fiscal_year,self.doc.posting_date,'Transaction Date')


	# Get Item Details
	def get_item_details(self, arg = ''):
		if arg:
			return get_obj(dt='Purchase Common').get_item_details(self,arg)
		else:
			import json
			obj = get_obj('Purchase Common')
			for doc in self.doclist:
				if doc.fields.get('item_code'):
					temp = {
						'item_code': doc.fields.get('item_code'),
						'warehouse': doc.fields.get('warehouse')
					}
					ret = obj.get_item_details(self, json.dumps(temp))
					for r in ret:
						if not doc.fields.get(r):
							doc.fields[r] = ret[r]


	# Get UOM Details
	def get_uom_details(self, arg = ''):
		return get_obj(dt='Purchase Common').get_uom_details(arg)

	def get_tc_details(self):
		return get_obj('Purchase Common').get_tc_details(self)


	# get available qty at warehouse
	def get_bin_details(self, arg = ''):
		return get_obj(dt='Purchase Common').get_bin_details(arg)

	# Pull Purchase Order
	def get_po_details(self):
		self.validate_prev_docname()
		get_obj('DocType Mapper', 'Purchase Order-Purchase Receipt').dt_map('Purchase Order', 'Purchase Receipt', self.doc.purchase_order_no, self.doc, self.doclist, "[['Purchase Order','Purchase Receipt'],['Purchase Order Item', 'Purchase Receipt Item'],['Purchase Taxes and Charges','Purchase Taxes and Charges']]")

	# validate if PO has been pulled twice
	def validate_prev_docname(self):
		for d in getlist(self.doclist, 'purchase_receipt_details'):
			if self.doc.purchase_order_no and d.prevdoc_docname and self.doc.purchase_order_no == d.prevdoc_docname:
				msgprint(cstr(self.doc.purchase_order_no) + " Purchase Order details have already been pulled. ")
				raise Exception

	def validate_accepted_rejected_qty(self):
		for d in getlist(self.doclist, "purchase_receipt_details"):

			# If Reject Qty than Rejected warehouse is mandatory
			if flt(d.rejected_qty) and (not self.doc.rejected_warehouse):
				msgprint("Rejected Warehouse is necessary if there are rejections.")
				raise Exception

			# Check Received Qty = Accepted Qty + Rejected Qty
			if ((flt(d.qty) + flt(d.rejected_qty)) != flt(d.received_qty)):

				msgprint("Sum of Accepted Qty and Rejected Qty must be equal to Received quantity. Error for Item: " + cstr(d.item_code))
				raise Exception


	def validate_challan_no(self):
		"Validate if same challan no exists for same supplier in a submitted purchase receipt"
		if self.doc.challan_no:
			exists = webnotes.conn.sql("""
			SELECT name FROM `tabPurchase Receipt`
			WHERE name!=%s AND supplier=%s AND challan_no=%s
		AND docstatus=1""", (self.doc.name, self.doc.supplier, self.doc.challan_no))
			if exists:
				webnotes.msgprint("Another Purchase Receipt using the same Challan No. already exists.\
			Please enter a valid Challan No.", raise_exception=1)


	# Check for Stopped status
	def check_for_stopped_status(self, pc_obj):
		check_list =[]
		for d in getlist(self.doclist, 'purchase_receipt_details'):
			if d.fields.has_key('prevdoc_docname') and d.prevdoc_docname and d.prevdoc_docname not in check_list:
				check_list.append(d.prevdoc_docname)
				pc_obj.check_for_stopped_status( d.prevdoc_doctype, d.prevdoc_docname)

	def po_required(self):
		"""check in manage account if purchase order required or not."""
		res = sql("select value from `tabSingles` where doctype = 'Global Defaults' and field = 'po_required'")
		if res and res[0][0]== 'Yes':
			 for d in getlist(self.doclist,'purchase_receipt_details'):
				 if not d.prevdoc_docname:
					 msgprint("Purchse Order No. required against item %s"%d.item_code)
					 raise Exception


	# validate
	def validate(self):
		self.po_required()
		self.validate_fiscal_year()
		webnotes.conn.set(self.doc, 'status', 'Draft')			 # set status as "Draft"
		self.validate_accepted_rejected_qty()
		self.validate_inspection()						 # Validate Inspection
		get_obj('Stock Ledger').validate_serial_no(self, 'purchase_receipt_details')
		self.validate_challan_no()
		
		pc_obj = get_obj(dt='Purchase Common')
		pc_obj.validate_for_items(self)
		pc_obj.validate_mandatory(self)
		pc_obj.validate_conversion_rate(self)
		pc_obj.get_prevdoc_date(self)
		pc_obj.validate_reference_value(self)
		# update item valuation rate
		pc_obj.update_item_valuation_rate(self)

		self.check_for_stopped_status(pc_obj)
		
		# get total in words
		dcc = super(DocType, self).get_company_currency(self.doc.company)
		self.doc.in_words = pc_obj.get_total_in_words(dcc, self.doc.grand_total)
		self.doc.in_words_import = pc_obj.get_total_in_words(self.doc.currency, self.doc.grand_total_import)

	def on_update(self):
		if self.doc.rejected_warehouse:
			for d in getlist(self.doclist,'purchase_receipt_details'):
				d.rejected_warehouse = self.doc.rejected_warehouse

		get_obj("Purchase Common").update_subcontracting_raw_materials(self)
		get_obj('Stock Ledger').scrub_serial_nos(self)
		self.scrub_rejected_serial_nos()

	def scrub_rejected_serial_nos(self):
		for d in getlist(self.doclist, 'purchase_receipt_details'):
			if d.rejected_serial_no:
				d.rejected_serial_no = d.rejected_serial_no.replace(',', '\n')
				d.save()

 # Update Stock
	def update_stock(self, is_submit):
		pc_obj = get_obj('Purchase Common')
		self.values = []
		for d in getlist(self.doclist, 'purchase_receipt_details'):
			# Check if is_stock_item == 'Yes'
			if sql("select is_stock_item from tabItem where name=%s", d.item_code)[0][0]=='Yes':
				ord_qty = 0
				pr_qty = flt(d.qty) * flt(d.conversion_factor)

				# Check If Prevdoc Doctype is Purchase Order
				if cstr(d.prevdoc_doctype) == 'Purchase Order':
					# get qty and pending_qty of prevdoc
					curr_ref_qty = pc_obj.get_qty( d.doctype, 'prevdoc_detail_docname', d.prevdoc_detail_docname, 'Purchase Order Item', 'Purchase Order - Purchase Receipt', self.doc.name)
					max_qty, qty, curr_qty = flt(curr_ref_qty.split('~~~')[1]), flt(curr_ref_qty.split('~~~')[0]), 0

					if flt(qty) + flt(pr_qty) > flt(max_qty):
						curr_qty = (flt(max_qty) - flt(qty)) * flt(d.conversion_factor)
					else:
						curr_qty = flt(pr_qty)

					ord_qty = -flt(curr_qty)
					# update order qty in bin
					bin = get_obj('Warehouse', d.warehouse).update_bin(0, 0, (is_submit and 1 or -1) * flt(ord_qty), 0, 0, d.item_code, self.doc.posting_date)

				# UPDATE actual qty to warehouse by pr_qty
				self.make_sl_entry(d, d.warehouse, flt(pr_qty), d.valuation_rate, is_submit)
				# UPDATE actual to rejected warehouse by rejected qty
				if flt(d.rejected_qty) > 0:
					self.make_sl_entry(d, self.doc.rejected_warehouse, flt(d.rejected_qty) * flt(d.conversion_factor), d.valuation_rate, is_submit, rejected = 1)

		self.bk_flush_supp_wh(is_submit)

		if self.values:
			get_obj('Stock Ledger', 'Stock Ledger').update_stock(self.values)


	# make Stock Entry
	def make_sl_entry(self, d, wh, qty, in_value, is_submit, rejected = 0):
		if rejected:
			serial_no = d.rejected_serial_no
		else:
			serial_no = d.serial_no

		self.values.append({
			'item_code'					: d.fields.has_key('item_code') and d.item_code or d.rm_item_code,
			'warehouse'					: wh,
			'transaction_date'			: getdate(self.doc.modified).strftime('%Y-%m-%d'),
			'posting_date'				: self.doc.posting_date,
			'posting_time'				: self.doc.posting_time,
			'voucher_type'				: 'Purchase Receipt',
			'voucher_no'				: self.doc.name,
			'voucher_detail_no'			: d.name,
			'actual_qty'				: qty,
			'stock_uom'					: d.stock_uom,
			'incoming_rate'				: in_value,
			'company'					: self.doc.company,
			'fiscal_year'				: self.doc.fiscal_year,
			'is_cancelled'				: (is_submit==1) and 'No' or 'Yes',
			'batch_no'					: d.batch_no,
			'serial_no'					: serial_no
			})


	def validate_inspection(self):
		for d in getlist(self.doclist, 'purchase_receipt_details'):		 #Enter inspection date for all items that require inspection
			ins_reqd = sql("select inspection_required from `tabItem` where name = %s", (d.item_code), as_dict = 1)
			ins_reqd = ins_reqd and ins_reqd[0]['inspection_required'] or 'No'
			if ins_reqd == 'Yes' and not d.qa_no:
				msgprint("Item: " + d.item_code + " requires QA Inspection. Please enter QA No or report to authorized person to create Quality Inspection")

	# Check for Stopped status
	def check_for_stopped_status(self, pc_obj):
		check_list =[]
		for d in getlist(self.doclist, 'purchase_receipt_details'):
			if d.fields.has_key('prevdoc_docname') and d.prevdoc_docname and d.prevdoc_docname not in check_list:
				check_list.append(d.prevdoc_docname)
				pc_obj.check_for_stopped_status( d.prevdoc_doctype, d.prevdoc_docname)


	# on submit
	def on_submit(self):
		# Check for Approving Authority
		get_obj('Authorization Control').validate_approving_authority(self.doc.doctype, self.doc.company, self.doc.grand_total)

		# Set status as Submitted
		webnotes.conn.set(self.doc,'status', 'Submitted')
		pc_obj = get_obj('Purchase Common')

		# Update Previous Doc i.e. update pending_qty and Status accordingly
		pc_obj.update_prevdoc_detail(self, is_submit = 1)

		# Update Serial Record
		get_obj('Stock Ledger').update_serial_record(self, 'purchase_receipt_details', is_submit = 1, is_incoming = 1)

		# Update Stock
		self.update_stock(is_submit = 1)

		# Update last purchase rate
		pc_obj.update_last_purchase_rate(self, 1)
		
		# make gl entry
		self.make_gl_entries()

	def make_gl_entries(self, cancel=False):
		abbr, stock_in_hand = self.get_company_details()
			
		gl_entries = []
		for item in getlist(self.doclist, 'purchase_receipt_details'):
			# debit stock in hand 
			gl_entries.append(
				self.get_gl_dict({
					"account": stock_in_hand,
					"against": "Stock Received But Not Billed - %s" % (abbr,),
					"debit": item.valuation_rate * item.conversion_factor * item.qty,
					"remarks": self.doc.remarks or "Accounting Entry for Stock"
				}, cancel)
			)

			# credit stock received but not billed
			gl_entries.append(
				self.get_gl_dict({
					"account": "Stock Received But Not Billed - %s" % (abbr,),
					"against": stock_in_hand,
					"credit": item.valuation_rate * item.conversion_factor * item.qty,
					"remarks": self.doc.remarks or "Accounting Entry for Stock"
				}, cancel)
			)

		super(DocType, self).make_gl_entries(cancel=cancel, gl_map=gl_entries)
				
	def check_next_docstatus(self):
		submit_rv = sql("select t1.name from `tabPurchase Invoice` t1,`tabPurchase Invoice Item` t2 where t1.name = t2.parent and t2.purchase_receipt = '%s' and t1.docstatus = 1" % (self.doc.name))
		if submit_rv:
			msgprint("Purchase Invoice : " + cstr(self.submit_rv[0][0]) + " has already been submitted !")
			raise Exception , "Validation Error."


	def on_cancel(self):
		pc_obj = get_obj('Purchase Common')

		self.check_for_stopped_status(pc_obj)

		submitted = sql("select t1.name from `tabPurchase Invoice` t1,`tabPurchase Invoice Item` t2 where t1.name = t2.parent and t2.purchase_receipt = '%s' and t1.docstatus = 1" % self.doc.name)
		if submitted:
			msgprint("Purchase Invoice : " + cstr(submitted[0][0]) + " has already been submitted !")
			raise Exception

		# 2.Set Status as Cancelled
		webnotes.conn.set(self.doc,'status','Cancelled')

		# 3. Cancel Serial No
		get_obj('Stock Ledger').update_serial_record(self, 'purchase_receipt_details', is_submit = 0, is_incoming = 1)

		# 4.Update Bin
		self.update_stock(is_submit = 0)

		# 5.Update Purchase Requests Pending Qty and accordingly it's Status
		pc_obj.update_prevdoc_detail(self, is_submit = 0)

		# 6. Update last purchase rate
		pc_obj.update_last_purchase_rate(self, 0)
		
		self.make_gl_entries(cancel=True)


	def bk_flush_supp_wh(self, is_submit):
		"""Back Flush function called on submit and on cancel from update stock"""
		for d in getlist(self.doclist, 'items_supplied_for_subcontracting'):
			self.make_sl_entry(d, self.doc.supplier_warehouse, -1*flt(d.required_qty), 0, is_submit)

	def get_rate(self,arg):
		return get_obj('Purchase Common').get_rate(arg,self)
	
	def load_default_taxes(self):
		self.doclist = get_obj('Purchase Common').load_default_taxes(self)
	
	def get_purchase_tax_details(self):
		self.doclist = get_obj('Purchase Common').get_purchase_tax_details(self)
