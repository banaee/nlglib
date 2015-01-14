import numbers
from pyparsing import (nums, alphas, alphanums, restOfLine, Word,
                       Group, Optional, Keyword, Literal, CaselessKeyword,
                       Combine, Forward, Suppress, opAssoc, operatorPrecedence,
                       delimitedList, ParserElement,
                       ParseException, ParseSyntaxException)
import logging

def get_log():
    return logging.getLogger(__name__)


#______________________________________________________________________________

OP_NOT = '~'
OP_OR  = '|'
OP_AND = '&'

OP_EQUALS     = '%'
OP_NOTEQUALS  = '^'

OP_IMPLIES    = '>>'
OP_IMPLIED_BY = '<<'
OP_EQUIVALENT = '<->'

OP_FORALL = 'forall'
OP_EXISTS = 'exists'

OP_TRUE   = 'TRUE'
OP_FALSE  = 'FALSE'


# ∀ ?x: Happy(?x) ⇔ ¬Sad(?x)
OPS = {
    'not'    : OP_NOT,
    '\u00AC' : OP_NOT,
    'equals' : OP_EQUALS,
    '='      : OP_EQUALS,
    'notequals' : OP_NOTEQUALS,
    '=/='    : OP_NOTEQUALS,
    '\u2260' : OP_NOTEQUALS,
    'and'    : OP_AND,
    '\u2227' : OP_AND,
    'or'     : OP_OR,
    '\u2228' : OP_OR,
    'implies' : OP_IMPLIES,
    '->'      : OP_IMPLIES,
    '==>'     : OP_IMPLIES,
    '\u2192'  : OP_IMPLIES,
    'impliedby' : OP_IMPLIED_BY,
    '<-'        : OP_IMPLIED_BY,
    '<=='       : OP_IMPLIED_BY,
    '\u2190'    : OP_IMPLIED_BY,
    '\u2194'    : OP_EQUIVALENT,
    'equivalent': OP_EQUIVALENT,
    '<->'       : OP_EQUIVALENT,
    '<=>'       : OP_EQUIVALENT,
    '\u2200'    : OP_FORALL,
    '\u2203'    : OP_EXISTS
}


# Class based on the code accompanying AI: a modern approach.
class Expr:
    """A symbolic mathematical expression.  We use this class for logical
    expressions, and for terms within logical expressions. In general, an
    Expr has an op (operator) and a list of args.  The op can be:
      Null-ary (no args) op:
        A number, representing the number itself.  (e.g. Expr(42) => 42)
        A symbol, representing a variable or constant (e.g. Expr('F') => F)
      Unary (1 arg) op:
        '~', '-', representing NOT, negation (e.g. Expr('~', Expr('P')) => ~P)
      Binary (2 arg) op:
        '>>', '<<', representing forward and backward implication
        '**' representing biconditional (logical equivalence)
        '+', '-', '*', '/' representing arithmetic operators
        '<', '>', '>=', '<=', representing comparison operators
        '<=>', '^', representing logical equality and XOR
      N-ary (0 or more args) op:
        '&', '|', representing conjunction and disjunction
        A symbol, representing a function term or FOL proposition

    Exprs can be constructed with operator overloading: if x and y are Exprs,
    then so are x + y and x & y, etc.
    
    WARNING: x == y and x != y are NOT Exprs.  The reason is that we want
    to write code that tests 'if x == y:' and if x == y were the same
    as Expr('==', x, y), then the result would always be true; not what a
    programmer would expect.  But we still need to form Exprs representing
    equalities and disequalities.  We concentrate on logical equality (or
    equivalence) and logical disequality (or XOR).  You have 3 choices:
        (1) Expr('<=>', x, y) and Expr('^', x, y)
            Note that ^ is bitwose XOR in Python (and Java and C++)
        (2) expr('x <=> y') and expr('x =/= y').
            See the doc string for the function expr.
        (3) (x % y) and (x ^ y).
            It is very ugly to have (x % y) mean (x <=> y), but we need
            SOME operator to make (2) work, and this seems the best choice.

    WARNING: if x is an Expr, then so is x + 1, because the int 1 gets
    coerced to an Expr by the constructor.  But 1 + x is an error, because
    1 doesn't know how to add an Expr.  (Adding an __radd__ method to Expr
    wouldn't help, because int.__add__ is still called first.) Therefore,
    you should use Expr(1) + x instead, or ONE + x, or expr('1 + x').
    """

    def __init__(self, op, *args):
        "Op is a string or number; args are Exprs (or are coerced to Exprs)."
        assert (isinstance(op, str) or
                (isinstance(op, numbers.Number) and not args)),\
               '{0}({1})'.format(op, args)
        self.op = num_or_str(op)
        self.args = list(map(to_expr, args)) ## Coerce args to Exprs

    def __str__(self):
        "Show something like 'P' or 'P(x, y)', or '~P' or '(P | Q | R)'"
        if not self.args:         # Constant or proposition with arity 0
            return str(self.op)
        elif is_symbol(self.op):  # Functional or propositional operator
            return '%s(%s)' % (self.op, ', '.join(map(str, self.args)))
        elif len(self.args) == 1: # Prefix operator
            return self.op + str(self.args[0])
        else:                     # Infix operator
            return '(%s)' % (' '+self.op+' ').join(map(str, self.args))

    def __repr__(self):
        "Show something like 'P' or '(P x, y)', or '(~ P)' or '(| P Q R)'"
        if not self.args:         # Constant or proposition with arity 0
            return str(self.op)
        else :
            return '(%s %s)' % (self.op, ', '.join(map(repr, self.args)))

    def __eq__(self, other):
        """x and y are equal iff their ops and args are equal."""
        return (other is self) or (isinstance(other, Expr)
            and self.op == other.op and self.args == other.args)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        "Need a hash method so Exprs can live in dicts."
        return hash(self.op) ^ hash(tuple(self.args))

    # Some operators implemented for convenience
    def __neg__(self):           return Expr('-',  self)
    def __lt__(self, other):     return Expr('<',  self, other)
    def __le__(self, other):     return Expr('<=', self, other)
    def __ge__(self, other):     return Expr('>=', self, other)
    def __gt__(self, other):     return Expr('>',  self, other)
    def __add__(self, other):    return Expr('+',  self, other)
    def __sub__(self, other):    return Expr('-',  self, other)
    def __mul__(self, other):    return Expr('*',  self, other)
    def __div__(self, other):    return Expr('/',  self, other)
    def __truediv__(self, other):return Expr('/',  self, other)
    
    def __invert__(self):        return Expr(OP_NOT,  self)
    def __and__(self, other):    return Expr(OP_AND,  self, other)
    def __or__(self, other):     return Expr(OP_OR,  self, other)
    
    def __lshift__(self, other): return Expr(OP_IMPLIED_BY, self, other)
    def __rshift__(self, other): return Expr(OP_IMPLIES, self, other)
    def __pow__(self, other):    return Expr(OP_EQUIVALENT, self, other)
    
    def __mod__(self, other):    return Expr(OP_EQUALS,  self, other)
    def __xor__(self, other):    return Expr(OP_NOTEQUALS,  self, other)


class Quantifier(Expr):
    """ Quantified expression is an expression that contains variables. """

    def __init__(self, op, vars, *args):
        super(Quantifier, self).__init__(op, *args)
        if isinstance(vars, Expr):
            self.vars = [vars]
        else:
            self.vars = list(map(to_expr, vars))

    def __repr__(self):
        "Show something like 'P' or 'P(x, y)', or '~P' or '(P | Q | R)'"
        return '{0} {1}: ({2})'.format(self.op,
                                ', '.join(map(repr, self.vars)),
                                ', '.join(map(repr, self.args)))

    def __str__(self):
        "Show something like 'P' or 'P(x, y)', or '~P' or '(P | Q | R)'"
        return '{0} {1}: ({2})'.format(self.op,
                                ', '.join(map(str, self.vars)),
                                ', '.join(map(str, self.args)))
    
    def __eq__(self, other):
        """x and y are equal iff their ops and args are equal."""
        return (isinstance(other, Quantifier) and
                self.op == other.op and
                self.vars == other.vars and
                self.args == other.args)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        "Need a hash method so Exprs can live in dicts."
        return hash(self.op) ^ hash(tuple(self.vars)) ^ hash(tuple(self.args))

# TODO: split into is_symbol and is_number?
def is_symbol(s):
    "A string s is a symbol if it starts with an alphabetic char."
    return ((isinstance(s, str) and
             (s[0].isalpha() or s[0] == '?') and
             (s != OP_FORALL and s != OP_EXISTS)) or
             isinstance(s, numbers.Number))


def is_var_symbol(s):
    "A logic variable symbol is an initial-lowercase string."
    try:
        return is_symbol(s) and (s[0] == '?' or s[0].islower())
    except:
        return False


def is_function_symbol(s):
    "A string s is a symbol if it starts with an initial-lowercase string."
    try:
        return is_symbol(s) and s[0].islower()
    except:
        return False


def is_prop_symbol(s):
    """A proposition logic symbol is an initial-uppercase string other than
    TRUE or FALSE."""
    try:
        return is_symbol(s) and s[0].isupper() and s != 'TRUE' and s != 'FALSE'
    except:
        return False


def is_variable(f):
    """Formula f is a variable if it has a variable symbol as an operator. """
    return is_var_symbol(f.op)


def is_constant(f):
    """Formula f is a constant if its op is a function symbol with no args. """
    return ((is_function_symbol(f.op) and len(f.args) == 0) or
            (isinstance(f.op, numbers.Number)))


def is_function(f):
    """Formula f is a function if its op is a function symbol with args. """
    return (is_function_symbol(f.op) and len(f.args) > 0)


def is_term(f):
    """Formula f is a term if it is a variable, constant or a function. """
    return (is_variable(f) or is_constant(f) or is_function(f))


def is_quantified(f):
    """Formula f is quantifie if the operator is a quantifier. """
    return (f.op == OP_EXISTS or f.op == OP_FORALL)


def is_atomic_formula(f):
    """Formula f is an atomic formula if it is =, != or a predicate. """
    return (f.op == OP_EQUALS or f.op == OP_NOTEQUALS or is_prop_symbol(f.op))


def is_true(f):
    """ Return True if the operator is OP_TRUE (ignore case). """
    return str(f.op).upper() == OP_TRUE


def is_false(f):
    """ Return True if the operator is OP_FALSE (ignore case). """
    return str(f.op).upper() == OP_FALSE


def vars(s):
    """ Return all variables in a formula (including vars in quantifiers). """
    if is_variable(s):
        return {s}
    elif is_quantified(s):
        return set(s.vars).union(*list(map(vars, s.args)))
    else:
        return set().union(*list(map(vars, s.args)))


def fvars(s):
    """ Return free variables. """
    if is_variable(s):
        return {s}
    elif is_quantified(s):
        return set().union(*list(map(fvars, s.args))) - set(s.vars)
    else:
        return set().union(*list(map(fvars, s.args)))


def generalise(f):
    """Take a formula and bind all free variables to a universal quantifier. """
    return Quantifier(OP_FORALL, fvars(f), f)


def variant(x, vars):
    """ Create a variant of a variable name. If the variable x appears 
    in the set of variables, add an apostrophe and try again.
    
    >>> variant('x', ['y', 'z'])
    "x"
    >>> variant('x', ['x', 'y', 'z'])
    "x'"
    
    """
    if x in vars: return variant(Expr(x.op + "'", *x.args), vars)
    else: return x


def subst(mappings, tm):
    """ Substitute terms in a formula.
    
    For example, to substitute 'c' by 'x' the variable in forall x has to be
    renamed to something else (x' in our case).
    
    >>> subst({Expr('c'): Expr('x')}, expr('forall x: c > 0 -> x + c > x'))
    #   --> "forall x': x > 0 -> x' + x > x'"
    
    """
    if is_variable(tm):
        if tm in mappings: return mappings[tm]
        else: return tm
    if is_quantified(tm):
        for var in tm.vars:
            # get the list of existing variables in the mappings
            existing_vars = set().union(*list(map(vars, mappings.values())))
            # rename any quantifier variable that would become bound by subst.
            if var in existing_vars:
                var2 = variant(var, existing_vars)
                mappings[var] = var2
        return Quantifier(tm.op,
                          [subst(mappings, x) for x in tm.vars],
                          *[subst(mappings, x) for x in tm.args])
    else:
        return Expr(tm.op, *[subst(mappings, x) for x in tm.args])


def simplify(f):
    """ Take a FOL formula and try to simplify it. """
#    print('\nSimplifying op "{0}" args "{1}"'.format(f.op, f.args))
    if is_quantified(f): # remove variable that are not in f
        vars = set(f.vars)
        fv = fvars(f.args[0])
        needed = vars & fv
        if needed == set():
            return simplify(f.args[0])
        else:
            arg = simplify(f.args[0])
            variables = [v for v in f.vars if v in needed] # keep the same order
            if (arg != f.args[0]) or (len(needed) < len(f.vars)):
                return simplify(Quantifier(f.op, variables, arg))
            else:
                return f
    if f.op == OP_NOT:
        arg = f.args[0]
        if arg.op == OP_NOT: # double neg
            return simplify(arg.args[0])
        elif is_true(arg): # -TRUE --> FALSE
            return Expr(OP_FALSE)
        elif is_false(arg): # -FALSE --> TRUE
            return Expr(OP_TRUE)
        else:
            arg2 = simplify(arg)
            if arg2 != arg:
                return simplify(Expr(OP_NOT, arg2))
            return f
    if f.op == OP_AND:
        if any(map(is_false, f.args)): # if one conjuct is FALSE, expr is FALSE
            return Expr(OP_FALSE)
        elif len(f.args) == 1:
            return simplify(f.args[0])
        else: # remove conjuncts that are TRUE and simplify args
            args = list(map(simplify, filter(lambda x: not is_true(x),f.args)))
            if args != f.args:
                return simplify(Expr(OP_AND, *args))
            else:
                return f
    if f.op == OP_OR:
        if any(map(is_true, f.args)): # if one conjuct is TRUE, expr is TRUE
            return Expr(OP_TRUE)
        elif len(f.args) == 1:
            return simplify(f.args[0])
        else: # remove conjuncts that are TRUE and simplify args
            args = list(map(simplify, filter(lambda x: not is_false(x),f.args)))
            if args != f.args:
                return simplify(Expr(OP_OR, *args))
            else:
                return f
    if f.op == OP_IMPLIES:
        if is_false(f.args[0]) or is_true(f.args[1]):
            return Expr(OP_TRUE)
        elif is_true(f.args[0]):
            return simplify(f.args[1])
        elif is_false(f.args[1]):
            return simplify(Expr(OP_NOT, simplify(f.args[0])))
        else:
            arg1 = simplify(f.args[0])
            arg2 = simplify(f.args[1])
            if arg1 != f.args[0] or arg2 != f.args[1]:
                return simplify(Expr(OP_IMPLIES, arg1, arg2))
            else:
                return f
    if f.op == OP_IMPLIED_BY:
        if is_false(f.args[1]) or is_true(f.args[0]):
            return Expr(OP_TRUE)
        elif is_true(f.args[1]):
            return simplify(f.args[0])
        elif is_false(f.args[0]):
            return simplify(Expr(OP_NOT, simplify(f.args[1])))
        else:
            arg1 = simplify(f.args[0])
            arg2 = simplify(f.args[1])
            if arg1 != f.args[0] or arg2 != f.args[1]:
                return simplify(Expr(OP_IMPLIES, arg1, arg2))
            else:
                return f
    if f.op == OP_EQUIVALENT:
        if is_true(f.args[0]):
            return simplify(f.args[1])
        elif is_true(f.args[1]):
            return simplify(f.args[0])
        elif is_false(f.args[0]):
            return simplify(Expr(OP_NOT, simplify(f.args[1])))
        elif is_false(f.args[1]):
            return simplify(Expr(OP_NOT, simplify(f.args[0])))
        else:
            arg1 = simplify(f.args[0])
            arg2 = simplify(f.args[1])
            if arg1 != f.args[0] or arg2 != f.args[1]:
                return simplify(Expr(OP_EQUIVALENT, arg1, arg2))
            else:
                return f
    else:
        return f


def nnf(f):
    """ Create a Negated Normal Form """
    if f.op == OP_NOT:
        arg = f.args[0]
        if arg.op == OP_NOT:
            return nnf(arg.args[0])
        elif arg.op == OP_AND:
            return Expr(OP_OR, *[nnf(Expr(OP_NOT, x)) for x in arg.args])
        elif arg.op == OP_OR:
            return Expr(OP_AND, *[nnf(Expr(OP_NOT, x)) for x in arg.args])
        elif arg.op == OP_IMPLIES: # p -> q
            p, q = arg.args[0], arg.args[1]
            return (nnf(p) & nnf(~(q)))
        elif arg.op == OP_IMPLIED_BY: # p <- q
            p, q = arg.args[0], arg.args[1]
            return (nnf(~p) & nnf(q))
        elif arg.op == OP_EQUIVALENT: # p <-> q
            p, q = arg.args[0], arg.args[1]
            return ((nnf(p) & nnf(~q)) | (nnf(~p) & nnf(q)))
        elif arg.op == OP_FORALL:
            return Quantifier(OP_EXISTS, arg.vars,
                              nnf(Expr(OP_NOT, arg.args[0])))
        elif arg.op == OP_EXISTS:
            return Quantifier(OP_FORALL, arg.vars,
                              nnf(Expr(OP_NOT, arg.args[0])))
        else:
            return f
    elif f.op == OP_AND or f.op == OP_OR:
        if len(f.args) > 2:
            return Expr(f.op,
                        nnf(f.args[0]),
                        nnf(Expr(f.op, *[nnf(x) for x in f.args[1:]])))
        else:
            return Expr(f.op, *[nnf(x) for x in f.args])
    elif f.op == OP_IMPLIES:
        p, q = f.args[0], f.args[1]
        return (nnf(~p) | nnf(q))
    elif f.op == OP_IMPLIED_BY:
        p, q = f.args[0], f.args[1]
        return (nnf(p) | nnf(~q))
    elif f.op == OP_EQUIVALENT:
        p, q = f.args[0], f.args[1]
        return (nnf(p) & nnf(q)) | (nnf(~p) & nnf(~q))
    elif is_quantified(f):
        if len(f.vars) > 1:
            return Quantifier(f.op, f.vars[0],
                              nnf(Quantifier(f.op, f.vars[1:],
                                  *[nnf(x) for x in f.args])))
        else:
            return Quantifier(f.op, f.vars, *[nnf(x) for x in f.args])
    else:
        return f


def unique_vars(f):
    """ Rename variable so that each variable appears only once per formula.
    >>> unique_vars(expr('(forall x: P(x)) | (forall x: Q(x)))')
    expr("(forall x: P(x)) | (forall x': Q(x'))")
    
    """
    def helper(f, used, substs):
        if is_variable(f):
            if f in substs: return substs[f]
            else: return f
        if is_quantified(f):
            # does this quantifier use a variable that is already used?
            clashing = (used & set(f.vars)) # set intersection
            if len(clashing) > 0:
                for var in clashing:
                    existing = used.union(*list(map(vars, substs.values())))
                    # rename any clashing variable
                    var2 = variant(var, existing)
                    substs[var] = var2
                used.update(f.vars)
                arg = helper(f.args[0], used, substs)
                return Quantifier(f.op,
                                  [subst(substs, x) for x in f.vars],
                                  *[subst(substs, x) for x in f.args])
            else:
                used.update(f.vars)
                arg = helper(f.args[0], used, substs)
                return Quantifier(f.op, f.vars, arg)
        else:
            return Expr(f.op, *[helper(x, used, substs) for x in f.args])
    return helper(f, set(), {})


def pullquants(f):
    """ Pull out quantifiers to the front of the formula f.
    The function assumes that all operators have at most two arguments 
    and all quantifiers have at most one variable (this can be achieved using
    the function nnf(), which converts a formula into a negated normal form).
    Also, each variabl name can be used only once per formula.
    
    """
#    print('pullquants({0})'.format(str(f)))
    if f.op == OP_AND:
        arg1 = pullquants(f.args[0])
        arg2 = pullquants(f.args[1])
        if arg1.op == OP_FORALL and arg2.op == OP_FORALL:
            # when both conjuncts are forall, we can re-use the variable name
            # eg. (forall x: P(x) & forall y: Q(y)) <-> (forall x: P(x) & Q(x))
            old_var = arg1.vars[0]
            new_var = variant(arg1.vars[0], fvars(f))
            a1 = subst({arg1.vars[0]: new_var}, arg1.args[0])
            a2 = subst({arg2.vars[0]: new_var}, arg2.args[0])
            return Quantifier(OP_FORALL, [new_var], pullquants(a1 & a2))
        elif arg1.op == OP_EXISTS and arg2.op == OP_EXISTS:
            return f
        elif is_quantified(arg1):
            old_var = arg1.vars[0]
            new_var = variant(old_var, fvars(f))
            a1 = subst({old_var: new_var}, arg1.args[0])
            a2 = arg2 #subst({old_var: new_var}, arg2)
            return Quantifier(arg1.op, [new_var], pullquants(a1 & a2))
        elif is_quantified(arg2):
            old_var = arg2.vars[0]
            new_var = variant(old_var, fvars(f))
            a1 = arg1 #subst({old_var: new_var}, arg1)
            a2 = subst({old_var: new_var}, arg2.args[0])
            return Quantifier(arg2.op, [new_var], pullquants(a1 & a2))
        else:
            return (arg1 & arg2)
    elif f.op == OP_OR:
        arg1 = pullquants(f.args[0])
        arg2 = pullquants(f.args[1])
        if arg1.op == OP_EXISTS and arg2.op == OP_EXISTS:
            # when both disjuncts are exists, we can re-use the variable name
            # eg. (exists x: P(x) | exists y: Q(y)) <-> (exists x: P(x) | Q(y))
            new_var = variant(arg1.vars[0], fvars(f))
            a1 = subst({arg1.vars[0]: new_var}, arg1.args[0])
            a2 = subst({arg2.vars[0]: new_var}, arg2.args[0])
            return Quantifier(OP_EXISTS, [new_var], pullquants(a1 | a2))
        elif arg1.op == OP_FORALL and arg2.op == OP_FORALL:
            return f
        elif is_quantified(arg1):
            old_var = arg1.vars[0]
            new_var = variant(old_var, fvars(f))
            a1 = subst({old_var: new_var}, arg1.args[0])
            a2 = arg2 #subst({old_var: new_var}, arg2)
            return Quantifier(arg1.op, [new_var], pullquants(a1 | a2))
        elif is_quantified(arg2):
            old_var = arg2.vars[0]
            new_var = variant(old_var, fvars(f))
            a1 = arg1 #subst({old_var: new_var}, arg1)
            a2 = subst({old_var: new_var}, arg2.args[0])
            return Quantifier(arg2.op, [new_var], pullquants(a1 | a2))
        else:
            return (arg1 | arg2)
    # TODO add conditionals (just for fun)
    else:
        return f


def pnf(f):
    """ Return formula f in a Prenex Normal Form. """
    return pullquants(nnf(simplify(f)))


def pushquants(f):
    """Return formula f' equivalent to f in which quantifiers have the smallest
    possible scope.
    
    """
    assert False, 'Not implemented.'



# #############################  PARSING  ################################### #


PARSE_DEBUG = False


def get_op(x):
    """ Return a standard operator given an alternative one. """
    if x in OPS: return OPS[x]
    return x


def to_expr(item):
    """ Convert to instance of Expr. """
    get_log().debug('to_expr: ' + str((repr(type(item)), repr(item))))
    if isinstance(item, str): return Expr(num_or_str(item))
    if isinstance(item, Expr): return item
    if hasattr(item, '__getitem__'): return list(map(to_expr, item))
    return item.to_expr()


class FOLQuant:
    def __init__(self, t):
        tmp = t[0].asDict()
        self.op = get_op(tmp['quantifier'])
        self.vars = tmp['vars'].asList()
        self.args = [tmp['args']]
        if PARSE_DEBUG:
            print('created quant "{0}"'.format(self.op))
            print('\targs "{0}"'.format(self.args))

    def __str__(self):
        vars = ', '.join(self.vars)
        return("%s %s: (" % (self.op, vars)) + ''.join(map(str,self.args)) + ")"

    __repr__ = __str__

    def to_expr(self):
        return Quantifier(self.op, [to_expr(v) for v in self.vars], *self.args)


class FOLBinOp:
    def __init__(self,t):
        self.op = get_op(t[0][1])
        self.args = t[0][0::2]
        if PARSE_DEBUG:
            print('created binop "{0}"'.format(self.op))
            print('\targs "{0}"'.format(self.args))
        
    def __str__(self):
        sep = " %s " % self.op
        return "(" + sep.join(map(str,self.args)) + ")"
    
    __repr__ = __str__
        
    def to_expr(self):
        return Expr(self.op, *self.args)


class FOLUnOp:
    def __init__(self,t):
        self.op = get_op(t[0][0])
        self.args = to_expr(t[0][1])
        if PARSE_DEBUG:
            print('created unop "{0}"'.format(self.op))
            print('\targs "{0}"'.format(self.args))
        
    def __str__(self):
        return (str(self.op) + "(" + str(self.args) + ")")

    __repr__ = __str__

    def to_expr(self):
        return Expr(self.op, self.args)


class FOLPred:
    def __init__(self,t):
        self.op = get_op(t[0][0])
        self.args = t[0][1]
        if PARSE_DEBUG:
            print('created pred "{0}"'.format(self.op))
            print('\targs "{0}"'.format(self.args))
        
    def __str__(self):
        return (str(self.op) + "(" + ', '.join(map(str,self.args)) + ")")

    __repr__ = __str__

    def to_expr(self):
        return Expr(self.op, *self.args)


# code nicked from the book Programming in Python 3 (kindle)
# optimisation -- before creating any parsing elements
ParserElement.enablePackrat()


left_parenthesis, right_parenthesis = map(Suppress, '()')
forall = Keyword('forall') | Literal('\u2200')
exists = Keyword('exists') | Literal('\u2203')
implies = Literal('->') | Literal('==>') | \
          Keyword('implies') | Literal('\u2192')
implied = Literal('<-') | Literal('<==') | \
          Keyword('impliedby') | Literal('\u2190')
iff = Literal('<=>') | Literal('<->') | Keyword('iff') | Literal('\u2194')
or_  = Literal('\\/') | Literal('|') | Keyword('or') | Literal('\u2228')
and_ = Literal('/\\') | Literal('&') | Keyword('and') | Literal('\u2227')
not_ = Literal('~') | Keyword('not') | Literal('\u00AC')
equals = Literal('=') | Keyword('equals')
maths = list(map(Literal, ['^', '*', '/', '+', '-']))
relations = list(map(Keyword, ['<', '<=', '>', '>=']))
notequals = Literal('=/=') | Keyword('notequals') | Literal('\u2260')
boolean = (CaselessKeyword('FALSE') | CaselessKeyword('TRUE'))
colon = Literal(':').suppress()
symbol = Word(alphas + '?', alphanums + "'")
number = Combine(Optional('-') + Word(nums, nums + '.'))

math_expr = Forward()
math_expr << operatorPrecedence(number | symbol,
                [(op, 2, opAssoc.LEFT, FOLBinOp) for op in maths])

term = Forward() # definition of term will involve itself
term << (Group(Word(alphas, alphanums) +
               Group(left_parenthesis +
               delimitedList(term) +
               right_parenthesis)).setParseAction(FOLPred) |
         math_expr)

# allow python style comments
comment = (Literal('#') + restOfLine).suppress()

# main parser for FOL formula
formula = Forward()
formula.ignore(comment)
forall_expression = Group(forall.setResultsName("quantifier") +
                       delimitedList(symbol).setResultsName("vars") + colon +
                       formula.setResultsName("args")
                    ).setParseAction(FOLQuant)
exists_expression = Group(exists.setResultsName("quantifier") +
                      delimitedList(symbol).setResultsName("vars") + colon +
                      formula.setResultsName("args")).setParseAction(FOLQuant)

operand = forall_expression | exists_expression | boolean | term

# specify the precedence -- highest precedence first, lowest last
operator_list = [(not_, 1, opAssoc.RIGHT, FOLUnOp)]

operator_list += ([(r, 2, opAssoc.LEFT, FOLBinOp) for r in relations])

operator_list += [(equals, 2, opAssoc.LEFT, FOLBinOp),
                  (notequals, 2, opAssoc.LEFT, FOLBinOp),
                  (and_, 2, opAssoc.LEFT, FOLBinOp),
                  (or_, 2, opAssoc.LEFT, FOLBinOp),
                  (implies, 2, opAssoc.RIGHT, FOLBinOp),
                  (implied, 2, opAssoc.RIGHT, FOLBinOp),
                  (iff, 2, opAssoc.RIGHT, FOLBinOp)]

formula << operatorPrecedence(operand, operator_list)


# #############################  HELPERS  ################################### #


def num_or_str(x):
    """The argument is a string; convert to a number if possible, or strip it.
    >>> num_or_str('42')
    42
    >>> num_or_str(' 42x ')
    '42x'
    """
    if isinstance(x, numbers.Number):
        return x
    try:
        if '.' in x:
            return float(x)
        else:
            return int(x)
    except ValueError:
        return str(x).strip()


class FormulaParseError(Exception):
    pass


def expr(s):
    """ Parse the string s representing a formula and return it as an Expr. """
    try:
        result = formula.parseString(s, parseAll=True)
        return to_expr(result[0])
    except (ParseException, ParseSyntaxException) as err:
        msg=("Syntax error: {0!r}\n{0.line}\n{1}^".\
             format(err, " " * (err.column)))
        raise FormulaParseError(msg)
    except RuntimeError:
        raise FormulaParseError("Infinite loop in parse.")

# error handling -- consider
#>>> def oops(s, loc, expr, err):
#...     print ("s={0!r} loc={1!r} expr={2!r}\nerr={3!r}".format(
#...            s, loc, expr, err))
#... 
#>>> fail = pp.NoMatch().setName('fail-parser').setFailAction(oops)
#>>> r = fail.parseString("None shall pass!")
#s='None shall pass!' loc=0 expr=fail-parser
#err=Expected fail-parser (at char 0), (line:1, col:1)
#pyparsing.ParseException: Expected fail-parser (at char 0), (line:1,
#col:1)

###
