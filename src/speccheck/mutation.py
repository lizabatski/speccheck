"""Mutation generation — turn a correct function into many broken variants.

We edit the function's Abstract Syntax Tree (not its text), so mutations are precise:
"flip > to >=" means "find Compare nodes with a Gt op and swap it", which can't
accidentally corrupt strings or comments.

Each single-node change produces one mutant. The catalogue below covers the standard
mutation-testing operators that map cleanly onto Python AST nodes.
"""
from __future__ import annotations

import ast
import copy
import inspect
from typing import Callable, Iterator


# ---- comparison operator swaps ----
_CMP_SWAP = {
    ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Lt: ast.LtE, ast.LtE: ast.Lt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
}

# ---- binary arithmetic operator swaps ----
_BIN_SWAP = {
    ast.Add: ast.Sub, ast.Sub: ast.Add,
    ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult,
}

# ---- boolean operator swaps ----
_BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


def _strip_indent(src: str) -> str:
    """inspect.getsource keeps original indentation; dedent so ast.parse is happy."""
    import textwrap
    return textwrap.dedent(src)


def _compile_func(tree: ast.Module, name: str) -> Callable:
    ast.fix_missing_locations(tree)
    code = compile(tree, filename="<mutant>", mode="exec")
    ns: dict = {}
    exec(code, ns)
    return ns[name]


class _Mutation:
    """A description of one single-node change to apply to a fresh tree copy."""
    def __init__(self, kind: str, node_index: int, op_slot: int, old: str, new: str,
                 new_factory):
        self.kind = kind
        self.node_index = node_index   # index among nodes of this kind, in walk order
        self.op_slot = op_slot         # for Compare, which op in the ops list
        self.old = old
        self.new = new
        self.new_factory = new_factory

    def label(self) -> str:
        return f"{self.kind}#{self.node_index}: {self.old} -> {self.new}"


def _plan_mutations(tree: ast.Module) -> list[_Mutation]:
    """Walk the tree once and enumerate every mutation we can apply."""
    plan: list[_Mutation] = []

    cmp_i = bin_i = bool_i = const_i = ret_i = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for slot, op in enumerate(node.ops):
                if type(op) in _CMP_SWAP:
                    new_t = _CMP_SWAP[type(op)]
                    plan.append(_Mutation("cmp", cmp_i, slot,
                                          type(op).__name__, new_t.__name__, new_t))
                cmp_i += 1
        elif isinstance(node, ast.BinOp) and type(node.op) in _BIN_SWAP:
            new_t = _BIN_SWAP[type(node.op)]
            plan.append(_Mutation("bin", bin_i, -1,
                                  type(node.op).__name__, new_t.__name__, new_t))
            bin_i += 1
        elif isinstance(node, ast.BoolOp) and type(node.op) in _BOOL_SWAP:
            new_t = _BOOL_SWAP[type(node.op)]
            plan.append(_Mutation("bool", bool_i, -1,
                                  type(node.op).__name__, new_t.__name__, new_t))
            bool_i += 1
        elif isinstance(node, ast.Constant) and isinstance(node.value, int) \
                and not isinstance(node.value, bool):
            # off-by-one style tweak: n -> n+1
            plan.append(_Mutation("const", const_i, -1,
                                  str(node.value), str(node.value + 1), None))
            const_i += 1

    return plan


def _apply_mutation(tree: ast.Module, m: _Mutation) -> None:
    """Mutate a FRESH copy of the tree in place according to plan item m."""
    cmp_i = bin_i = bool_i = const_i = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for slot, op in enumerate(node.ops):
                if m.kind == "cmp" and cmp_i == m.node_index and slot == m.op_slot:
                    node.ops[slot] = m.new_factory()
                    return
                cmp_i += 1
        elif isinstance(node, ast.BinOp) and type(node.op) in _BIN_SWAP:
            if m.kind == "bin" and bin_i == m.node_index:
                node.op = m.new_factory()
                return
            bin_i += 1
        elif isinstance(node, ast.BoolOp) and type(node.op) in _BOOL_SWAP:
            if m.kind == "bool" and bool_i == m.node_index:
                node.op = m.new_factory()
                return
            bool_i += 1
        elif isinstance(node, ast.Constant) and isinstance(node.value, int) \
                and not isinstance(node.value, bool):
            if m.kind == "const" and const_i == m.node_index:
                node.value = node.value + 1
                return
            const_i += 1


def generate_mutants(f: Callable) -> Iterator[tuple[str, Callable]]:
    """Yield (label, mutant_function) for every single-node mutation of f."""
    src = _strip_indent(inspect.getsource(f))
    base_tree = ast.parse(src)
    name = f.__name__

    plan = _plan_mutations(base_tree)
    for m in plan:
        mtree = copy.deepcopy(base_tree)
        _apply_mutation(mtree, m)
        try:
            mutant = _compile_func(mtree, name)
        except Exception:
            continue  # a mutation that produces invalid/uncompilable code: skip
        yield m.label(), mutant

    # ---- constant-return mutants ----
    # Replace the body of the function with `return <const>` for a few constants.
    # These are brutal tests of whether the spec pins down the actual VALUE: a spec
    # that only checks a range/type will accept "always return lo", exposing looseness
    # that operator-level mutations may miss.
    yield from _constant_return_mutants(base_tree, name, f)


def _constant_return_mutants(base_tree, name, f) -> Iterator[tuple[str, Callable]]:
    # find the function's argument names to build plausible constant returns
    func_def = None
    for node in ast.walk(base_tree):
        if isinstance(node, ast.FunctionDef):
            func_def = node
            break
    if func_def is None:
        return
    args = [a.arg for a in func_def.args.args]

    # candidate constant return expressions (as source), each plausible-but-wrong
    candidates = ["0", "1", "-1"]
    # also "return <arg>" for EACH argument — e.g. clamp returning lo or hi always,
    # which an in-range-only spec accepts by construction (a sharp under-constraint probe)
    candidates.extend(args)

    for expr_src in candidates:
        new_def = copy.deepcopy(func_def)
        try:
            ret_node = ast.parse(f"return {expr_src}").body[0]
        except Exception:
            continue
        new_def.body = [ret_node]
        mod = ast.Module(body=[new_def], type_ignores=[])
        try:
            mutant = _compile_func(mod, name)
            # sanity: must be callable with the right arity on a probe later
        except Exception:
            continue
        yield f"const-return: return {expr_src}", mutant
