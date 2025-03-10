"""This module provides discrete-time filter support.

Copyright 2021 Michael Hayes, UCECE

"""

from .expr import expr, equation, ExprTuple
from .nexpr import DiscreteTimeDomainExpression
from .diffeq import DifferenceEquation
from .discretetime import n, z, seq
from .sequence import Sequence
from .utils import isiterable
from numpy import arange, ndarray
from scipy.signal import lfilter
import sympy as sym


class DLTIFilter(object):

    def __init__(self, b, a):
        """Create discrete-time filter where `b` is a list or array of
        numerator coefficients and `a` is a list or array of
        denominator coefficients."""

        if not isiterable(b):
            b = (b, )
        if not isiterable(a):
            a = (a, )            
        
        self.a = ExprTuple(a)
        self.b = ExprTuple(b)

    def __repr__(self):
        """This is called by repr(expr).  It is used, e.g., when printing
        in the debugger."""
        
        return '%s(%s, %s)' % (self.__class__.__name__, self.b, self.a)

    def transfer_function(self):
        """Return discrete-time impulse response (transfer function) in
        z-domain."""                

        Nl = len(self.a)
        Nr = len(self.b)
        
        # numerator of H(z)
        num = 0 * z 
        for i in range(Nr): 
            num += self.b[i] * z**(-i)
            
        # denominator for H(z)
        denom = self.a[0] * z**0  
        for k in range(1, Nl):
            az = self.a[k] * z**(-k)
            denom += az
  
        # collect with respect to positive powers of the variable z
        num = sym.collect(sym.expand(num * z**Nl), z)
        denom = sym.collect(sym.expand(denom * z**Nl), z)
        
        Hz = expr(sym.simplify(num / denom))
        Hz.is_causal = True
        return Hz

    def impulse_response(self):
        """Return discrete-time impulse response (transfer function) in time domain."""        

        H = self.transfer_function()
        return H(n)

    def difference_equation(self, inputsym='x', outputsym='y'):
        """Return difference equation."""

        rhs = 0 * n

        for m, bn in enumerate(self.b):
            rhs += bn * expr('%s(n - %d)' % (inputsym, m))

        for m, an in enumerate(self.a[1:]):
            rhs -= an * expr('%s(n - %d)' % (outputsym, m + 1))

        lhs = self.a[0] * expr('y(n)')
        return DifferenceEquation(lhs, rhs, inputsym, outputsym)

    def zdomain_initial_response(self, ic):
        """Return Z-domain response due to initial conditions.
           ic : list with initial values y[-1], y[-2], ... 
        """        

        Nl = len(self.a)
        
        # Denominator for Yi(z)
        denom = self.a[0] * z**0  
        num = 0 * z
        for k in range(1, Nl):
            az = self.a[k] * z**(-k)
            denom += az
            # Numerator for Yi(z)
            y0 = 0 * z
            for i in range(0, k):
                y0 += ic[i] * z**(i + 1)
            num += az * y0
  
        # Collect with respect to positive powers of the variable z
        num = sym.collect(sym.expand(num * z**Nl), z)
        denom = sym.collect(sym.expand(denom * z**Nl), z)
  
        Yzi = expr(-sym.simplify(num / denom))
        Yzi.is_causal = True
        
        return Yzi

    def initial_response(self, ic):
        """Return response due to initial conditions in the time domain.
           ic : list with initial values y[-1], y[-2], ...
        """

        Yzi = self.zdomain_initial_response(ic)
        return Yzi(n)
    
    def response(self, x, ic=None, ni=None):
        """Calculate response of filter to input `x` given a list of initial conditions
        `ic` for time indexes specified by `ni`.  If `ni` is a tuple,
        this specifies the first and last (inclusive) time index. 
        
        The initial conditions are valid prior to the time indices given by the ni
        `x` can be an expression, a sequence, or a list/array of values.
        """

        if (ic is None and ni is None and isinstance(x, ndarray)
            and self.a.symbols == {} and self.b.symbols == {}):

            # Calculate numerical response
            b = self.b.fval
            a = self.a.fval
            return lfilter(b, a, x)

        if ic is None:
            ic = [0] * (len(self.a) - 1)

        if not isiterable(x) and not isinstance(x, DiscreteTimeDomainExpression):
            x = (x, )

        if not isiterable(ic):
            ic = (ic, )            
        
        if isinstance(x, (tuple, list, ndarray)):
            x = seq(x)
        elif not isinstance(x, (Sequence, DiscreteTimeDomainExpression)):
            raise ValueError('The input x must be a scalar, tuple, sequence, nexpr, list, or array')

        NO = len(ic)
        
        if NO != len(self.a) - 1:
            raise ValueError("Expected %d initial conditions, got %d" % (len(self.a) - 1, NO))

        if ni is None:
            ni = (0, 10)
        
        if isinstance(ni, tuple):
            ni = arange(ni[0], ni[1] + 1)
        
        Nn = len(ni)
  
        # Order right hand side
        Nr = len(self.b)
  
        y_tot = list(ic[-1::-1]) + Nn * [0]
  
        a_r = self.a[-1:-1-NO:-1]
        for i, nval in enumerate(ni):
            # Get previous y vals (sliding window)
            pre_y = y_tot[i:i + NO]
    
            # Calculate rhs of new value
            if isinstance(x, Sequence):
                rhs = sum(self.b[l] * x[nval - l] for l in range(Nr))
            else:
                rhs = sum(self.b[l] * x(nval - l) for l in range(Nr))
    
            # Add lhs
            y_tot[i + NO] = -1 / self.a[0] * sum(csi * ysi for csi, ysi in zip(a_r, pre_y)) + rhs / self.a[0]

        # Solution, without initial values
        ret_seq = seq(y_tot[NO:], ni)  
  
        return ret_seq


    def subs(self, *args, **kwargs):

        a = self.a.subs(*args, **kwargs)
        b = self.b.subs(*args, **kwargs)

        return self.__class__(b, a)
