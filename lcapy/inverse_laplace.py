"""This module provides support for the unilateral inverse Laplace
transform.

Copyright 2021 Michael Hayes, UCECE

"""

from .transformer import UnilateralInverseTransformer
from .ratfun import Ratfun
from .sym import simplify, AppliedUndef
from .utils import factor_const, scale_shift, as_sum_terms
import sympy as sym

Zero = sym.S.Zero
One = sym.S.One

__all__ = ('ILT', 'inverse_laplace_transform')


class InverseLaplaceTransformer(UnilateralInverseTransformer):

    name = 'inverse Laplace transform'
    
    def noevaluate(self, expr, s, t):

        # Construct Bromwich integral.
        self.error('TODO')

    def check(self, expr, s, t, **kwargs):

        if expr.has(t):
            self.error('Expression depends on t')

    def key(self, expr, s, t, **kwargs):
        return (expr, s, t,
                kwargs.get('causal', False),
                kwargs.get('damped_sin', True),            
                kwargs.get('damping', None))

    def func(self, expr, s, t):

        if not isinstance(expr, AppliedUndef):
            self.error('Expecting function')

        scale, shift = scale_shift(expr.args[0], s)    

        # Convert V(s) to v(t), etc.
        name = expr.func.__name__
        undef = sym.Function(name[0].lower() + name[1:])(t)

        result = undef.subs(t, t / scale) / abs(scale)

        if shift != 0:
            result = result * sym.exp(t * shift / scale)    
        return result

    def do_damped_sin(self, expr, s, t):

        ncoeffs, dcoeffs = expr.coeffs()
        K = ncoeffs[0] / dcoeffs[0]

        ncoeffs = [(c / ncoeffs[0]) for c in ncoeffs]
        dcoeffs = [(c / dcoeffs[0]) for c in dcoeffs]        

        if len(ncoeffs) > 3 or len(dcoeffs) > 3:
            self.error('Not a second-order response')

        omega0 = sym.sqrt(dcoeffs[2])
        zeta = dcoeffs[1] / (2 * omega0)

        if zeta.is_constant() and zeta > 1:
            print('Warning: expression is overdamped')

        sigma1 = (zeta * omega0).simplify()
        omega1 = (omega0 * sym.sqrt(1 - zeta**2)).simplify()
        K = (K / omega1).simplify()

        E = sym.exp(-sigma1 * t)
        S = sym.sin(omega1 * t)

        h = K * E * S

        # If overdamped
        #h = K * sym.exp(-sigma1 * t) * sym.sinh(omega0 * mu * t)

        if len(ncoeffs) == 1:
            return Zero, h

        C = sym.cos(omega1 * t)
        kCd = omega1
        kSd = -sigma1
        hd = K * E * (kCd * C + kSd * S)

        if len(ncoeffs) == 2:
            return Zero, K * E * (kCd * C + (ncoeffs[1] + kSd) * S)

        kCdd = -2 * omega1 * sigma1
        kSdd = sigma1**2 - omega1**2

        G = K * E * ((kCdd + ncoeffs[1] * kCd) * C + (kSdd + ncoeffs[1] * kSd + ncoeffs[2]) * S)

        return K * kCd * sym.DiracDelta(t), G

    def ratfun(self, expr, s, t, **kwargs):

        sexpr = Ratfun(expr, s)

        if kwargs.get('damped_sin', False):
            if sexpr.degree == 2:
                return self.do_damped_sin(sexpr, s, t)
            #if False and sexpr.degree == 3 and Ratfun(expr * s).degree == 2:
            #    return self.do_damped_sin3(sexpr, s, t)

        Q, M, D, delay, undef = sexpr.as_QMD()
        if delay != 0:
            # This will be caught and trigger expansion of the expression.
            raise ValueError('Unhandled delay %s' % delay)

        cresult = Zero

        if Q:
            Qpoly = sym.Poly(Q, s)        
            C = Qpoly.all_coeffs()
            for n, c in enumerate(C):
                cresult += c * sym.diff(sym.DiracDelta(t), t, len(C) - n - 1)

        expr = M / D
        for factor in expr.as_ordered_factors():
            if factor == sym.oo:
                return Zero, factor

        sexpr = Ratfun(expr, s)
        poles = sexpr.poles(damping=kwargs.get('damping', None))

        polesdict = {}
        for pole in poles:
            polesdict[pole.expr] = pole.n

        uresult = Zero

        for pole in poles:

            p = pole.expr

            # Number of occurrences of the pole.
            o = polesdict[p]        

            if o == 0:
                continue

            if o == 1:
                pc = pole.conj
                r = sexpr.residue(p, poles)

                if pc != p and pc in polesdict:
                    # Remove conjugate from poles and process pole with its
                    # conjugate.  Unfortunately, for symbolic expressions
                    # we cannot tell if a quadratic has two real poles,
                    # a repeated real pole, or a complex conjugate pair of poles.

                    polesdict[pc] -= 1

                    p_re = sym.re(p)
                    p_im = sym.im(p)
                    r_re = sym.re(r)
                    r_im = sym.im(r)
                    et = sym.exp(p_re * t)
                    uresult += 2 * r_re * et * sym.cos(p_im * t)
                    uresult -= 2 * r_im * et * sym.sin(p_im * t)
                else:
                    uresult += r * sym.exp(p * t)
                continue

            # Handle repeated poles.
            expr2 = expr * (s - p) ** o
            expr2 = expr2.simplify()
            bino = 1
            for n in range(1, o + 1):
                m = o - n
                r = sym.limit(
                    sym.diff(expr2, s, m), s, p) / sym.factorial(m)
                uresult += r * sym.exp(p * t) * t**(n - 1) / bino
                bino *= n                

        # cresult is a sum of Dirac deltas and its derivatives so is known
        # to be causal.

        return cresult, uresult

    def product(self, expr, s, t, **kwargs):

        # Handle expressions with a function of s, e.g., V(s) * Y(s), V(s)
        # / s etc.
        if kwargs.get('causal', False):
            # Assume that all functions are causal in the expression.
            t1 = Zero
            t2 = t
        else:
            t1 = -sym.oo
            t2 = sym.oo        

        const, expr = factor_const(expr, s)

        factors = expr.as_ordered_factors()
        if len(factors) < 2:
            cresult, uresult = self.term1(expr, s, t, **kwargs)
            return const * (cresult + uresult)

        if (len(factors) > 2 and not
            # Help s * 1 / (s + R * C) * I(s)
            isinstance(factors[1], AppliedUndef) and
            isinstance(factors[2], AppliedUndef)):
            factors = [factors[0], factors[2], factors[1]] + factors[3:]

        if isinstance(factors[1], AppliedUndef):
            # Try to expose more simple cases, e.g. (R + s * L) * V(s)
            terms = factors[0].expand().as_ordered_terms()
            if len(terms) >= 2:
                result = Zero
                for term in terms:
                    result += self.product(factors[1] * term, s, t, **kwargs)
                return result * const

        cresult, uresult = self.term1(factors[0], s, t, **kwargs)
        result = cresult + uresult

        intnum = 0
        for m in range(len(factors) - 1):
            if m == 0 and isinstance(factors[1], AppliedUndef):
                # Note, as_ordered_factors puts powers of s before the functions.
                if factors[0] == s:
                    # Handle differentiation
                    # Convert s * V(s) to d v(t) / dt                        
                    result = self.func(factors[1], s, t)            
                    result = sym.Derivative(result, t)
                    continue
                elif factors[0].is_Pow and factors[0].args[0] == s and factors[0].args[1] > 0:
                    # Handle higher order differentiation
                    # Convert s ** 2 * V(s) to d^2 v(t) / dt^2
                    result = self.func(factors[1], s, t)            
                    result = sym.Derivative(result, t, factors[0].args[1])
                    continue                
                elif factors[0].is_Pow and factors[0].args[0] == s and factors[0].args[1] == -1:
                    # Handle integration  1 / s * V(s)
                    tau = self.dummy_var(expr, 'tau', level=intnum, real=True)
                    intnum += 1
                    result = self.func(factors[1], s, tau)
                    result = sym.Integral(result, (tau, t1, t))
                    continue                
            # Convert product to convolution
            tau = self.dummy_var(expr, 'tau', level=intnum, real=True)
            intnum += 1
            cresult, uresult = self.term1(factors[m + 1], s, t, **kwargs)
            expr2 = cresult + uresult
            result = sym.Integral(result.subs(t, t - tau) * expr2.subs(t, tau),
                                  (tau, t1, t2))

        return result * const

    def power(self, expr, s, t):

        # Handle expressions with a power of s.
        if not (expr.is_Pow and expr.args[0] == s):
            self.error('Expression not a power of s')
        exponent = expr.args[1]

        # Have many possible forms; the common ones are:
        # s**a, s**-a, s**(1+a), s**(1-a), s**-(1+a), s**(a-1)
        # Cannot tell if 1-a is positive.

        if exponent.is_positive:
            # Unfortunately, SymPy does not seem to support fractional
            # derivatives...
            return sym.Derivative(sym.DiracDelta(t), t, exponent,
                                  evaluate=False)

        if exponent.is_negative:
            return sym.Pow(t, -exponent - 1) / sym.Gamma(-exponent)

        self.error('Cannot determine sign of exponent')

    def delay_factor(self, expr, var):

        delay = Zero    
        rest = One

        for f in expr.as_ordered_factors():
            b, e = f.as_base_exp()
            if b == sym.E and e.is_polynomial(var):
                p = sym.Poly(e, var)
                c = p.all_coeffs()
                if p.degree() == 1:
                    delay -= c[0]
                    if c[1] != 0:
                        rest *= sym.exp(c[1])
                    continue

            rest *= f
        return rest, delay

    def sympy(self, expr, s, t):

        # This barfs when needing to generate Dirac deltas
        from sympy.integrals.transforms import inverse_laplace_transform
        result = inverse_laplace_transform(expr, s, t)

        if result.has(sym.InverseLaplaceTransform):
            raise ValueError('SymPy cannot find inverse Laplace transform of %s' % expr)
        return result

    def term1(self, expr, s, t, **kwargs):

        const, expr = factor_const(expr, s)

        if isinstance(expr, AppliedUndef):
            # Handle V(s), 3 * V(s) etc.  If causal is True it is assumed
            # that the unknown functions are causal.
            result = self.func(expr, s, t)
            return result * const, Zero

        if expr.has(AppliedUndef):
            return const * self.product(expr, s, t, **kwargs), Zero

        try:
            # This is the common case.
            cresult, uresult = self.ratfun(expr, s, t, **kwargs)
            return const * cresult, const * uresult
        except:
            pass

        if expr.is_Pow and expr.args[0] == s:
            return Zero, const * self.power(expr, s, t)            

        raise ValueError('Cannot determine inverse Laplace transform')

    def term(self, expr, s, t, **kwargs):

        expr, delay = self.delay_factor(expr, s)

        if delay == 0 and expr.has(sym.exp):
            # Handle cases like 1 / (s**2 * exp(5 * s) + s * exp(5 * s))
            expr1 = expr.simplify()
            expr2, delay2 = self.delay_factor(expr1, s)
            if not expr2.has(sym.exp):
                # Simplify can make things worse, e.g., 1 - exp(-5 *s)
                # becomes exp(-5 * s) * (exp(5 * s) - 1)
                expr = expr2
                delay = delay2

        try:
            cresult, uresult = self.term1(expr, s, t, **kwargs)
        except:

            # With deep=True, SymPy makes mess of (1 - exp(-s * T))
            terms = expr.expand(deep=False).as_ordered_terms()
           
            if len(terms) > 1:

                try:
                    # See if can convert to convolutions...
                    return self.product(expr, s, t, **kwargs), Zero
                except:
                    pass
                
                uresult = Zero
                cresult = Zero
                
                for term in terms:
                    term = term.simplify()
                    cterm, uterm = self.term(term, s, t, **kwargs)
                    cresult += cterm
                    uresult += uterm
                return cresult, uresult

            expr = expr.simplify()            
 
            try:
                cresult, uresult = self.term1(expr, s, t, **kwargs)
            except:           
                return Zero, self.sympy(expr, s, t)

        if delay != 0:
            cresult = cresult.subs(t, t - delay)
            uresult = uresult.subs(t, t - delay)

            # h(t) = g(t - T)
            # If h(t) is known to be causal and T >= 0, then g(t)
            # is also causal.  If T > 0, then causality is violated.

            # If h(t) is not known to be causal then we can only infer
            # it for t >= 0 from its Laplace transform H(s).
            # From the delay theorem, H(s) = G(s) * exp(-s * T).
            # So given G(s) we can only infer g(t) for t >= 0.
            # This implies that we can only infer h(t) for t >= T.
            # This creates a can of worms since different terms of
            # an expression can have different conditions, say
            # exp(-3 * s) / s**2 + exp(-4 * s) / s.  So for now,
            # assume causal expression...

            if not kwargs.get('causal', False):
                print('Warning, assuming causal expression')
            
            if not delay.is_negative:
                if not delay.is_positive:
                    print('Assuming %s is positive' % delay)
                cresult += uresult * sym.Heaviside(t - delay)
                uresult = Zero
            else:
                raise ValueError('Causality violated with time advance %s.' % delay)

        else:
            if kwargs.get('causal', False):
                cresult += uresult * sym.Heaviside(t)
                uresult = Zero                

        return cresult, uresult

    
inverse_laplace_transformer = InverseLaplaceTransformer()


def inverse_laplace_transform(expr, s, t, evaluate=True, **kwargs):
    """Calculate inverse Laplace of X(s) and return x(t).

    The unilateral Laplace transform cannot determine x(t) for n < 0
    unless given additional information:

    `dc` -- x(t) = constant
    `causal` -- x(t) = 0 for n < 0.
    `ac` -- x(t) = A cos(a * n) + B * sin(b * n)
    """
    
    return inverse_laplace_transformer.transform(expr, s, t,
                                                 evaluate=evaluate,
                                                 **kwargs)


def ILT(expr, s, t, evaluate=True, **kwargs):
    """Calculate inverse Laplace of X(s) and return x(t).

    The unilateral Laplace transform cannot determine x(t) for n < 0
    unless given additional information:

    `dc` -- x(t) = constant
    `causal` -- x(t) = 0 for n < 0.
    `ac` -- x(t) = A cos(a * n) + B * sin(b * n)
    """

    return inverse_laplace_transformer.transform(expr, s, t,
                                                 evaluate=evaluate,
                                                 **kwargs)
