"""This module provides the State class that maintains the global state,
such as the symbol context.

Copyright 2014--2021 Michael Hayes, UCECE

"""

from sympy.assumptions.assume import global_assumptions

from .context import Context
from .config import check_units, abbreviate_units, loose_units, show_units
from .config import canonical_units, printing_order
from .printing_config import PrintingConfig
from copy import copy

class State(object):
    """This maintains Lcapy's state, such as the defined symbols, and
    behaviour.

    `loose_units` (default True) allows constants to be added to quantities
    `show_units` (default False) prints the units after an expression
    `canonical_units` (default True) converts units to canonical form, e.g., V / A is
    shown as ohms.
    'printing.abbreviate_units` (default True) prints V rather than volts
    'printing.order` (default `none`) controls the order that symbols in an expression are printed.

    """

    def __init__(self):
        self.global_context = Context()
        self.context = self.global_context
        self.previous_context = []
        self.printing = PrintingConfig()
        
        # With loose_units can add constants to quantities, e.g., voltage(1) + 2
        # or impedance(2) == 2.
        self.loose_units = loose_units
        self.check_units = check_units
        self.show_units = show_units
        self.canonical_units = canonical_units
        self.printing.abbreviate_units = abbreviate_units
        self.printing.order = printing_order

    def new_context(self):

        context = Context()
        context.symbols = copy(self.global_context.symbols)
        return context
        
    def switch_context(self, context):

        self.previous_context.append(self.context)
        self.context = context

        global_assumptions.clear()
        global_assumptions.update(self.context.assumptions)

    def restore_context(self):

        self.context.assumptions.update(global_assumptions)
        
        self.context = self.previous_context.pop()
        
        global_assumptions.clear()
        global_assumptions.update(self.context.assumptions)

    @property
    def abbreviate_units(self):

        return self.printing.abbreviate_units

    @abbreviate_units.setter
    def abbreviate_units(self, val):
        """Enable/disable printing of units in abbreviated form."""

        self.printing.abbreviate_units = val


state = State()
