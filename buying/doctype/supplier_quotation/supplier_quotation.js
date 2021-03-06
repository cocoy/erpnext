// ERPNext - web based ERP (http://erpnext.com)
// Copyright (C) 2012 Web Notes Technologies Pvt Ltd
// 
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
// 
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
// 
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

// define defaults for purchase common
cur_frm.cscript.tname = "Supplier Quotation Item";
cur_frm.cscript.fname = "quotation_items";
cur_frm.cscript.other_fname = "purchase_tax_details";

// attach required files
wn.require('app/accounts/doctype/purchase_taxes_and_charges_master/purchase_taxes_and_charges_master.js');
wn.require('app/buying/doctype/purchase_common/purchase_common.js');

erpnext.buying.SupplierQuotationController = erpnext.buying.BuyingController.extend({
	refresh: function() {
		this._super();

		if (this.frm.doc.docstatus === 1) {
			cur_frm.add_custom_button("Make Purchase Order", this.make_purchase_order);
		} 
		else if (this.frm.doc.docstatus===0) {
			cur_frm.add_custom_button(wn._('From Material Request'), 
				function() {
					wn.model.map_current_doc({
						method: "stock.doctype.material_request.material_request.make_supplier_quotation",
						source_doctype: "Material Request",
						get_query_filters: {
							material_request_type: "Purchase",
							docstatus: 1,
							status: ["!=", "Stopped"],
							per_ordered: ["<", 99.99],
							company: cur_frm.doc.company
						}
					})
				});
		}
	},	
		
	make_purchase_order: function() {
		wn.model.open_mapped_doc({
			method: "buying.doctype.supplier_quotation.supplier_quotation.make_purchase_order",
			source_name: cur_frm.doc.name
		})
	}
});

// for backward compatibility: combine new and previous states
$.extend(cur_frm.cscript, new erpnext.buying.SupplierQuotationController({frm: cur_frm}));

cur_frm.cscript.uom = function(doc, cdt, cdn) {
	// no need to trigger updation of stock uom, as this field doesn't exist in supplier quotation
}

cur_frm.fields_dict['quotation_items'].grid.get_field('project_name').get_query = 
	function(doc, cdt, cdn) {
		return{
			filters:[
				['Project', 'status', 'not in', 'Completed, Cancelled']
			]
		}
	}

cur_frm.cscript.supplier_address = function(doc, dt, dn) {
	if (doc.supplier) {
		get_server_fields("get_supplier_address", JSON.stringify({supplier: doc.supplier,
			address: doc.supplier_address, contact: doc.contact_person}), '', doc, dt, dn, 1);
	}
}
cur_frm.cscript.contact_person = cur_frm.cscript.supplier_address;

cur_frm.fields_dict['supplier_address'].get_query = function(doc, cdt, cdn) {
	return {
		filters:{'supplier': doc.supplier}
	}
}

cur_frm.fields_dict['contact_person'].get_query = function(doc, cdt, cdn) {
	return {
		filters:{'supplier': doc.supplier}
	}
}