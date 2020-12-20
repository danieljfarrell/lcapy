"""This module performs transformations between domains.

Copyright 2018--2020 Michael Hayes, UCECE

"""

from .sym import sympify, pi
from .symbols import f, s, t, omega, jomega, j
from .expr import expr as expr1


def transform1(expr, arg, **assumptions):

    # Handle things like (3 * s)(5 * s)
    if isinstance(expr, arg.__class__) and not isinstance(expr, Superposition):
        return expr.subs(arg)

    # Special case: handle expr(j * omega)
    if isinstance(expr, (LaplaceDomainExpression, Superposition)) and arg == j * omega:
        return expr.laplace(**assumptions).subs(arg)

    # Handle expr(t), expr(s), expr(f), expr(omega)
    if arg is t:
        return expr.time(**assumptions)
    elif arg is s:
        return expr.laplace(**assumptions)
    elif arg is f:
        return expr.fourier(**assumptions)
    elif arg is omega:
        return expr.angular_fourier(**assumptions)

    # Handle expr(texpr), expr(sexpr), expr(fexpr), expr(omegaexpr).  For example,
    # expr(2 * f).
    result = None 
    if isinstance(arg, TimeDomainExpression):
        result = expr.time(**assumptions)
    elif isinstance(arg, LaplaceDomainExpression):
        result = expr.laplace(**assumptions)
    elif isinstance(arg, FourierDomainExpression):
        result = expr.fourier(**assumptions)
    elif isinstance(arg, AngularFourierDomainExpression):
        result = expr.angular_fourier(**assumptions)        
    elif arg.has(jomega):
        # Perhaps restrict this to jomega and not expressions like 5 * jomega ?
        if isinstance(expr, LaplaceDomainExpression):
            result = expr.subs(arg)
            return result
        else:
            result = expr.laplace(**assumptions)
    elif arg.is_constant:
        if not isinstance(expr, Superposition):
            result = expr.time(**assumptions)
        else:
            result = expr
    else:
        raise ValueError('Can only return t, f, s, or omega domains')

    return result.subs(arg, **assumptions)


def transform(expr, arg, **assumptions):
    """If arg is f, s, t, omega, jomega perform domain transformation,
    otherwise perform substitution.

    Note (5 * s)(omega) will fail since 5 * s is assumed not to be
    causal and so Fourier transform is unknown.  However, Zs(5 *
    s)(omega) will work since Zs is assumed to be causal.

    """

    arg = expr1(arg)

    new = transform1(expr, arg, **assumptions)
    return wrap(expr, new)


def wrap(old, new):

    if not hasattr(old, 'wrapper'):
        return new
    
    wrappers = {'voltage': voltage, 'current': current,
                'impedance': impedance, 'admittance': admittance,
                'transfer': transfer}
    if old.wrapper not in wrappers:
        return new
    return wrappers[old.wrapper](new)    
    

def call(expr, arg, **assumptions):

    if id(arg) in (id(f), id(s), id(t), id(omega), id(jomega)):
        return expr.transform(arg, **assumptions)

    if arg in (f, s, t, omega, jomega):
        return expr.transform(arg, **assumptions)    
    
    return expr.subs(arg)


def select(expr, kind):

    if kind in ('t', 'time'):
        return expr.time()
    elif kind == 'dc':
        return expr.subs(0)
    elif kind in ('s', 'ivp'):
        return expr.laplace()
    elif kind == 'f':
        return expr.fourier()
    elif kind == 'omega':
        return expr.angular_fourier()
    return expr.subs(j * kind)


from .cexpr import ConstantExpression    
from .fexpr import FourierDomainExpression    
from .sexpr import LaplaceDomainExpression
from .texpr import TimeDomainExpression
from .omegaexpr import AngularFourierDomainExpression
from .super import Superposition
from .current import current
from .voltage import voltage
from .admittance import admittance
from .impedance import impedance
from .transfer import transfer
